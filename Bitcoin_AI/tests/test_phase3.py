import json
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
import joblib
from pandas.testing import assert_frame_equal

from btc_research.external import ExternalEvent, macro_risk_filter
from btc_research.live_market import LocalOrderBook, SequenceMonitor
from btc_research.microstructure import (AGG_COLUMNS, AggTradeQualityError, MICRO_SPECS,
                                         ingest_archive, make_micro_features,
                                         read_aggtrade_chunks, reconstructed_candles)
from btc_research.prospective import (ImmutableLedger, PaperSession, PaperSpotConfig,
                                      ProspectiveObserver, feature_snapshot_hash,
                                      paper_fixed_payout, paper_spot_long, prospective_evaluation,
                                      write_prospective_report)


class DummyProspectiveModel:
    columns = ["x"]

    def predict_proba(self, frame):
        return np.tile([.1, .1, .8], (len(frame), 1))


def _agg_frame(day="2026-10-01", minutes=90):
    times = pd.date_range(day, periods=minutes * 2, freq="30s", tz="UTC")
    base = pd.Timestamp(day, tz="UTC")
    timestamp = ((times - base) / pd.Timedelta(microseconds=1) + base.value // 1000).astype("int64")
    ids = np.arange(1000, 1000 + len(times))
    return pd.DataFrame({
        "aggregate_trade_id": ids, "price": 60_000 + np.sin(np.arange(len(times)) / 10) * 20,
        "quantity": .01 + (np.arange(len(times)) % 5) * .001, "first_trade_id": ids * 2,
        "last_trade_id": ids * 2 + 1, "transact_time": timestamp,
        "is_buyer_maker": np.arange(len(times)) % 3 == 0, "is_best_match": True,
    })


def _zip(path, frame):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(path.stem + ".csv", frame[AGG_COLUMNS].to_csv(index=False, header=False))


def test_aggtrade_chunk_parse_and_incremental_ingest(tmp_path):
    path = tmp_path / "BTCUSDT-aggTrades-2026-10-01.zip"
    frame = _agg_frame()
    _zip(path, frame)
    chunks = list(read_aggtrade_chunks(path, chunksize=41))
    assert sum(map(len, chunks)) == len(frame) and len(chunks) > 1
    result = ingest_archive(path, tmp_path, chunksize=41)
    assert result["rows"] == len(frame) and result["minutes"] == 90
    assert result["duplicate_agg_ids"] == 0 and result["aggregate_id_gap_events"] == 0
    minutes = pd.read_parquet(tmp_path / result["minute_file"])
    candles = reconstructed_candles(minutes)
    assert len(candles) == 90 and candles.trades.sum() == len(frame) * 2


def test_aggtrade_duplicate_detected(tmp_path):
    path = tmp_path / "BTCUSDT-aggTrades-2026-10-01.zip"
    frame = _agg_frame(minutes=2)
    frame.loc[2, "aggregate_trade_id"] = frame.loc[1, "aggregate_trade_id"]
    _zip(path, frame)
    with pytest.raises(AggTradeQualityError, match="duplicado"):
        ingest_archive(path, tmp_path, chunksize=2)


def test_micro_features_are_causal_and_restart_after_gap():
    raw = _agg_frame(minutes=100)
    raw["event_time"] = pd.to_datetime(raw.transact_time, unit="us", utc=True)
    from btc_research.microstructure import _partial_minutes
    minutes = _partial_minutes(raw).rename(columns={"minute": "open_time"})
    first = make_micro_features(minutes)
    changed = minutes.copy()
    changed.loc[70:, "taker_buy_base"] *= 9
    second = make_micro_features(changed)
    assert_frame_equal(first.iloc[:70], second.iloc[:70])
    gapped = minutes.drop(index=50).reset_index(drop=True)
    features = make_micro_features(gapped)
    assert features.loc[50:53, "cum_delta_5"].isna().all()
    assert set(features.columns) - {"decision_time", "available_at"} == set(MICRO_SPECS)


def test_sequence_monitor_and_depth_gap_invalidation():
    monitor = SequenceMonitor()
    assert monitor.observe_aggtrade(10)["status"] == "first"
    assert monitor.observe_aggtrade(10)["status"] == "duplicate"
    assert monitor.observe_aggtrade(13)["missing_ids"] == 2
    book = LocalOrderBook()
    book.buffer_event({"U": 101, "u": 102, "b": [["99", "1"]], "a": [["101", "1"]]})
    book.install_snapshot({"lastUpdateId": 100, "bids": [["98", "2"]], "asks": [["102", "2"]]})
    assert book.top()["valid"] and book.last_update_id == 102
    assert not book.apply({"U": 105, "u": 105, "b": [], "a": []})
    assert not book.top()["valid"] and book.invalidations == 1


def test_depth_can_sync_on_first_event_after_snapshot():
    book = LocalOrderBook()
    book.install_snapshot({"lastUpdateId": 200, "bids": [["98", "2"]], "asks": [["102", "2"]]})
    assert not book.valid
    assert book.apply({"U": 200, "u": 201, "b": [["99", "1"]], "a": [["101", "1"]]})
    assert book.top()["valid"] and book.last_update_id == 201


def test_immutable_ledger_detects_tampering(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ImmutableLedger(path)
    now = datetime.now(timezone.utc)
    prediction = ledger.record_prediction(
        prediction_id="p1", decision_time=now, horizon_minutes=1, model_version="test",
        feature_snapshot_hash=feature_snapshot_hash({"x": 1}), probabilities=[.2, .1, .7],
        data_quality={"complete": True}, decision="up", threshold=.6)
    ledger.resolve("p1", event_end=now + pd.Timedelta(minutes=2), outcome=2,
                   entry={"ask": 100}, exit={"bid": 101})
    assert ledger.verify()["resolved"] == 1
    report = prospective_evaluation(ledger)
    assert report["metrics"]["accuracy"] == 1 and report["selected_opportunities"] == 1
    assert write_prospective_report(ledger, tmp_path / "report.json")["resolved"] == 1
    rows = path.read_text(encoding="utf-8").splitlines()
    altered = json.loads(rows[0])
    altered["decision"] = "down"
    rows[0] = json.dumps(altered)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="adulterado"):
        ledger.verify()


def test_technical_abstention_and_paper_costs(tmp_path):
    ledger = ImmutableLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="abstenção"):
        ledger.record_prediction(decision_time=datetime.now(timezone.utc), horizon_minutes=1,
                                 model_version="x", feature_snapshot_hash="x", probabilities=[.2, .1, .7],
                                 data_quality={"complete": False}, decision="up", threshold=.6)
    cheap = paper_spot_long(entry_ask=100, exit_bid=101, config=PaperSpotConfig(fee_bps_per_side=1))
    costly = paper_spot_long(entry_ask=100, exit_bid=101, config=PaperSpotConfig(fee_bps_per_side=20))
    assert cheap["net_quote"] > costly["net_quote"] and not cheap["real_order_sent"]
    assert paper_fixed_payout(correct=True, tie=False, payout=.8)["pnl_units"] == .8


def test_prospective_observer_writes_before_outcome_and_abstains(tmp_path):
    model_path = tmp_path / "model.joblib"
    joblib.dump(DummyProspectiveModel(), model_path)
    ledger = ImmutableLedger(tmp_path / "ledger.jsonl")
    observer = ProspectiveObserver(model_path, ledger, model_version="v1", horizon_minutes=1, threshold=.6)
    with pytest.raises(ValueError, match="Hash"):
        ProspectiveObserver(model_path, ledger, model_version="v1", horizon_minutes=1,
                            expected_sha256="0" * 64)
    now = datetime.now(timezone.utc)
    frame = pd.DataFrame({"decision_time": [now - pd.Timedelta(seconds=1)],
                          "available_at": [now - pd.Timedelta(seconds=1)], "x": [2.]})
    prediction = observer.observe(frame, {"complete": True}, now=now)
    assert prediction["decision"] == "up" and ledger.verify()["predictions"] == 1
    incomplete = frame.drop(columns="x")
    abstention = observer.observe(incomplete, {"complete": False, "reason": "missing"}, now=now)
    assert abstention["decision"] == "abstain_technical" and abstention["probabilities"] is None


def test_paper_session_tracks_drawdown_abstention_and_stop():
    session = PaperSession(PaperSpotConfig(fee_bps_per_side=0, max_drawdown_fraction=.001,
                                           max_daily_loss_fraction=.001))
    assert not session.observe_decision("abstain_policy")
    assert session.observe_decision("up")
    session.add_spot_result(entry_ask=100, exit_bid=99)
    state = session.status()
    assert not state["active"] and state["trades"] == 1 and state["abstention_rate"] == .5
    with pytest.raises(RuntimeError, match="interrompida"):
        session.add_spot_result(entry_ask=100, exit_bid=101)


def test_macro_filter_never_uses_future_event():
    now = datetime.now(timezone.utc)
    past = ExternalEvent("official", "past", "x", "", now - pd.Timedelta(minutes=2),
                         now - pd.Timedelta(minutes=1), "macro", "official", "risk only")
    future = ExternalEvent("official", "future", "x", "", now + pd.Timedelta(minutes=1),
                           now + pd.Timedelta(minutes=2), "regulatory_emergency", "official", "risk only")
    state = macro_risk_filter([past, future], now)
    assert state.level == "elevated" and not state.force_abstention and "future" not in state.reasons
