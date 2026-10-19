from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from btc_research.common import ROOT
from btc_research.phase6_2 import PersistentKillSwitch
from btc_research.phase6_connectivity import _assert_demo_url
from btc_research.phase6_4 import (AutonomousStore, ObservationStore,
                                   SupervisedDemoEngine, authorize_session,
                                   economic_report, load_phase64_config,
                                   prepare_authorization)


UTC = timezone.utc


def phase64_root(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "configs/phase_6_4.json", tmp_path / "configs/phase_6_4.json")
    return tmp_path


def exchange_info():
    return {"symbols": [{"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC",
                         "quoteAsset": "USDT", "quoteOrderQtyMarketAllowed": True,
                         "filters": [
                             {"filterType": "LOT_SIZE", "minQty": "0.00001",
                              "maxQty": "9000", "stepSize": "0.00001"},
                             {"filterType": "MARKET_LOT_SIZE", "minQty": "0",
                              "maxQty": "100", "stepSize": "0"},
                             {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
                         ]}]}


class FakeJournal:
    def unresolved(self):
        return []


class FakeBroker:
    enabled = True

    def __init__(self):
        self.submissions = []

    def exchange_info(self, symbol):
        return exchange_info()

    def average_price(self, symbol):
        return {"price": "50000"}

    def open_orders(self, symbol):
        return []

    def balances(self):
        return {"canTrade": True, "balances": [
            {"asset": "USDT", "free": "100", "locked": "0"},
            {"asset": "BTC", "free": "1", "locked": "0"}]}

    def server_time(self):
        return {"serverTime": int(datetime.now(UTC).timestamp() * 1000)}


class FakeService:
    def __init__(self, broker):
        self.broker = broker
        self.journal = FakeJournal()

    def plan(self, symbol, quote):
        return SimpleNamespace(quantity="0.0002")

    def _submit(self, *, diagnostic_id, symbol, side, quantity, client_id):
        self.broker.submissions.append(side)
        quote = "10" if side == "BUY" else "10.1"
        return {"status": "FILLED", "executedQty": quantity,
                "cummulativeQuoteQty": quote, "fills": [], "side": side}


def insert_candidate(root: Path) -> None:
    path = root / "runtime/phase_6_1/evaluations.sqlite3"
    path.parent.mkdir(parents=True)
    market = {"data_complete": True, "spread_bps": 1.0, "ask": 50000,
              "bid_depth_quote": 20_000, "ask_depth_quote": 20_000}
    prediction = {"state": "ready", "horizons": {"5": {
        "signal": "up", "probabilities": {"down": .1, "tie": .1, "up": .8}}}}
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE evaluations(
            evaluation_id TEXT PRIMARY KEY,evaluated_at TEXT,prediction_json TEXT,
            market_json TEXT,causal_valid INTEGER,symbol TEXT,policy TEXT)""")
        db.execute("INSERT INTO evaluations VALUES(?,?,?,?,?,?,?)",
                   ("eval-1", datetime.now(UTC).isoformat(), json.dumps(prediction),
                    json.dumps(market), 1, "BTCUSDT", "A_quantitative"))


def test_phase64_config_is_demo_only_and_frozen():
    config = load_phase64_config(ROOT)
    assert config["endpoints"]["rest"] == "https://demo-api.binance.com/api"
    assert config["experimental_demo"]["symbol"] == "BTCUSDT"
    assert config["experimental_demo"]["quote_amount"] == 10
    assert not config["experimental_demo"]["orders_enabled_by_default"]


def test_observation_cannot_complete_before_real_24_hours(tmp_path):
    root = phase64_root(tmp_path)
    config = load_phase64_config(root)
    store = ObservationStore(root / "runtime/phase_6_4/observation.sqlite3", config)
    session = store.active_or_create(10)
    store.add_sample(session, {"decision_worker": {"state": "abstaining", "evaluations_recorded": 14},
                               "collectors": {}, "demo_public": {"available": True}})
    assert not store.status(session)["minimum_24h_completed"]
    with sqlite3.connect(store.path) as db:
        old = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
        db.execute("UPDATE observation_sessions SET started_at=? WHERE session_id=?", (old, session))
    store.add_sample(session, {"decision_worker": {"state": "abstaining", "evaluations_recorded": 18},
                               "collectors": {}, "demo_public": {"available": True}})
    assert store.status(session)["minimum_24h_completed"]


def test_economic_report_keeps_validation_blocked_for_small_sample(tmp_path):
    root = phase64_root(tmp_path)
    path = root / "runtime/phase_6_1/evaluations.sqlite3"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE forecast_outcomes(
            cycle_id TEXT,horizon_minutes INTEGER,decision_at TEXT,p_down REAL,p_tie REAL,p_up REAL,
            signal TEXT,status TEXT,gross_return_bps REAL,net_return_bps REAL)""")
        db.execute("INSERT INTO forecast_outcomes VALUES(?,?,?,?,?,?,?,?,?,?)",
                   ("c1", 5, datetime.now(UTC).isoformat(), .1, .1, .8, "up", "resolved", 5.0, -5.0))
    result = economic_report(root)
    assert result["horizons"]["5"]["resolved_observations"] == 1
    assert not result["economically_validated"]
    assert not result["reserved_2026_07_to_09_holdout_consumed"]


def test_authorization_is_bound_to_running_boot_and_does_not_send_order(tmp_path, monkeypatch):
    root = phase64_root(tmp_path)
    runtime = root / "runtime/phase_6_4"
    runtime.mkdir(parents=True)
    (runtime / "engine.json").write_text(json.dumps({"boot_id": "boot-a", "state": "OBSERVE",
                                                      "updated_at": datetime.now(UTC).isoformat()}),
                                         encoding="utf-8")
    prepared = prepare_authorization(root)
    monkeypatch.setenv("BITCOIN_AI_ENABLE_DEMO_ORDERS", "I_UNDERSTAND_DEMO_ONLY")
    broker = FakeBroker()
    authorized = authorize_session(prepared["session_id"],
        "I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL", root,
        service_factory=lambda _: FakeService(broker))
    assert authorized["state"] == "authorized"
    assert not PersistentKillSwitch(root / "runtime/phase_6_2/kill_switch.json").status()["engaged"]
    assert AutonomousStore(runtime / "autonomous.sqlite3").status()["open_position"] is None


def test_mocked_authorized_cycle_opens_and_closes_btc_only(tmp_path):
    root = phase64_root(tmp_path)
    insert_candidate(root)
    broker = FakeBroker()
    engine = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(broker))
    store = engine.store
    session_id = "session-1"
    with sqlite3.connect(store.path) as db:
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (session_id, engine.boot_id, datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(), (datetime.now(UTC)+timedelta(hours=1)).isoformat(),
                    "authorized", "A_quantitative", "BTCUSDT", "10", "hash", 0, None))
    engine.kill.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    engine.cycle()
    opened = store.open_position()
    assert opened and opened["symbol"] == "BTCUSDT" and broker.submissions == ["BUY"]
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE positions SET planned_close_at=? WHERE position_id=?",
                   ((datetime.now(UTC)-timedelta(minutes=1)).isoformat(), opened["position_id"]))
    engine.cycle()
    assert store.open_position() is None
    assert broker.submissions == ["BUY", "SELL"]
    assert store.status()["closed_positions"][0]["net_quote"] == "0.1"


def test_connectivity_allowlist_rejects_production_hosts():
    assert _assert_demo_url("https://demo-api.binance.com/api", {"https"}) == (
        "demo-api.binance.com", 443)
    for url in ("https://api.binance.com/api", "wss://stream.binance.com/ws",
                "http://demo-api.binance.com/api"):
        with __import__("pytest").raises(ValueError, match="Demo allowlist"):
            _assert_demo_url(url, {"https", "wss"})


def test_engine_cannot_enter_without_a_bound_authorized_session(tmp_path):
    root = phase64_root(tmp_path)
    insert_candidate(root)
    broker = FakeBroker()
    engine = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(broker))
    engine.kill.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    engine.cycle()
    assert broker.submissions == []
    assert engine.store.open_position() is None
    assert engine.state == "OBSERVE"


def test_connection_failure_blocks_entry_and_engages_kill_switch(tmp_path):
    root = phase64_root(tmp_path)
    insert_candidate(root)
    engine = SupervisedDemoEngine(
        root, service_factory=lambda _: (_ for _ in ()).throw(ConnectionError("offline")))
    with sqlite3.connect(engine.store.path) as db:
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("session-offline", engine.boot_id, datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                    (datetime.now(UTC)+timedelta(hours=1)).isoformat(), "authorized",
                    "A_quantitative", "BTCUSDT", "10", "hash", 0, None))
    engine.kill.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    engine.cycle()
    assert engine.store.open_position() is None
    assert engine.kill.status()["engaged"]
    assert engine.state == "RECOVERY_REQUIRED"


def test_frozen_spread_limit_rejects_entry_without_submission(tmp_path):
    root = phase64_root(tmp_path)
    insert_candidate(root)
    evaluations = root / "runtime/phase_6_1/evaluations.sqlite3"
    with sqlite3.connect(evaluations) as db:
        market = json.loads(db.execute(
            "SELECT market_json FROM evaluations WHERE evaluation_id='eval-1'").fetchone()[0])
        market["spread_bps"] = 11.0
        db.execute("UPDATE evaluations SET market_json=? WHERE evaluation_id='eval-1'",
                   (json.dumps(market),))
    broker = FakeBroker()
    engine = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(broker))
    with sqlite3.connect(engine.store.path) as db:
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("session-spread", engine.boot_id, datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                    (datetime.now(UTC)+timedelta(hours=1)).isoformat(), "authorized",
                    "A_quantitative", "BTCUSDT", "10", "hash", 0, None))
    engine.kill.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    engine.cycle()
    assert broker.submissions == []
    assert engine.store.open_position() is None
    assert engine.store.status()["recent_activity"][0]["event_type"] == "entry_abstention"
    assert "spread_limit" in engine.store.status()["recent_activity"][0]["payload"]["reasons"]


def test_restart_preserves_position_but_invalidates_process_authorization(tmp_path):
    root = phase64_root(tmp_path)
    first = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(FakeBroker()))
    now = datetime.now(UTC)
    with sqlite3.connect(first.store.path) as db:
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("session-restart", first.boot_id, now.isoformat(), now.isoformat(),
                    (now+timedelta(hours=1)).isoformat(), "running", "A_quantitative",
                    "BTCUSDT", "10", "hash", 1, None))
        db.execute("INSERT INTO positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("position-restart", "session-restart", "BTCUSDT", "A_quantitative",
                    "OPEN", "eval-restart", now.isoformat(),
                    (now+timedelta(minutes=5)).isoformat(), None, "0.0002", "10", None,
                    "50000", None, "[]", None, "entry-client", None, None, "{}"))
    restarted = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(FakeBroker()))
    assert restarted.boot_id != first.boot_id
    assert restarted._authorization() is None
    assert restarted.store.open_position()["position_id"] == "position-restart"
