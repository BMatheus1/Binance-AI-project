from __future__ import annotations

import asyncio
import json
import time
from decimal import Decimal

import pytest

from btc_research.phase6_2 import (DIAGNOSTIC_CONFIRMATION,
                                   ExecutionJournal, PersistentKillSwitch,
                                   PriorityInferenceQueue, SymbolRules,
                                   DemoExecutionService, endpoint_safety_check,
                                   environment_diagnostic, floor_to_step,
                                   load_phase62_config)
from btc_research.phase6_trading import (BinanceDemoAPIError, BinanceDemoBroker, DecisionLedger,
                                         RequestsDemoTransport)


def exchange_info(symbol="BTCUSDT"):
    return {"symbols": [{"symbol": symbol, "status": "TRADING", "baseAsset": "BTC",
                         "quoteAsset": "USDT", "quoteOrderQtyMarketAllowed": True,
                         "filters": [
                             {"filterType": "LOT_SIZE", "minQty": "0.00001",
                              "maxQty": "9000", "stepSize": "0.00001"},
                             {"filterType": "MARKET_LOT_SIZE", "minQty": "0",
                              "maxQty": "100", "stepSize": "0"},
                             {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
                         ]}]}


class FakeBroker:
    enabled = True

    def __init__(self, *, ambiguous=False, unrecoverable=False, open_orders=None):
        self.ambiguous = ambiguous
        self.unrecoverable = unrecoverable
        self._open_orders = open_orders or []
        self.submissions = []

    def balances(self):
        return {"canTrade": True, "balances": [{"asset": "USDT", "free": "100", "locked": "0"}]}

    def exchange_info(self, symbol):
        return exchange_info(symbol)

    def average_price(self, symbol):
        return {"price": "50000"}

    def submit_market(self, **kwargs):
        self.submissions.append(kwargs)
        if self.ambiguous:
            raise TimeoutError("ambiguous")
        side = kwargs["side"]
        return {"status": "FILLED", "orderId": len(self.submissions),
                "executedQty": kwargs["quantity"], "fills": [], "side": side}

    def order_status(self, **kwargs):
        if self.unrecoverable:
            raise TimeoutError("still unknown")
        quantity = self.submissions[-1]["quantity"]
        return {"status": "FILLED", "orderId": 99, "executedQty": quantity, "fills": []}

    def cancel(self, **kwargs):
        return {"status": "CANCELED"}

    def open_orders(self, symbol):
        return self._open_orders


def build_service(tmp_path, broker):
    return DemoExecutionService(
        broker=broker,
        kill_switch=PersistentKillSwitch(tmp_path / "kill.json"),
        journal=ExecutionJournal(tmp_path / "orders.db"),
        ledger=DecisionLedger(tmp_path / "ledger.jsonl"),
        config=load_phase62_config(),
    )


def test_config_is_fail_closed_and_demo_only():
    config = load_phase62_config()
    assert config["default_mode"] == "OBSERVE"
    assert not config["real_trading_supported"]
    assert config["endpoints"]["rest"] == "https://demo-api.binance.com/api"
    assert not config["demo_execution"]["orders_enabled_by_default"]


def test_environment_diagnostic_never_returns_values(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("BINANCE_DEMO_API_KEY=top-secret\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    monkeypatch.setenv("BINANCE_DEMO_API_KEY", "top-secret")
    result = environment_diagnostic(tmp_path)
    assert result["dotenv_ignored"] and result["expected_variables"]["BINANCE_DEMO_API_KEY"]["nonempty"]
    assert "top-secret" not in json.dumps(result)


def test_production_endpoints_are_rejected():
    assert endpoint_safety_check()["production_endpoints_rejected"]
    with pytest.raises(ValueError):
        BinanceDemoBroker(base_url="https://api.binance.com/api")


def test_kill_switch_defaults_engaged_and_persists(tmp_path):
    path = tmp_path / "kill.json"
    switch = PersistentKillSwitch(path)
    assert switch.status()["engaged"]
    with pytest.raises(PermissionError):
        switch.clear("wrong")
    switch.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    assert not PersistentKillSwitch(path).status()["engaged"]
    PersistentKillSwitch(path).engage("test")
    assert PersistentKillSwitch(path).status()["engaged"]


def test_corrupt_kill_switch_fails_closed(tmp_path):
    path = tmp_path / "kill.json"
    path.write_text("not-json", encoding="utf-8")
    assert PersistentKillSwitch(path).status()["reason"] == "invalid_state_fail_closed"


def test_symbol_rules_fall_back_to_lot_step_and_floor_quantity():
    rules = SymbolRules.from_exchange_info(exchange_info(), "BTCUSDT")
    assert rules.market_step_size == Decimal("0.00001")
    assert rules.quantity_for_quote(Decimal("10"), Decimal("50000")) == Decimal("0.0002")
    assert floor_to_step(Decimal("1.239"), Decimal("0.01")) == Decimal("1.23")


def test_symbol_rules_reject_below_minimum_notional():
    rules = SymbolRules.from_exchange_info(exchange_info(), "BTCUSDT")
    with pytest.raises(ValueError, match="notional mínimo"):
        rules.quantity_for_quote(Decimal("4"), Decimal("50000"))


def test_journal_reserves_before_submission_and_blocks_duplicate(tmp_path):
    journal = ExecutionJournal(tmp_path / "orders.db")
    journal.reserve(client_order_id="x", diagnostic_id="d", symbol="BTCUSDT",
                    side="BUY", quantity="0.001")
    assert journal.get("x")["state"] == "PREPARED"
    with pytest.raises(ValueError, match="reenvio bloqueado"):
        journal.reserve(client_order_id="x", diagnostic_id="d", symbol="BTCUSDT",
                        side="BUY", quantity="0.001")


def test_diagnostic_plan_is_read_only(tmp_path):
    broker = FakeBroker()
    service = build_service(tmp_path, broker)
    plan = service.plan("BTCUSDT", Decimal("10"))
    assert plan.quantity == "0.0002" and not plan.order_will_be_sent
    assert broker.submissions == []


def test_diagnostic_requires_both_confirmation_and_cleared_kill_switch(tmp_path):
    service = build_service(tmp_path, FakeBroker())
    with pytest.raises(PermissionError, match="confirmação"):
        service.execute_diagnostic(symbol="BTCUSDT", quote_amount=Decimal("10"), confirmation="wrong")
    with pytest.raises(PermissionError, match="kill switch"):
        service.execute_diagnostic(symbol="BTCUSDT", quote_amount=Decimal("10"),
                                   confirmation=DIAGNOSTIC_CONFIRMATION)


def test_diagnostic_round_trip_reconciles_and_rearms_kill_switch(tmp_path):
    broker = FakeBroker()
    service = build_service(tmp_path, broker)
    service.kill_switch.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    result = service.execute_diagnostic(symbol="BTCUSDT", quote_amount=Decimal("10"),
                                        confirmation=DIAGNOSTIC_CONFIRMATION)
    assert [row["side"] for row in broker.submissions] == ["BUY", "SELL"]
    assert result["reconciled"] and not result["strategy_evaluation_eligible"]
    assert service.kill_switch.status()["engaged"]
    assert service.ledger.verify()["records"] == 2


def test_ambiguous_submit_queries_status_without_retry(tmp_path):
    broker = FakeBroker(ambiguous=True)
    service = build_service(tmp_path, broker)
    service.kill_switch.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    result = service.execute_diagnostic(symbol="BTCUSDT", quote_amount=Decimal("10"),
                                        confirmation=DIAGNOSTIC_CONFIRMATION)
    assert result["reconciled"]
    assert len(broker.submissions) == 2


def test_unknown_order_status_engages_kill_switch(tmp_path):
    broker = FakeBroker(ambiguous=True, unrecoverable=True)
    service = build_service(tmp_path, broker)
    service.kill_switch.clear("I_AUTHORIZE_BINANCE_DEMO_ONLY")
    with pytest.raises(RuntimeError, match="status da ordem desconhecido"):
        service.execute_diagnostic(symbol="BTCUSDT", quote_amount=Decimal("10"),
                                   confirmation=DIAGNOSTIC_CONFIRMATION)
    assert service.kill_switch.status()["engaged"]
    assert len(broker.submissions) == 1


def test_priority_queue_deduplicates_and_rejects_stale():
    queue = PriorityInferenceQueue(maxsize=2, maximum_age_seconds=10)
    now = time.time()
    assert queue.submit(text="fresh", fingerprint="a", received_at_epoch=now,
                        novelty=1, relevance=1)
    assert not queue.submit(text="dup", fingerprint="a", received_at_epoch=now,
                            novelty=1, relevance=1)
    assert not queue.submit(text="old", fingerprint="b", received_at_epoch=now - 11,
                            novelty=1, relevance=1)
    job = asyncio.run(queue.next_valid())
    assert job and job.text == "fresh"
    assert queue.metrics["duplicates"] == 1 and queue.metrics["stale"] == 1


def test_requests_transport_rejects_non_demo_before_network():
    transport = RequestsDemoTransport()
    with pytest.raises(ValueError, match="allowlist"):
        transport("GET", "https://api.binance.com/api/v3/account", {}, {})


def test_authenticated_reads_do_not_enable_order_actions():
    calls = []
    def transport(method, url, headers, params):
        calls.append((method, url))
        return {"canTrade": True, "balances": []}
    broker = BinanceDemoBroker(enabled=False, api_key="demo-key", api_secret="demo-secret",
                               transport=transport, clock_ms=lambda: 1)
    assert broker.balances()["canTrade"]
    with pytest.raises(RuntimeError, match="orders are disabled"):
        broker.submit_market(symbol="BTCUSDT", side="BUY", quantity="0.001", client_order_id="x")
    assert len(calls) == 1


def test_timestamp_rejection_resynchronizes_only_reads():
    calls = []

    def transport(method, url, headers, params):
        calls.append((method, url, dict(params)))
        if url.endswith("/time"):
            return {"serverTime": 1000000}
        if sum(url == entry[1] for entry in calls) == 1:
            raise BinanceDemoAPIError("timestamp", http_status=400, api_code=-1021)
        return {"canTrade": True, "balances": []}

    broker = BinanceDemoBroker(enabled=True, api_key="test", api_secret="test", transport=transport,
                               clock_ms=lambda: 1)
    assert broker.balances()["canTrade"]
    account = [row for row in calls if row[1].endswith("/account")]
    assert len(account) == 2
    assert account[0][2]["timestamp"] == 1
    assert account[1][2]["timestamp"] >= 1000000
    calls.clear()
    with pytest.raises(BinanceDemoAPIError):
        broker.submit_market(symbol="BTCUSDT", side="BUY", quantity="0.00012", client_order_id="once")
    assert len(calls) == 1
    assert calls[0][0] == "POST"

