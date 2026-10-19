"""Verify one CLOSED Demo cycle using authenticated reads. Never submits orders."""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from btc_research.common import save_json
from btc_research.phase6_2 import build_demo_service, load_local_dotenv


def verify(position_id: str) -> dict:
    path = ROOT / "runtime/phase_6_4/autonomous.sqlite3"
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM positions WHERE position_id=?", (position_id,)).fetchone()
    if row is None or row["state"] != "CLOSED":
        raise RuntimeError("position must already be CLOSED; this audit never sells")
    position = dict(row)
    payload = json.loads(position["payload_json"])
    load_local_dotenv(ROOT)
    service = build_demo_service(ROOT)
    server = service.broker.server_time()
    offset = int(server["serverTime"]) - int(time.time()*1000)
    service.broker.clock_ms = lambda: int(time.time()*1000) + offset
    orders = {}
    for name, side in (("entry", "BUY"), ("exit", "SELL")):
        order = service.broker.order_status(symbol="BTCUSDT", client_order_id=position[f"{name}_client_id"])
        if order.get("status") != "FILLED" or order.get("symbol") != "BTCUSDT" or order.get("side") != side:
            raise RuntimeError("exchange did not confirm the complete expected Demo order")
        if str(order["orderId"]) != str(payload[name]["orderId"]):
            raise RuntimeError("exchange/local order identity mismatch")
        orders[name] = order
    history = service.broker.account_trades("BTCUSDT", limit=1000)
    trades = {name: [t for t in history if str(t["orderId"]) == str(order["orderId"])] for name, order in orders.items()}
    for name, order in orders.items():
        if sum((Decimal(t["qty"]) for t in trades[name]), Decimal(0)) != Decimal(order["executedQty"]):
            raise RuntimeError("complete actual trade history is unavailable")
        if Decimal(order["cummulativeQuoteQty"]) != Decimal(position[f"{name}_quote"]):
            raise RuntimeError("exchange/local quote amount mismatch")
    fees = {}
    for name, fills in trades.items():
        fees[name] = {}
        for fill in fills:
            asset = fill["commissionAsset"]
            fees[name][asset] = fees[name].get(asset, Decimal(0)) + Decimal(fill["commission"])
    buy = Decimal(orders["entry"]["cummulativeQuoteQty"])
    sell = Decimal(orders["exit"]["cummulativeQuoteQty"])
    acquired = Decimal(orders["entry"]["executedQty"]) - fees["entry"].get("BTC", Decimal(0))
    disposed = Decimal(orders["exit"]["executedQty"]) + fees["exit"].get("BTC", Decimal(0))
    basis = buy + fees["entry"].get("USDT", Decimal(0))
    allocated = basis * disposed / acquired
    unknown_assets = sorted({asset for group in fees.values() for asset, amount in group.items() if amount and asset not in {"BTC", "USDT"}})
    realized = sell - fees["exit"].get("USDT", Decimal(0)) - allocated if not unknown_assets else None
    if realized is not None and (position["net_quote"] is None or abs(realized-Decimal(position["net_quote"])) > Decimal("0.00000001")):
        raise RuntimeError("actual fills and local realized result differ")
    account = service.broker.balances()
    open_orders = service.broker.open_orders("BTCUSDT")
    record = {"verified_at": datetime.now(timezone.utc).isoformat(), "environment": "Binance Spot Demo",
        "endpoint": service.broker.readiness()["base_url"], "session_id": position["session_id"],
        "position_id": position_id, "entry_category": payload["decision"]["entry_category"],
        "opened_at": position["opened_at"], "closed_at": position["closed_at"], "close_reason": position["close_reason"],
        "orders": orders, "actual_trades": trades,
        "fees_by_side": {side:{asset:str(value) for asset,value in group.items()} for side,group in fees.items()},
        "realized_net_quote": str(realized) if realized is not None else None,
        "cash_flow_quote": str(sell-buy-fees["entry"].get("USDT",Decimal(0))-fees["exit"].get("USDT",Decimal(0))),
        "residual_BTC": str(acquired-disposed), "residual_cost_basis_quote": str(basis-allocated),
        "unknown_fee_assets": unknown_assets, "open_order_count": len(open_orders),
        "unresolved_intents": len(service.journal.unresolved()), "account_can_trade": bool(account.get("canTrade")),
        "virtual_balances": [b for b in account.get("balances",[]) if b["asset"] in {"BTC","USDT"}],
        "actual_Demo_buy_and_sell_confirmed": True, "audit_sent_orders": False,
        "predictive_performance_eligible": payload["decision"]["entry_category"] == "AI_SIGNAL",
        "economic_advantage_proven": False}
    save_json(ROOT / "reports/phase_6_4_3" / f"{position_id}-exchange_verified.json", record)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--position-id", required=True)
    args = parser.parse_args()
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in args.position_id):
        raise ValueError("invalid position ID")
    result = verify(args.position_id)
    print(json.dumps({key:result[key] for key in ("verified_at","position_id","entry_category","realized_net_quote","cash_flow_quote","residual_BTC","fees_by_side","close_reason","open_order_count","unresolved_intents","actual_Demo_buy_and_sell_confirmed","audit_sent_orders")}, indent=2))
