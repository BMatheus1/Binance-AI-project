from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from btc_research.common import ROOT
from btc_research.dashboard_api import CachedDemoAccount, DashboardRepository, DashboardSettings
from btc_research.opportunity_research import (ExitExperiment, chronological_roles,
                                               executable_net, exit_candidate, pattern_hypotheses)
from btc_research.phase6_4 import load_phase64_config
from btc_research.phase6_decisions import ContinuousDecisionWorker
from btc_research.unified_intelligence import UnifiedDecisionStore, UnifiedTradingIntelligenceEngine

UTC = timezone.utc


def inputs():
    now = datetime.now(UTC).isoformat()
    return {"evaluation_id": "fixture-not-a-real-signal", "symbol": "BTCUSDT", "evaluated_at": now,
            "prediction": {"state": "ready", "horizons": {"5": {"signal": "up",
                "model_version": "test-only", "probabilities": {"down": .2, "tie": .01, "up": .79}}}},
            "market": {"candle_close_time": now, "data_available_at": now,
                       "quote_received_at": now, "book_received_at": now,
                       "data_complete": True, "bid": 49999, "ask": 50000, "spread_bps": 1,
                       "bid_depth_quote": 20000, "ask_depth_quote": 20000},
            "estimated_cost_bps": 14.0}


def intelligence():
    return UnifiedTradingIntelligenceEngine(load_phase64_config(ROOT)["experimental_demo"], "frozen-test")


def test_unified_proposal_is_not_authorization_and_does_not_invent_economics(tmp_path):
    result = intelligence().evaluate(**inputs())
    assert result.decision == "COMPRAR"
    assert result.costs["expected_net_bps"] is None
    assert result.uncertainty["favorable_net_move_probability"] is None
    assert result.execution_state == "PROPOSAL_ONLY_REQUIRES_SESSION_AND_RISK"
    assert not result.context["fusion"]["context_changes_entry"]
    store = UnifiedDecisionStore(tmp_path / "evaluations.sqlite3")
    assert store.add(result)
    assert not store.add(result)
    assert store.recent(store.path)[0]["decision_id"] == result.decision_id


@pytest.mark.parametrize("field,value", [("bid", float("nan")), ("ask", 0),
    ("ask_depth_quote", float("inf")), ("spread_bps", 11), ("data_complete", False)])
def test_malformed_market_blocks_central_proposal(field, value):
    data = inputs()
    data["market"][field] = value
    assert intelligence().evaluate(**data).decision != "COMPRAR"


@pytest.mark.parametrize("field,seconds", [("data_available_at", 1), ("candle_close_time", 1),
    ("candle_close_time", -121), ("quote_received_at", -6), ("book_received_at", -6)])
def test_temporal_contract_blocks_future_or_old_information(field, seconds):
    data = inputs()
    data["market"][field] = (datetime.fromisoformat(data["evaluated_at"]) + timedelta(seconds=seconds)).isoformat()
    assert intelligence().evaluate(**data).decision == "AGUARDAR_DADOS"


@pytest.mark.parametrize("up", [float("nan"), float("inf"), -.1, 1.1, None])
def test_invalid_probabilities_never_become_eligible(up):
    data = inputs()
    data["prediction"]["horizons"]["5"]["probabilities"]["up"] = up
    assert intelligence().evaluate(**data).decision != "COMPRAR"


def test_optional_qwen_context_cannot_promote_or_veto_frozen_a():
    data = inputs()
    a = intelligence().evaluate(**data)
    b = intelligence().evaluate(**data, context={"qwen3": {"state": "unavailable"}})
    assert a.decision == b.decision and a.reasons == b.reasons
    data["symbol"] = "ETHUSDT"
    assert intelligence().evaluate(**data).decision != "COMPRAR"


def test_gross_gain_can_be_net_loss_and_unknown_costs_stay_unknown():
    kwargs = dict(quantity=Decimal(".0002"), entry_ask=Decimal("50000"), exit_bid=Decimal("50001"),
                  buy_fee_rate=Decimal(".001"), sell_fee_rate=Decimal(".001"),
                  exit_slippage_rate=Decimal(".0001"))
    result = executable_net(**kwargs)
    assert Decimal(result["gross_quote"]) > 0 > Decimal(result["net_quote"])
    assert executable_net(**{**kwargs, "sell_fee_rate": None})["net_quote"] is None


def test_exit_experiment_does_not_extend_losses_or_take_gross_only_profit():
    config = ExitExperiment(50, .03, .2, 300, 180)
    assert exit_candidate(config=config, elapsed_seconds=100, gross_bps=1,
                          net_quote=-.02, peak_net_quote=0) is None
    assert exit_candidate(config=config, elapsed_seconds=300, gross_bps=-1,
                          net_quote=-.02, peak_net_quote=0, continuity_confirmed=True) == "planned_horizon"
    assert exit_candidate(config=config, elapsed_seconds=310, gross_bps=40,
                          net_quote=.04, peak_net_quote=.04, continuity_confirmed=True) is None
    assert exit_candidate(config=config, elapsed_seconds=480, gross_bps=40,
                          net_quote=.04, peak_net_quote=.04, continuity_confirmed=True) == "planned_horizon"
    assert exit_candidate(config=config, elapsed_seconds=20, gross_bps=-51,
                          net_quote=None, peak_net_quote=None) == "stop_loss"


def test_exit_trailing_never_loosens_and_requires_net_profit():
    config = ExitExperiment(50, .03, .2, 300)
    assert exit_candidate(config=config, elapsed_seconds=100, gross_bps=40,
                          net_quote=.035, peak_net_quote=.05) == "trailing_net_profit"


def test_pattern_hypotheses_are_causal_and_research_only():
    times = pd.date_range("2026-10-19", periods=61, freq="min", tz="UTC")
    frame = pd.DataFrame({"open_time": times, "close_time": times + pd.Timedelta(seconds=59),
                          "open": np.arange(61)+100, "high": np.arange(61)+102,
                          "low": np.arange(61)+99, "close": np.arange(61)+101, "volume": 100})
    result = pattern_hypotheses(frame, {}, as_of=times[-1]+pd.Timedelta(minutes=1))
    assert result["state"] == "research_only" and not result["operational"]
    assert len(result["patterns"]) == 9
    assert pattern_hypotheses(frame, {}, as_of=times[-1])["state"] == "unavailable"
    frame.loc[30, "open_time"] += pd.Timedelta(minutes=1)
    assert pattern_hypotheses(frame, {}, as_of=times[-1]+pd.Timedelta(minutes=1))["state"] == "unavailable"


def test_research_roles_purge_labels_and_reject_consumed_holdout():
    times = pd.date_range("2026-01-01", periods=12, freq="D", tz="UTC")
    rows = pd.DataFrame({"observed_at": times, "available_at": times,
                         "label_end": times + pd.Timedelta(days=1)})
    boundaries = tuple(f"2026-01-{day:02}T00:00:00Z" for day in (4, 7, 10, 13))
    blocks = chronological_roles(rows, boundaries)
    assert all(len(block) == 2 for block in blocks.values())
    rows.loc[0, "label_end"] = pd.Timestamp("2026-07-01", tz="UTC")
    with pytest.raises(ValueError, match="holdout"):
        chronological_roles(rows, boundaries)


def test_news_context_path_does_not_load_models_or_build_features(monkeypatch, tmp_path):
    worker = ContinuousDecisionWorker.__new__(ContinuousDecisionWorker)
    worker.quantitative_only = False
    worker.publish_quantitative = False
    worker.evaluations_recorded = worker.cycles_completed = 0
    worker.store = SimpleNamespace(add_cycle=lambda *args, **kwargs: 0)
    worker._build_cycle = lambda _: pytest.fail("duplicate feature engineering")
    result = {"as_of": datetime.now(UTC).isoformat(), "policies": {
        "A_quantitative": {"selected": None}, "B_conservative_news": {"selected": None}}, "forecasts": {}}
    worker.engine = SimpleNamespace(evaluate=lambda *args, **kwargs: result)
    instant = pd.Timestamp.now(tz="UTC")
    worker._evaluate_cycle(instant, ([], {}, {}, {}))
    assert worker.cycles_completed == 1


def test_account_failure_never_labels_cached_balance_current(tmp_path):
    import shutil
    (tmp_path / "configs").mkdir()
    shutil.copy2(ROOT / "configs/phase_6_2.json", tmp_path / "configs/phase_6_2.json")
    value = {"account": {"canTrade": True, "balances": []}, "prices": {}, "open_orders": {},
             "endpoint": "https://demo-api.binance.com/api", "received_at": datetime.now(UTC).isoformat()}
    repo = DashboardRepository(DashboardSettings(tmp_path), account_loader=lambda: value)
    assert repo.account_snapshot()["available"]
    repo.account.loader = lambda: (_ for _ in ()).throw(TimeoutError("fake failure"))
    result = repo.account_snapshot(force=True)
    assert not result["available"] and result["stale"] and result["balances"] == []


def test_market_features_model_central_decision_risk_fills_dashboard_end_to_end(tmp_path, monkeypatch):
    import shutil
    from btc_research.features import SPECS
    from btc_research.phase6_4 import SupervisedDemoEngine
    from test_phase6_4 import FakeBroker, FakeService, _authorize_fake
    (tmp_path / "configs").mkdir()
    for name in ("phase_6_1.json", "phase_6_2.json", "phase_6_4.json"):
        shutil.copy2(ROOT / "configs" / name, tmp_path / "configs" / name)

    class Model:
        columns = list(SPECS)
        def predict_proba(self, rows):
            assert np.isfinite(rows[self.columns].to_numpy()).all()
            return np.tile([.1, .1, .8], (len(rows), 1))

    def registry(worker):
        worker.models = {key: Model() for key in (1, 5, 15, 30)}
        worker.model_versions = {key: "fixture-only-not-trained" for key in worker.models}

    monkeypatch.setattr(ContinuousDecisionWorker, "_load_models", registry)
    worker = ContinuousDecisionWorker(tmp_path, quantitative_only=True)
    times = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("min")-pd.Timedelta(minutes=1),
                          periods=240, freq="min")
    prices = np.linspace(49900, 50000, len(times))
    frame = pd.DataFrame({"open_time": times, "close_time": times + pd.Timedelta(seconds=59),
                          "open": prices-1, "high": prices+2, "low": prices-2, "close": prices,
                          "volume": 10., "trades": 100, "taker_base": 5.})
    now = datetime.now(UTC).isoformat()
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        worker.candles[symbol] = frame.copy()
        worker.quotes[symbol] = {"bid": 50000, "ask": 50000, "received_at": now}
        worker.books[symbol] = {"valid": True, "spread_bps": 0., "bid_depth_quote": 20000,
                                "ask_depth_quote": 20000, "received_at": now}
        worker.quote_volume_24h[symbol] = 10000000
    worker._evaluate_cycle(times[-1])
    central = UnifiedDecisionStore.recent(worker.store.path, symbol="BTCUSDT")[0]
    assert central["decision"] == "COMPRAR"
    assert worker.engine.ledger.verify()["records"] == 4
    broker = FakeBroker()
    engine = SupervisedDemoEngine(tmp_path, service_factory=lambda _: FakeService(broker))
    _authorize_fake(engine)
    engine.cycle()
    position = engine.store.open_position()
    assert position["evaluation_id"] == central["evaluation_id"]
    assert position["payload"]["decision"]["unified_decision_id"] == central["decision_id"]
    with sqlite3.connect(engine.store.path) as db:
        db.execute("UPDATE positions SET planned_close_at=?", ((datetime.now(UTC)-timedelta(seconds=1)).isoformat(),))
    engine.cycle()
    assert broker.submissions == ["BUY", "SELL"]  # In-memory fake; no network.
    assert engine.store.open_position() is None
    assert engine.ledger.verify()["records"] >= 3
    repo = DashboardRepository(DashboardSettings(tmp_path), account_loader=lambda: None)
    operation = repo._strategy_operations()[0]
    assert operation["evaluation_id"] == central["evaluation_id"]
    assert operation["net_result_quote"] == pytest.approx(.1)
    events = repo.operational_events()
    assert len({row["event_id"] for row in events}) == len(events)
    assert any(row["type"] == "demo_position_closed" for row in events)
