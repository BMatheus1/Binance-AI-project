from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from btc_research.phase6_1 import (FourPolicyEngine, POLICIES,
                                   MarketEventDetector, evaluate_four_policies,
                                   extension_counterfactual)
from btc_research.phase6_news import (EventStore, RawFeedItem, SourcePolicy,
                                      assess_market_reaction, classify_item)
from btc_research.phase6_nlp import (CARDIFF_REVISION, FINBERT_MODEL_ID,
                                     QWEN3_MODEL_ID, QWEN3_REVISION,
                                     AssetImpact, FinancialNewsAnalysis,
                                     FinBERTClassifier, NeuralInferenceWorker,
                                     NewsInterpretationResult, SentimentResult,
                                     evaluate_labeled_cases, load_phase61_config,
                                     validate_qwen_output)
from btc_research.phase6_trading import DecisionLedger, MarketSnapshot
from btc_research.phase6_runtime import Phase61Supervisor


UTC = timezone.utc
NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


class FakeNeuralClassifier:
    @property
    def identity(self):
        return {"model_id": "fake-qwen", "revision": "test", "device": "cpu"}

    def interpret(self, texts):
        result = []
        for text in texts:
            negative = any(word in text.lower() for word in ("hack", "breach", "loss"))
            analysis = FinancialNewsAnalysis(
                sentiment="negative" if negative else "neutral",
                sentiment_confidence=.95 if negative else .7,
                main_event="security incident" if negative else "news",
                affected_assets=["BTCUSDT"],
                impacts=[AssetImpact(asset="BTCUSDT", direction="negative" if negative else "neutral",
                                     confidence=.95 if negative else .7, rationale="test evidence")],
                source_reliability="high", novelty=.8, intensity=.9 if negative else .3,
                contradictory_information=False, contradiction_notes="",
                possibly_priced_in="unknown", insufficient_information=False,
                hallucination_risk="low", prompt_injection_detected=False,
                limitations=[], order_instruction=None)
            result.append(NewsInterpretationResult(
                hashlib.sha256(text.encode()).hexdigest(), analysis, "fake-qwen", "test",
                "cpu", .1, True))
        return result

    def classify(self, texts):
        results = []
        for text in texts:
            negative = .95 if any(word in text.lower() for word in ("hack", "breach", "loss")) else .05
            probabilities = {"negative": negative, "neutral": .03,
                             "positive": 1 - negative - .03}
            label = max(probabilities, key=probabilities.get)
            results.append(SentimentResult(
                hashlib.sha256(text.encode()).hexdigest(), probabilities, label,
                probabilities[label], False, "synthetic-baseline", "test", "cpu", .1))
        return results


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot("BTCUSDT", NOW, 99.99, 100.01, 10_000_000,
                          100_000, 100_000, 10, 25, .7)


def _event(title: str, summary: str):
    source = SourcePolicy("official", "https://example.gov/feed", "official", 120)
    item = RawFeedItem(source, title, title, "https://example.gov/item", summary,
                       NOW - timedelta(minutes=1), NOW)
    return classify_item(item, NOW)


def test_independent_policy_a_matches_full_engine_without_reading_news(tmp_path):
    store = EventStore(tmp_path / "news.sqlite3")
    engine = FourPolicyEngine(event_store=store, ledger=DecisionLedger(tmp_path / "decisions.jsonl"),
                              neural_classifier=FakeNeuralClassifier())
    snapshots = [_snapshot()]
    forecasts = {"BTCUSDT": {"expected_gross_return_bps": None}}
    reasons = {"BTCUSDT": ("quantitative_threshold_abstention",)}
    expected = engine.evaluate(snapshots, as_of=NOW, forecasts=forecasts,
                                technical_reasons=reasons)["policies"]["A_quantitative"]

    def forbidden(*args, **kwargs):
        raise AssertionError("policy A must not wait for news or Qwen")

    engine.event_store.available = forbidden
    engine.neural.interpret = forbidden
    actual = engine.evaluate_quantitative(snapshots, as_of=NOW, forecasts=forecasts,
                                          technical_reasons=reasons)
    assert actual["policies"]["A_quantitative"] == expected
    assert actual["neural_interpretation"] == {}
    assert actual["orders_sent"] is False


@pytest.fixture(scope="module")
def tiny_finbert(tmp_path_factory):
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    path = tmp_path_factory.mktemp("tiny_finbert")
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "profit", "loss", "stable", "."]
    (path / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
    tokenizer = transformers.BertTokenizer(vocab_file=str(path / "vocab.txt"), do_lower_case=True)
    tokenizer.save_pretrained(path)
    config = transformers.BertConfig(
        vocab_size=len(vocab), hidden_size=12, num_hidden_layers=1,
        num_attention_heads=3, intermediate_size=16, num_labels=3,
        id2label={0: "positive", 1: "negative", 2: "neutral"},
        label2id={"positive": 0, "negative": 1, "neutral": 2},
    )
    model = transformers.BertForSequenceClassification(config)
    model.save_pretrained(path, safe_serialization=True)
    return path


def test_phase61_license_gate_and_fixed_identity():
    config = load_phase61_config()
    assert config["nlp"]["primary_model_id"] == QWEN3_MODEL_ID
    assert config["nlp"]["revision"] == QWEN3_REVISION
    assert config["nlp"]["weights_license"] == "Apache-2.0"
    assert config["nlp"]["commercial_use_allowed"]
    assert not config["nlp"]["experimental_finbert"]["enabled"]
    assert not config["nlp"]["experimental_finbert"]["commercial_use_allowed"]
    assert config["nlp"]["optional_cardiff_baseline"]["revision"] == CARDIFF_REVISION
    assert config["nlp"]["optional_cardiff_baseline"]["attribution_required"]
    assert not config["nlp"]["fine_tuning_enabled"]


def test_finbert_loads_and_infers_on_cpu_without_network(tiny_finbert):
    classifier = FinBERTClassifier(tiny_finbert, device="cpu", maximum_tokens=16)
    results = classifier.classify(["profit", "loss", "stable"])
    assert len(results) == 3 and classifier.identity["device"] == "cpu"
    assert classifier.identity["model_id"] == FINBERT_MODEL_ID
    assert all(sum(row.probabilities.values()) == pytest.approx(1) for row in results)
    assert all(row.inference_ms >= 0 for row in results)


def test_finbert_rejects_empty_text_and_unavailable_cuda(tiny_finbert):
    classifier = FinBERTClassifier(tiny_finbert, device="cpu")
    with pytest.raises(ValueError, match="non-empty"):
        classifier.classify([""])
    import torch
    if not torch.cuda.is_available():
        with pytest.raises(RuntimeError, match="CUDA"):
            FinBERTClassifier(tiny_finbert, device="cuda")


def test_sentiment_result_validates_three_probabilities():
    with pytest.raises(ValueError, match="sum"):
        SentimentResult("x", {"negative": .5, "neutral": .5, "positive": .5},
                        "negative", .5, False, "x", "x", "cpu", 1)


def _valid_qwen_json() -> str:
    return json.dumps({
        "sentiment": "negative", "sentiment_confidence": .91,
        "main_event": "Exchange disclosed a security incident",
        "affected_assets": ["BTCUSDT"],
        "impacts": [{"asset": "BTCUSDT", "direction": "negative",
                     "confidence": .88, "rationale": "Possible forced selling"}],
        "source_reliability": "medium", "novelty": .8, "intensity": .9,
        "contradictory_information": False, "contradiction_notes": "",
        "possibly_priced_in": "unknown", "insufficient_information": False,
        "hallucination_risk": "low", "prompt_injection_detected": False,
        "limitations": ["No market reaction data"], "order_instruction": None,
    })


def test_qwen_output_is_strictly_structured_and_has_no_order():
    analysis = validate_qwen_output(_valid_qwen_json())
    assert analysis.impacts[0].asset == "BTCUSDT"
    assert analysis.possibly_priced_in == "unknown"
    assert analysis.order_instruction is None
    invalid = json.loads(_valid_qwen_json())
    invalid["unexpected"] = "field"
    with pytest.raises(Exception, match="extra"):
        validate_qwen_output(json.dumps(invalid))


def test_prompt_injection_forces_unreliable_result():
    analysis = validate_qwen_output(_valid_qwen_json(), injection_detected=True)
    assert analysis.prompt_injection_detected
    assert analysis.sentiment == "unreliable"
    assert analysis.insufficient_information


def test_async_neural_worker_times_out_without_blocking_other_tasks():
    class SlowInterpreter:
        @property
        def identity(self):
            return {"model_id": "slow", "revision": "test", "device": "cpu"}

        def interpret(self, texts):
            import time
            time.sleep(.05)
            return []

    async def scenario():
        worker = NeuralInferenceWorker(SlowInterpreter(), queue_size=1, timeout_seconds=.005)
        task = asyncio.create_task(worker.run())
        marker = []
        marker.append("market_loop_remained_responsive")
        result = await worker.submit("news")
        worker.stop()
        await task
        return marker, result

    marker, result = asyncio.run(scenario())
    assert marker and result.error_code == "timeout"
    assert result.analysis.insufficient_information


def test_synthetic_labeled_set_is_authored_and_evaluable():
    payload = json.loads((load_phase61_config.__globals__["ROOT"] /
                          "knowledge/phase_6_1/sentiment_cases.json").read_text())
    report = evaluate_labeled_cases(FakeNeuralClassifier(), payload["cases"])
    assert payload["license"] == "CC0-1.0" and report["cases"] == 12
    assert "trading value" in report["limitation"]


def test_four_policies_use_same_snapshot_and_send_no_order(tmp_path):
    engine = FourPolicyEngine(event_store=EventStore(tmp_path / "events.db"),
                              ledger=DecisionLedger(tmp_path / "ledger.jsonl"),
                              neural_classifier=FakeNeuralClassifier())
    result = engine.evaluate([_snapshot()], as_of=NOW)
    assert set(result["policies"]) == set(POLICIES)
    assert all(block["selected"]["symbol"] == "BTCUSDT" for block in result["policies"].values())
    assert not result["orders_sent"] and not result["neural_confidence_is_price_probability"]


def test_negative_neural_event_vetoes_c_and_d(tmp_path):
    store = EventStore(tmp_path / "events.db")
    store.add(_event("Bitcoin hack", "A serious breach caused losses"))
    engine = FourPolicyEngine(event_store=store, ledger=DecisionLedger(tmp_path / "ledger.jsonl"),
                              neural_classifier=FakeNeuralClassifier())
    result = engine.evaluate([_snapshot()], as_of=NOW)
    assert result["policies"]["A_quantitative"]["selected"] is not None
    assert result["policies"]["C_qwen3_structured_news"]["selected"] is None
    assert result["policies"]["D_event_market_reaction"]["selected"] is None


def test_reaction_policy_requires_observed_confirmation(tmp_path):
    store = EventStore(tmp_path / "events.db")
    event = assess_market_reaction(_event("Bitcoin approval", "Strong inflows reported"),
                                   measured_at=NOW + timedelta(seconds=1),
                                   pre_receive_return_bps=1, post_receive_return_bps=4,
                                   volume_ratio=2, spread_bps=3)
    # Decision is after the reaction measurement, so the evidence is causal.
    store.add(event)
    engine = FourPolicyEngine(event_store=store, ledger=DecisionLedger(tmp_path / "ledger.jsonl"),
                              neural_classifier=FakeNeuralClassifier())
    result = engine.evaluate([_snapshot()], as_of=NOW + timedelta(seconds=1))
    assert result["policies"]["D_event_market_reaction"]["selected"] is not None


def test_four_policy_evaluator_and_duplicate_guard():
    rows = [{"instant": "1", **{name: .01 for name in POLICIES}},
            {"instant": "2", **{name: None for name in POLICIES}}]
    result = evaluate_four_policies(rows)
    assert result["same_observations"] and result["observations"] == 2
    assert all(block["trades"] == 1 for block in result["policies"].values())
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_four_policies([rows[0], rows[0]])


def test_extension_counterfactual_is_separate_and_bounded():
    result = extension_counterfactual(original_close_net=.5, actual_close_net=.7,
                                      extended=True, original_minutes=20, actual_minutes=23)
    assert result["extension_incremental_net"] == pytest.approx(.2)
    with pytest.raises(ValueError, match="duration"):
        extension_counterfactual(original_close_net=.5, actual_close_net=.7,
                                 extended=True, original_minutes=20, actual_minutes=24)


def test_market_event_detector_uses_chronological_snapshots():
    previous = _snapshot()
    current = MarketSnapshot("BTCUSDT", NOW + timedelta(seconds=1), 100.99, 101.01,
                             25_000_000, 20_000, 20_000, 30, 25, .7)
    signal = MarketEventDetector().compare(previous, current)
    assert signal.priority_news_refresh
    assert {"abrupt_price_move", "abnormal_volume", "liquidity_drop"}.issubset(signal.event_types)
    with pytest.raises(ValueError, match="chronological"):
        MarketEventDetector().compare(current, previous)


def test_supervisor_writes_heartbeat_and_stops_cleanly(tmp_path):
    class FakeNews:
        def __init__(self):
            self.stopped = asyncio.Event()

        async def serve(self):
            await self.stopped.wait()

        def stop(self):
            self.stopped.set()

    class FakeMarket:
        def __init__(self):
            self.stopped = asyncio.Event()

        async def run(self, duration_seconds=None):
            await self.stopped.wait()
            return {"real_orders": False}

        def stop(self):
            self.stopped.set()

    heartbeat = tmp_path / "heartbeat.json"
    supervisor = Phase61Supervisor(news_service=FakeNews(), market_service=FakeMarket(),
                                   heartbeat_path=heartbeat, log_path=tmp_path / "service.log",
                                   heartbeat_seconds=.01)
    result = asyncio.run(supervisor.run(duration_seconds=.03))
    stored = json.loads(heartbeat.read_text())
    assert result["state"] == "stopped" and stored["state"] == "stopped"
    assert not stored["real_orders"] and not result["task_failures"]
