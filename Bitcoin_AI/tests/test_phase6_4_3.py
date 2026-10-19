"""Active Demo tests use temporary databases and a fake exchange only."""
import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from btc_research.active_demo import (MODE, commission_rates, experiment_context,
    load_profile, mark_position, profile_hash, session_profile)
from btc_research.common import ROOT
from btc_research.phase6_4 import (SupervisedDemoEngine, authorize_session,
    prepare_authorization, stop_session)
from btc_research.unified_intelligence import UnifiedTradingIntelligenceEngine, UnifiedDecisionStore
from test_phase6_4 import FakeBroker, FakeService, insert_candidate, phase64_root

UTC = timezone.utc


class ActiveBroker(FakeBroker):
    bid = Decimal("50000")
    fee = "0.001"

    def commission(self, symbol):
        return {key: {"taker": self.fee if key == "standardCommission" else "0", "buyer": "0", "seller": "0"}
                for key in ("standardCommission", "specialCommission", "taxCommission")}

    def book_ticker(self, symbol):
        return {"bidPrice": str(self.bid), "askPrice": str(self.bid)}


class ActiveService(FakeService):
    def __init__(self, broker):
        super().__init__(broker)
        self.journal.transition = lambda *args: None

    def _submit(self, **kwargs):
        side, qty = kwargs["side"], Decimal(kwargs["quantity"])
        self.broker.submissions.append(side)
        price = self.broker.bid
        return {"status": "FILLED", "orderId": len(self.broker.submissions),
                "executedQty": str(qty), "cummulativeQuoteQty": str(qty*price),
                "time": int(datetime.now(UTC).timestamp()*1000),
                "fills": [{"qty": str(qty), "price": str(price),
                           "commission": str(qty*Decimal(".001") if side == "BUY" else qty*price*Decimal(".001")),
                           "commissionAsset": "BTC" if side == "BUY" else "USDT"}]}


def setup_active(tmp_path, monkeypatch, probes=False):
    root = phase64_root(tmp_path)
    shutil.copy2(ROOT / "configs/phase_6_4_3.json", root / "configs/phase_6_4_3.json")
    broker = ActiveBroker()
    service = ActiveService(broker)
    engine = SupervisedDemoEngine(root, service_factory=lambda _: service)
    assert engine._reconcile(None, None)
    engine._write_control()
    prepared = prepare_authorization(root, mode=MODE, allow_probes=probes)
    monkeypatch.setenv("BITCOIN_AI_ENABLE_DEMO_ORDERS", "I_UNDERSTAND_DEMO_ONLY")
    authorize_session(prepared["session_id"], prepared["confirmation"], root, service_factory=lambda _: service)
    engine._apply_profile(engine._authorization())
    insert_candidate(root)
    return root, engine, broker, service, prepared


def publish(engine, up=.55, momentum=2):
    path = engine.root / "runtime/phase_6_1/evaluations.sqlite3"
    candidate = engine._latest_candidate()
    now = datetime.now(UTC).isoformat()
    candidate["market"].update(momentum_5m_bps=momentum, volatility_bps=10)
    candidate["prediction"]["horizons"]["5"].update(signal="abstain",
        probabilities={"down": 1-up-.1, "tie": .1, "up": up})
    profile = engine.active_profile
    context = experiment_context(engine.store.path, datetime.now(UTC))
    decision = UnifiedTradingIntelligenceEngine(engine.demo, f"{profile['version']}:{profile_hash(profile)}").evaluate(
        evaluation_id=candidate["evaluation_id"], symbol="BTCUSDT", evaluated_at=now,
        prediction=candidate["prediction"], market=candidate["market"], estimated_cost_bps=None, experiment=context)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE evaluations SET evaluated_at=?,prediction_json=?,market_json=?", (now,json.dumps(candidate["prediction"]),json.dumps(candidate["market"])))
        db.execute("DELETE FROM unified_decisions")
    UnifiedDecisionStore(path).add(decision)
    return engine._latest_candidate()


def test_preparation_is_not_authorization_and_cannot_reuse_legacy_confirmation(tmp_path, monkeypatch):
    root, engine, broker, service, _ = setup_active(tmp_path, monkeypatch)
    stop_session(root)
    engine.state = "OBSERVE"
    engine._write_control()
    prepared = prepare_authorization(root, mode=MODE, allow_probes=True)
    assert session_profile(engine.store.path, prepared["session_id"])["allow_probes"]
    assert engine._authorization() is None and engine.kill.status()["engaged"]
    with pytest.raises(PermissionError):
        authorize_session(prepared["session_id"], "I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL", root)
    assert broker.submissions == []


def test_active_ai_mock_roundtrip_uses_real_fills_and_separate_dust(tmp_path, monkeypatch):
    root, engine, broker, _, _ = setup_active(tmp_path, monkeypatch)
    candidate = publish(engine)
    assert candidate["unified"]["entry_category"] == "AI_SIGNAL"
    assert engine._gate(engine._authorization(), candidate) == (True, [])
    engine.cycle()
    position = engine.store.open_position()
    assert position["payload"]["experiment_profile"]["mode"] == MODE
    assert broker.submissions == ["BUY"] and Decimal(position["entry_quote"]) <= 10
    broker.bid = Decimal("50300")
    engine.cycle()
    assert broker.submissions == ["BUY", "SELL"]
    assert engine.store.open_position() is None
    row = engine.store.status()["closed_positions"][0]
    economics = json.loads(row["payload_json"])["economics"]
    assert Decimal(row["net_quote"]) > 0
    assert Decimal(economics["cash_flow_quote"]) < 0  # Dust is retained inventory, not profit.
    assert Decimal(economics["residual_cost_basis_quote"]) > 0
    assert engine._residual_exposure(broker.bid) > 0
    assert row["close_reason"] == "take_profit_net_estimate"


@pytest.mark.parametrize("allow,elapsed,eligible", [(False,200,False),(True,0,False),(True,181,True)])
def test_probes_need_separate_consent_and_elapsed_window(tmp_path, monkeypatch, allow, elapsed, eligible):
    _, engine, broker, _, prepared = setup_active(tmp_path, monkeypatch, probes=allow)
    with sqlite3.connect(engine.store.path) as db:
        db.execute("UPDATE sessions SET authorized_at=?", ((datetime.now(UTC)-timedelta(seconds=elapsed)).isoformat(),))
    candidate = publish(engine, up=.4, momentum=-1)
    assert candidate["unified"]["entry_category"] == "EXPLORATORY_PROBE"
    assert engine._gate(engine._authorization(), candidate)[0] == eligible
    if eligible:
        engine.cycle()
        assert engine.store.open_position()["payload"]["decision"]["entry_category"] == "EXPLORATORY_PROBE"
    else:
        engine.cycle()
        assert broker.submissions == []


def test_profile_edit_blocks_entries_and_old_strategy_is_unchanged(tmp_path, monkeypatch):
    root, engine, broker, _, _ = setup_active(tmp_path, monkeypatch)
    candidate = publish(engine)
    path = root / "configs/phase_6_4_3.json"
    profile = json.loads(path.read_text())
    profile["limits"]["minimum_up_probability"] = .54
    path.write_text(json.dumps(profile))
    assert "active_profile_changed_after_freeze" in engine._gate(engine._authorization(), candidate)[1]
    engine.cycle()
    assert broker.submissions == []
    assert json.loads((root / "configs/phase_6_4.json").read_text())["experimental_demo"]["minimum_up_probability"] == .60


@pytest.mark.parametrize("change,reason", [("operation","planned_operation_loss_limit"),("session","planned_session_loss_limit"),("data","market_data_incomplete"),("future","signal_stale")])
def test_active_risk_vetoes(tmp_path, monkeypatch, change, reason):
    _, engine, broker, _, _ = setup_active(tmp_path, monkeypatch)
    candidate = publish(engine)
    if change == "operation":
        candidate["unified"]["planned_risk"]["planned_loss_quote_including_estimated_costs"] = .11
    elif change == "session":
        monkeypatch.setattr(engine, "_session_risk", lambda _: {"planned_risk_spent":.49,"probe_entries":0,"realized_losses":0,"unknown_closed_economics":False})
    elif change == "data":
        candidate["market"]["data_complete"] = False
    else:
        candidate["evaluated_at"] = (datetime.now(UTC)+timedelta(seconds=30)).isoformat()
    assert reason in engine._gate(engine._authorization(), candidate)[1]
    assert broker.submissions == []


@pytest.mark.parametrize("action,expected", [("stop","kill_switch"),("loss","net_loss_limit"),("time","planned_horizon"),("trail","trailing_net_giveback")])
def test_exit_rules_do_not_depend_on_qwen(tmp_path, monkeypatch, action, expected):
    _, engine, broker, service, _ = setup_active(tmp_path, monkeypatch)
    publish(engine)
    engine.cycle()
    position = engine.store.open_position()
    if action == "stop":
        stop_session(engine.root)
    elif action == "loss":
        broker.bid = Decimal("49000")
    elif action == "time":
        position["planned_close_at"] = (datetime.now(UTC)-timedelta(seconds=1)).isoformat()
    else:
        position["payload"]["management"] = {"mfe_net_quote":.019,"mae_net_quote":-.02}
    assert engine._exit_reason(position, None, service) == expected


def test_partial_entry_cancels_remainder_and_checks_actual_fills(tmp_path, monkeypatch):
    _, engine, broker, service, _ = setup_active(tmp_path, monkeypatch)
    calls = []
    order = {"status":"CANCELED","executedQty":".0001","orderId":1,"cummulativeQuoteQty":"5"}
    broker.cancel = lambda **kwargs: calls.append("cancel")
    broker.order_status = lambda **kwargs: order
    broker.account_trades = lambda *args, **kwargs: [{"orderId":1,"id":1,"qty":".0001","price":"50000","commission":".0000001","commissionAsset":"BTC"}]
    result = engine._confirmed_order(service, {"status":"PARTIALLY_FILLED"}, "one-intent")
    assert result["fills"][0]["commissionAsset"] == "BTC" and calls == ["cancel"]
    assert broker.submissions == []
    broker.account_trades = lambda *args, **kwargs: []
    with pytest.raises(RuntimeError, match="fills incomplete"):
        engine._confirmed_order(service, order, "one-intent")


def test_restart_recovers_terminal_entry_without_duplicate_buy(tmp_path, monkeypatch):
    root, engine, broker, service, _ = setup_active(tmp_path, monkeypatch)
    publish(engine)
    engine.cycle()
    position = engine.store.open_position()
    order = {**position["payload"]["entry"], "time":int(datetime.now(UTC).timestamp()*1000)}
    broker.order_status = lambda **kwargs: order
    with sqlite3.connect(engine.store.path) as db:
        db.execute("UPDATE positions SET state='ENTRY_SUBMITTING',opened_at=NULL,quantity=NULL")
    restarted = SupervisedDemoEngine(root, service_factory=lambda _: service)
    restarted.cycle()
    assert broker.submissions == ["BUY", "SELL"]  # Confirmed inventory exits under kill switch.
    assert restarted.kill.status()["engaged"] and restarted._authorization() is None
    assert restarted.store.open_position() is None


def test_commission_schedule_must_be_complete_and_within_budget(tmp_path, monkeypatch):
    root, engine, broker, service, _ = setup_active(tmp_path, monkeypatch)
    candidate = publish(engine)
    broker.fee = ".002"
    with pytest.raises(RuntimeError, match="cost ceiling"):
        engine._enter(engine._authorization(), candidate)
    assert broker.submissions == []
    with pytest.raises(ValueError, match="incomplete"):
        commission_rates({"standardCommission": {"taker":"0"}})
