from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from btc_research.common import ROOT, save_json
from btc_research.phase6 import MultiAssetMarketService
from btc_research.phase6_2 import (AUTONOMOUS_CONFIRMATION,
                                   DIAGNOSTIC_CONFIRMATION,
                                   KILL_SWITCH_CONFIRMATION,
                                   ExecutionJournal, PersistentKillSwitch,
                                   SymbolRules, autonomous_readiness,
                                   build_demo_service, endpoint_safety_check,
                                   environment_diagnostic, load_local_dotenv,
                                   load_phase62_config, summarize_account)
from btc_research.phase6_trading import LocalPaperBroker


def emit(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def load_environment() -> None:
    load_local_dotenv(ROOT)


def synced_service():
    service = build_demo_service(ROOT)
    sync = service.broker.synchronize_clock()
    return service, sync["server_time_offset_ms"]


def journal_summary(path: Path) -> dict:
    journal = ExecutionJournal(path)
    with __import__("sqlite3").connect(path) as conn:
        rows = conn.execute("SELECT state, COUNT(*) FROM order_intents GROUP BY state").fetchall()
    return {"states": dict(rows), "unresolved": len(journal.unresolved()),
            "diagnostic_orders_are_strategy_results": False}


async def observe(seconds: float) -> dict:
    result = await MultiAssetMarketService(ROOT).run(duration_seconds=seconds)
    result.update(mode="OBSERVE", orders_sent=False)
    save_json(ROOT / "reports/phase_6_2/observer_smoke.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bitcoin AI Trader Fase 6.2 — exclusivamente Binance Spot Demo")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("environment")
    sub.add_parser("public-check")
    sub.add_parser("auth-check")
    sub.add_parser("balances")
    rules = sub.add_parser("symbol-rules")
    rules.add_argument("--symbol", choices=list(load_phase62_config(ROOT)["universe"]), default="BTCUSDT")
    rules.add_argument("--quote", type=Decimal, default=Decimal("10"))
    sub.add_parser("endpoint-safety")
    observer = sub.add_parser("observe")
    observer.add_argument("--seconds", type=float, default=30)
    paper = sub.add_parser("paper")
    paper.add_argument("--symbol", choices=list(load_phase62_config(ROOT)["universe"]), default="BTCUSDT")
    paper.add_argument("--quantity", type=float, required=True)
    paper.add_argument("--bid", type=float, required=True)
    paper.add_argument("--ask", type=float, required=True)
    plan = sub.add_parser("diagnostic-plan")
    plan.add_argument("--symbol", choices=list(load_phase62_config(ROOT)["universe"]), default="BTCUSDT")
    plan.add_argument("--quote", type=Decimal, default=Decimal("10"))
    order = sub.add_parser("diagnostic-order")
    order.add_argument("--symbol", choices=list(load_phase62_config(ROOT)["universe"]), default="BTCUSDT")
    order.add_argument("--quote", type=Decimal, required=True)
    order.add_argument("--confirm", required=True)
    opened = sub.add_parser("open-orders")
    opened.add_argument("--symbol", choices=list(load_phase62_config(ROOT)["universe"]), default="BTCUSDT")
    sub.add_parser("results")
    switch = sub.add_parser("kill-switch")
    switch.add_argument("action", choices=["status", "engage", "clear"])
    switch.add_argument("--reason", default="manual")
    switch.add_argument("--confirm")
    sub.add_parser("autonomous-status")
    enable = sub.add_parser("enable-autonomous")
    enable.add_argument("--confirm", required=True)
    sub.add_parser("run-autonomous")
    sub.add_parser("stop-services")
    args = parser.parse_args()

    load_environment()
    kill = PersistentKillSwitch(ROOT / "runtime/phase_6_2/kill_switch.json")

    if args.command == "environment":
        emit(environment_diagnostic(ROOT))
    elif args.command == "public-check":
        service, offset = synced_service()
        emit({"endpoint": service.broker.base_url, "ping": service.broker.ping(),
              "server_time_offset_ms": offset, "public_connection": "ok",
              "orders_sent": False})
    elif args.command == "auth-check":
        service, offset = synced_service()
        account = service.broker.balances()
        summary = summarize_account(account)
        summary.update(authentication="ok", server_time_offset_ms=offset,
                       endpoint=service.broker.base_url, orders_sent=False)
        emit(summary)
    elif args.command == "balances":
        service, _ = synced_service()
        emit(summarize_account(service.broker.balances()))
    elif args.command == "symbol-rules":
        service, _ = synced_service()
        info = service.broker.exchange_info(args.symbol)
        parsed = SymbolRules.from_exchange_info(info, args.symbol)
        price = Decimal(str(service.broker.average_price(args.symbol)["price"]))
        row = parsed.public_record()
        try:
            row["quantity_for_requested_quote"] = str(parsed.quantity_for_quote(args.quote, price))
            row["requested_quote"] = str(args.quote)
            row["reference_price"] = str(price)
        except ValueError as exc:
            row["quantity_error"] = str(exc)
        row["orders_sent"] = False
        emit(row)
    elif args.command == "endpoint-safety":
        emit(endpoint_safety_check())
    elif args.command == "observe":
        emit(asyncio.run(observe(args.seconds)))
    elif args.command == "paper":
        broker = LocalPaperBroker()
        row = broker.submit_market(client_order_id="phase62-paper-local", symbol=args.symbol,
                                   side="BUY", quantity=args.quantity, bid=args.bid, ask=args.ask)
        emit({**asdict(row), "mode": "PAPER", "external_request": False})
    elif args.command == "diagnostic-plan":
        service, _ = synced_service()
        emit(asdict(service.plan(args.symbol, args.quote)))
    elif args.command == "diagnostic-order":
        service, _ = synced_service()
        result = service.execute_diagnostic(symbol=args.symbol, quote_amount=args.quote,
                                            confirmation=args.confirm)
        emit(result)
    elif args.command == "open-orders":
        service, _ = synced_service()
        rows = service.broker.open_orders(args.symbol)
        emit({"symbol": args.symbol, "count": len(rows), "orders": rows,
              "endpoint": service.broker.base_url})
    elif args.command == "results":
        emit(journal_summary(ROOT / "runtime/phase_6_2/execution.sqlite"))
    elif args.command == "kill-switch":
        if args.action == "status":
            emit(kill.status())
        elif args.action == "engage":
            emit(kill.engage(args.reason))
        else:
            emit(kill.clear(args.confirm or ""))
    elif args.command == "autonomous-status":
        emit(autonomous_readiness(ROOT))
    elif args.command == "enable-autonomous":
        if args.confirm != AUTONOMOUS_CONFIRMATION:
            raise PermissionError("confirmação DEMO_AUTONOMOUS inválida")
        ready = autonomous_readiness(ROOT)
        if not ready["ready"]:
            missing = [name for name, ok in ready["checks"].items() if not ok]
            raise RuntimeError("DEMO_AUTONOMOUS bloqueado; pendências: " + ", ".join(missing))
        state = {"enabled": True, "policy": ready["policy"], "environment": "DEMO",
                 "enabled_at": __import__("datetime").datetime.now(
                     __import__("datetime").timezone.utc).isoformat()}
        path = ROOT / "runtime/phase_6_2/autonomous.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        emit(state)
    elif args.command == "run-autonomous":
        state_path = ROOT / "runtime/phase_6_2/autonomous.json"
        ready = autonomous_readiness(ROOT)
        enabled = state_path.exists() and json.loads(state_path.read_text(encoding="utf-8")).get("enabled")
        if not ready["ready"] or not enabled:
            raise RuntimeError("DEMO_AUTONOMOUS não está habilitado e validado")
        raise RuntimeError("executor contínuo permanece bloqueado até validação prospectiva da política congelada")
    else:
        state = kill.engage("stop_services")
        stop = ROOT / "runtime/phase_6_2/stop_requested.json"
        stop.parent.mkdir(parents=True, exist_ok=True)
        stop.write_text(json.dumps({"stop_requested": True, "kill_switch": state}, indent=2),
                        encoding="utf-8")
        emit({"new_entries_blocked": True, "stop_request_written": str(stop),
              "note": "verifique posições e ordens abertas antes de encerrar o processo"})


if __name__ == "__main__":
    main()
