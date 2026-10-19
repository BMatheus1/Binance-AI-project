"""Read-only active Demo preflight and preservation evidence. Never authorizes."""
from __future__ import annotations
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from btc_research.active_demo import commission_rates, load_profile, profile_hash
from btc_research.common import digest, save_json
from btc_research.phase6_2 import PersistentKillSwitch, SymbolRules, build_demo_service, load_local_dotenv
from btc_research.phase6_4 import AutonomousStore, ObservationStore, load_phase64_config
from btc_research.unified_intelligence import UnifiedDecisionStore


def audit() -> dict:
    kill = PersistentKillSwitch(ROOT / "runtime/phase_6_2/kill_switch.json")
    if not kill.status()["engaged"]:
        raise RuntimeError("engage the kill switch before this read-only preflight")
    output = ROOT / "reports/phase_6_4_3"
    output.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((ROOT / "reports/phase_6_4_2/preservation_before.json").read_text(encoding="utf-8"))
    changed = [name for name, sha in baseline.items() if not (ROOT / name).exists() or digest(ROOT / name) != sha]
    preservation = {"checked_at": datetime.now(timezone.utc).isoformat(), "checked_files": len(baseline),
                    "changed_or_missing": changed, "all_preserved": not changed,
                    "holdout_used_for_strategy_selection": False}
    save_json(output / "preservation.json", preservation)
    profile = load_profile(ROOT, allow_probes=True)
    store = AutonomousStore(ROOT / "runtime/phase_6_4/autonomous.sqlite3")
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "environment": "Binance Spot Demo",
              "profile_sha256_with_probes": profile_hash(profile), "limits": profile["limits"],
              "kill_switch": kill.status(), "orders_sent_by_audit": False, "session_authorized_by_audit": False,
              "preservation": preservation, "blockers": []}
    load_local_dotenv(ROOT)
    service = build_demo_service(ROOT)
    try:
        server = service.broker.server_time()
        offset = int(server["serverTime"]) - int(time.time()*1000)
        service.broker.clock_ms = lambda: int(time.time()*1000) + offset
        account = service.broker.balances()
        orders = service.broker.open_orders("BTCUSDT")
        rates = commission_rates(service.broker.commission("BTCUSDT"))
        rules = SymbolRules.from_exchange_info(service.broker.exchange_info("BTCUSDT"), "BTCUSDT")
        book = service.broker.book_ticker("BTCUSDT")
        bid, ask = Decimal(book["bidPrice"]), Decimal(book["askPrice"])
        spread = (ask/bid-1)*10000
        quote = Decimal(str(profile["limits"]["quote_amount"])) / ((1+Decimal(rates["buy"]))*(1+Decimal(str(profile["limits"]["maximum_slippage_bps"]))/10000))
        qty = rules.quantity_for_quote(quote, ask)
        sellable = rules.quantity_for_quote(qty*(1-Decimal(rates["buy"]))*bid, bid)
        unresolved = service.journal.unresolved()
        report["authenticated_read"] = {"can_trade": bool(account.get("canTrade")),
            "virtual_usdt_free": next((row["free"] for row in account.get("balances", []) if row["asset"] == "USDT"), None),
            "open_orders": len(orders), "unresolved_intents": len(unresolved), "commission_estimates": rates,
            "book": {"bid": str(bid), "ask": str(ask), "spread_bps": str(spread)},
            "buy_quantity_if_authorized_at_this_quote": str(qty), "conservative_exit_quantity": str(sellable),
            "minimum_notional": str(rules.min_notional), "endpoint": service.broker.readiness().get("base_url")}
        if not account.get("canTrade") or orders or unresolved or store.open_position():
            report["blockers"].append("account_orders_or_position_not_clean")
        if spread > Decimal(str(profile["limits"]["maximum_spread_bps"])):
            report["blockers"].append("spread_limit")
        ceiling = Decimal(str(profile["limits"]["planning_fee_ceiling_bps_per_side"]))/10000
        if max(Decimal(rates["buy"]), Decimal(rates["sell"])) > ceiling:
            report["blockers"].append("commission_ceiling")
    except Exception as exc:
        # Only exception classification is exported; no signed URLs/headers.
        report["blockers"].append(f"read_only_preflight_failed:{type(exc).__name__}")
    engine = ROOT / "runtime/phase_6_4/engine.json"
    report["engine"] = json.loads(engine.read_text(encoding="utf-8")) if engine.exists() else None
    report["latest_btc_proposals"] = UnifiedDecisionStore.recent(ROOT / "runtime/phase_6_1/evaluations.sqlite3", limit=3, symbol="BTCUSDT")
    report["observation"] = ObservationStore(ROOT / "runtime/phase_6_4/observation.sqlite3", load_phase64_config(ROOT)).status()
    with sqlite3.connect(store.path) as db:
        report["experimental_position_states"] = dict(db.execute("SELECT state,COUNT(*) FROM positions GROUP BY state"))
    verified_cycles = [json.loads(path.read_text(encoding="utf-8")) for path in output.glob("*-exchange_verified.json")]
    report["live_round_trip_completed_during_this_phase"] = any(
        item.get("actual_Demo_buy_and_sell_confirmed") is True for item in verified_cycles)
    report["verified_cycle_count"] = sum(item.get("actual_Demo_buy_and_sell_confirmed") is True for item in verified_cycles)
    report["pending"] = ["explicit_authorization_for_new_session", "actual_Demo_buy_and_sell_after_authorization"]
    save_json(output / "preflight.json", report)
    return report


if __name__ == "__main__":
    result = audit()
    print(json.dumps({key:result[key] for key in ("checked_at","environment","blockers","experimental_position_states","orders_sent_by_audit","preservation","pending")}, indent=2))
