from __future__ import annotations

import json
import shutil
import sqlite3
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import pytest

from btc_research.common import ROOT, digest
from btc_research.phase6_2 import PersistentKillSwitch
from btc_research.phase6_connectivity import _assert_demo_url
from btc_research.phase6_4 import (AutonomousStore, ObservationStore,
                                   SupervisedDemoEngine, authorize_session,
                                   economic_report, load_phase64_config,
                                   prepare_authorization)
from btc_research.phase6_trading import BinanceDemoAPIError
from btc_research.unified_intelligence import UnifiedDecisionStore, UnifiedTradingIntelligenceEngine


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

    def readiness(self):
        return {"authenticated_reads_ready": True, "credentials_present": True,
                "base_url": "https://demo-api.binance.com/api",
                "production_endpoint_accessible": False}

    def exchange_info(self, symbol):
        return exchange_info()

    def average_price(self, symbol):
        return {"price": "50000"}

    def book_ticker(self, symbol):
        return {"bidPrice": "50000", "askPrice": "50000"}

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
        return SimpleNamespace(quantity="0.0002", available_quote_balance="100")

    def _submit(self, *, diagnostic_id, symbol, side, quantity, client_id):
        self.broker.submissions.append(side)
        quote = "10" if side == "BUY" else "10.1"
        return {"status": "FILLED", "executedQty": quantity,
                "cummulativeQuoteQty": quote, "fills": [], "side": side}


def insert_candidate(root: Path) -> None:
    path = root / "runtime/phase_6_1/evaluations.sqlite3"
    path.parent.mkdir(parents=True)
    now = datetime.now(UTC).isoformat()
    market = {"data_complete": True, "spread_bps": 1.0, "ask": 50000, "bid": 49999,
              "candle_close_time": now, "data_available_at": now,
              "quote_received_at": now, "book_received_at": now,
              "bid_depth_quote": 20_000, "ask_depth_quote": 20_000}
    prediction = {"state": "ready", "horizons": {"5": {
        "signal": "up", "probabilities": {"down": .1, "tie": .1, "up": .8}}}}
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE evaluations(
            evaluation_id TEXT PRIMARY KEY,evaluated_at TEXT,prediction_json TEXT,
            market_json TEXT,causal_valid INTEGER,symbol TEXT,policy TEXT)""")
        db.execute("INSERT INTO evaluations VALUES(?,?,?,?,?,?,?)",
                   ("eval-1", now, json.dumps(prediction),
                    json.dumps(market), 1, "BTCUSDT", "A_quantitative"))
    config = load_phase64_config(root)
    unified = UnifiedTradingIntelligenceEngine(config["experimental_demo"],
        f"{config['protocol_version']}:{digest(root / 'configs/phase_6_4.json')}")
    UnifiedDecisionStore(path).add(unified.evaluate(
        evaluation_id="eval-1", symbol="BTCUSDT", evaluated_at=now,
        prediction=prediction, market=market, estimated_cost_bps=14))


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
    now = datetime.now(UTC).isoformat()
    (runtime / "engine.json").write_text(json.dumps({"boot_id": "boot-a", "state": "OBSERVE",
                                                      "updated_at": now,
                                                      "reconciliation": {
                                                          "state": "healthy",
                                                          "last_success_at": now}}),
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
    assert opened["payload"]["decision"]["unified_decision_id"]
    assert opened["payload"]["decision"]["planned_risk"]["quote_amount"] == 10
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
    assert engine.state == "RECOVERY_RETRY_WAIT"


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


def _authorize_fake(engine):
    now = datetime.now(UTC)
    with sqlite3.connect(engine.store.path) as db:
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("recovery-session", engine.boot_id, now.isoformat(), now.isoformat(),
                    (now+timedelta(hours=1)).isoformat(), "authorized", "A_quantitative",
                    "BTCUSDT", "10", "hash", 0, None))
    engine.kill.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")


def test_transient_rest_failure_respects_backoff_and_recovery_never_reauthorizes(tmp_path):
    root = phase64_root(tmp_path)
    broker = FakeBroker()
    attempts = []

    def factory(_):
        attempts.append(1)
        if len(attempts) == 1:
            raise BinanceDemoAPIError("safe transport failure", transport_error="ReadTimeout")
        return FakeService(broker)

    engine = SupervisedDemoEngine(root, service_factory=factory)
    _authorize_fake(engine)
    engine.cycle()
    assert engine.reconciliation["transient"] is True
    assert engine.reconciliation["next_retry_at"] is not None
    assert engine.store.active_session() is None
    engine.cycle()
    assert len(attempts) == 1  # Repeated scheduler ticks do not ignore backoff.
    engine._next_reconcile_monotonic = 0
    engine.cycle()
    assert len(attempts) == 2
    assert engine.reconciliation["state"] == "healthy"
    assert engine.last_error is None
    assert engine.state == "OBSERVE"
    assert engine.kill.status()["engaged"]
    assert broker.submissions == []
    engine._write_control()
    assert json.loads(engine.control_path.read_text())["orders_enabled"] is False


@pytest.mark.parametrize("failure,category", [
    (BinanceDemoAPIError("auth", http_status=401, api_code=-2015), "authentication"),
    (BinanceDemoAPIError("invalid key", api_code=-2014), "authentication"),
    (BinanceDemoAPIError("tls", transport_error="SSLError"), "demo_api_rejected"),
    (RuntimeError("Binance Demo credentials are incomplete"), "runtime_configuration"),
    (RuntimeError("unknown runtime state"), "runtime_state"),
    (PermissionError("denied"), "permissions_or_authentication"),
])
def test_permanent_reconciliation_errors_require_intervention(tmp_path, failure, category):
    root = phase64_root(tmp_path)
    attempts = []

    def factory(_):
        attempts.append(1)
        raise failure

    engine = SupervisedDemoEngine(root, service_factory=factory)
    _authorize_fake(engine)
    engine.cycle()
    engine.cycle()
    assert len(attempts) == 1
    assert engine.reconciliation["category"] == category
    assert engine.reconciliation["transient"] is False
    assert engine.reconciliation["error"]["traceback"]
    assert engine.state == "RECOVERY_REQUIRED"
    assert engine.store.active_session() is None
    assert engine.kill.status()["engaged"]


def test_unknown_intent_blocks_without_retry_or_new_order(tmp_path):
    root = phase64_root(tmp_path)
    broker = FakeBroker()
    service = FakeService(broker)
    service.journal = SimpleNamespace(unresolved=lambda: [{"state": "UNKNOWN"}])
    engine = SupervisedDemoEngine(root, service_factory=lambda _: service)
    engine.cycle()
    assert engine.reconciliation["category"] == "unresolved_or_open_orders"
    assert engine.reconciliation["transient"] is False
    assert not engine._reconciled
    assert engine.kill.status()["engaged"]
    assert broker.submissions == []


@pytest.mark.parametrize("position_state,quantity,category", [
    ("OPEN", "2", "balance_divergence"),
    ("ENTRY_SUBMITTING", None, "position_state_unknown"),
    ("EXIT_SUBMITTING", "0.0002", "position_state_unknown"),
    ("RECOVERY_REQUIRED", "0.0002", "position_state_unknown"),
])
def test_position_divergences_remain_blocked_across_restart(tmp_path, position_state, quantity, category):
    root = phase64_root(tmp_path)
    broker = FakeBroker()
    engine = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(broker))
    position = {"state": position_state, "quantity": quantity,
                "session_id": "persisted-session"}
    assert not engine._reconcile(None, position)
    assert engine.reconciliation["category"] == category
    assert engine.kill.status()["engaged"]
    restarted = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(broker))
    assert not restarted._reconcile(None, position)
    assert restarted.reconciliation["category"] == category
    assert broker.submissions == []


def test_websocket_disconnect_blocks_fresh_candidate(tmp_path):
    root = phase64_root(tmp_path)
    insert_candidate(root)
    broker = FakeBroker()
    engine = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(broker),
                                  market_status=lambda: {"BTCUSDT": {
                                      "connection_state": "disconnected", "book_valid": False,
                                      "last_message_at": datetime.now(UTC).isoformat()}})
    _authorize_fake(engine)
    engine.cycle()
    assert broker.submissions == []
    assert engine.store.open_position() is None
    assert "live_market_disconnected_or_stale" in engine.store.status()["recent_activity"][0]["payload"]["reasons"]


def test_position_manager_has_capacity_when_default_worker_pool_is_busy(tmp_path):
    root = phase64_root(tmp_path)
    engine = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(FakeBroker()))

    async def scenario():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        release = threading.Event()
        occupied = threading.Event()
        managed = asyncio.Event()

        def slow_news():
            occupied.set()
            release.wait(5)

        def position_cycle():
            loop.call_soon_threadsafe(managed.set)
            engine.stop()

        engine.cycle = position_cycle
        blocker = loop.run_in_executor(None, slow_news)
        while not occupied.is_set():
            await asyncio.sleep(.001)
        task = asyncio.create_task(engine.run())
        try:
            await asyncio.wait_for(managed.wait(), timeout=2)
            assert not blocker.done()
        finally:
            release.set()
            engine.stop()
            await task
            await blocker

    asyncio.run(scenario())


def test_session_preparation_requires_healthy_authenticated_worker(tmp_path):
    root = phase64_root(tmp_path)
    engine = SupervisedDemoEngine(root, service_factory=lambda _: FakeService(FakeBroker()))
    engine._write_control()
    with pytest.raises(RuntimeError, match="not healthy"):
        prepare_authorization(root)
    engine.cycle()
    engine._write_control()
    assert prepare_authorization(root)["state"] == "prepared"
