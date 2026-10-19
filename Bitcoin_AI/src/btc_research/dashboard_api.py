"""Local, read-mostly FastAPI dashboard for Bitcoin AI Trader Phase 6.3.

The API reuses Phase 6-6.2 stores and safety controls. It never exposes
credentials, accepts arbitrary exchange endpoints, clears the kill switch or
enables trading.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import secrets
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import (Cookie, Depends, FastAPI, Header, HTTPException, Query,
                     Request, Response, WebSocket, WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .common import ROOT
from .phase6_2 import (ExecutionJournal, PersistentKillSwitch,
                       autonomous_readiness, environment_diagnostic,
                       load_local_dotenv, load_phase62_config,
                       summarize_account)
from .phase6_trading import BinanceDemoBroker, RequestsDemoTransport, UNIVERSE
from .phase6_4 import AutonomousStore, ObservationStore, load_phase64_config


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat()


def safe_decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def read_jsonl(path: Path, limit: int = 200) -> list[dict]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except json.JSONDecodeError:
            continue
    return rows


class Envelope(BaseModel):
    generated_at: str
    data: dict[str, Any]


class SessionResponse(BaseModel):
    authenticated: bool
    csrf_token: str
    expires_in_seconds: int


class KillSwitchRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=200)
    confirmation: Literal["ACIONAR KILL SWITCH"]


@dataclass(frozen=True)
class DashboardSettings:
    root: Path = ROOT
    origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    session_ttl_seconds: int = 8 * 60 * 60
    account_cache_seconds: int = 15
    allow_test_client: bool = False


class SessionStore:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def create(self) -> tuple[str, str]:
        session = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        with self._lock:
            self._sessions[session] = (time.time() + self.ttl_seconds, csrf)
        return session, csrf

    def validate(self, session: str | None, csrf: str | None = None) -> bool:
        if not session:
            return False
        with self._lock:
            item = self._sessions.get(session)
            if not item or item[0] <= time.time():
                self._sessions.pop(session, None)
                return False
            return csrf is None or secrets.compare_digest(item[1], csrf)

    def csrf(self, session: str) -> str | None:
        with self._lock:
            item = self._sessions.get(session)
            return item[1] if item and item[0] > time.time() else None

    def validate_stream_token(self, token: str | None) -> bool:
        if not token:
            return False
        now = time.time()
        with self._lock:
            expired = [key for key, value in self._sessions.items() if value[0] <= now]
            for key in expired:
                self._sessions.pop(key, None)
            return any(secrets.compare_digest(value[1], token)
                       for value in self._sessions.values())


class CachedDemoAccount:
    """Short-lived cache so dashboard reads cannot overload the Demo API."""
    def __init__(self, loader: Callable[[], dict], ttl_seconds: int = 15):
        self.loader = loader
        self.ttl_seconds = ttl_seconds
        self._value: dict | None = None
        self._loaded_at = 0.0
        self._lock = threading.Lock()
        self.last_error: str | None = None

    def get(self, force: bool = False) -> dict | None:
        with self._lock:
            if self._value is not None and not force and time.time() - self._loaded_at < self.ttl_seconds:
                return self._value
            try:
                self._value = self.loader()
                self._loaded_at = time.time()
                self.last_error = None
            except Exception as exc:
                self.last_error = type(exc).__name__
            return self._value


def default_account_loader() -> dict:
    load_local_dotenv(ROOT)
    transport = RequestsDemoTransport(timeout_seconds=8)
    broker = BinanceDemoBroker.from_environment(transport)
    server = broker.server_time()
    offset = int(server["serverTime"]) - int(time.time() * 1000)
    broker.clock_ms = lambda: int(time.time() * 1000) + offset
    account = broker.balances()
    open_orders = {symbol: broker.open_orders(symbol) for symbol in UNIVERSE}
    prices = {symbol: broker.average_price(symbol).get("price") for symbol in UNIVERSE}
    return {"account": account, "open_orders": open_orders, "prices": prices,
            "endpoint": broker.base_url, "received_at": iso_now()}


class DashboardRepository:
    def __init__(self, settings: DashboardSettings,
                 account_loader: Callable[[], dict] | None = None):
        self.settings = settings
        self.root = settings.root
        self.config = load_phase62_config(self.root)
        self.kill = PersistentKillSwitch(self.root / "runtime/phase_6_2/kill_switch.json")
        self.account = CachedDemoAccount(account_loader or default_account_loader,
                                         settings.account_cache_seconds)

    def _readonly(self, path: Path) -> sqlite3.Connection:
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=1)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection

    def account_snapshot(self, force: bool = False) -> dict:
        value = self.account.get(force)
        if value is None:
            return {"available": False, "error": self.account.last_error,
                    "balances": [], "open_orders": [], "prices": {}, "received_at": None}
        summary = summarize_account(value["account"])
        balances = []
        for row in summary["nonzero_balances"]:
            asset = row["asset"]
            free = safe_decimal(row["free"])
            locked = safe_decimal(row["locked"])
            symbol = f"{asset}USDT"
            price = Decimal("1") if asset == "USDT" else safe_decimal(value["prices"].get(symbol))
            reference_source = "quote_currency" if asset == "USDT" else (
                "binance_demo_average_price" if price is not None else None)
            quote_value = (free + locked) * price if free is not None and locked is not None and price else None
            category = "cash"
            if asset not in {"USDT", "USDC"}:
                category = "residual_dust" if quote_value is not None and quote_value < Decimal("5") else "asset_balance"
            balances.append({**row, "reference_price_usdt": number(price),
                             "reference_source": reference_source,
                             "quote_value_usdt": number(quote_value), "category": category})
        orders = [order for rows in value["open_orders"].values() for order in rows]
        equity_values = [safe_decimal(row["quote_value_usdt"]) for row in balances]
        unvalued_assets = [row["asset"] for row in balances if row["quote_value_usdt"] is None]
        equity = sum((item for item in equity_values if item is not None), Decimal("0")) if balances else None
        return {"available": True, "endpoint": value["endpoint"],
                "received_at": value["received_at"], "can_trade": summary["can_trade"],
                "account_type": summary["account_type"], "permissions": summary["permissions"],
                "balances": balances, "open_orders": orders,
                "open_order_count": len(orders), "prices": value["prices"],
                "equity_usdt": number(equity), "equity_complete": not unvalued_assets,
                "unvalued_assets": unvalued_assets}

    def _market_files(self, symbol: str, stream: str) -> list[Path]:
        folder = self.root / f"runtime/phase_6/market/{symbol}/{symbol.lower()}_{stream}"
        return sorted(folder.rglob("*.jsonl"), key=lambda path: path.stat().st_mtime)[-12:]

    def market(self, symbol: str, candle_limit: int = 240) -> dict:
        if symbol not in UNIVERSE:
            raise ValueError("símbolo fora do universo")
        candles_by_time: dict[int, dict] = {}
        last_received = None
        for path in self._market_files(symbol, "kline_1m"):
            for row in read_jsonl(path, limit=6000):
                kline = row.get("payload", {}).get("k", {})
                opened = kline.get("t")
                if opened is None:
                    continue
                candle = {"time": int(opened / 1000), "open": number(safe_decimal(kline.get("o"))),
                          "high": number(safe_decimal(kline.get("h"))), "low": number(safe_decimal(kline.get("l"))),
                          "close": number(safe_decimal(kline.get("c"))), "volume": number(safe_decimal(kline.get("v"))),
                          "closed": bool(kline.get("x"))}
                previous = candles_by_time.get(opened)
                if previous is None or candle["closed"] or not previous["closed"]:
                    candles_by_time[opened] = candle
                last_received = row.get("received_at") or last_received
        candles = sorted(candles_by_time.values(), key=lambda row: row["time"])[-candle_limit:]
        tick = None
        for path in self._market_files(symbol, "bookTicker"):
            rows = read_jsonl(path, limit=1)
            if rows:
                tick = rows[-1]
        bid = safe_decimal(tick.get("payload", {}).get("b")) if tick else None
        ask = safe_decimal(tick.get("payload", {}).get("a")) if tick else None
        price = (bid + ask) / 2 if bid is not None and ask is not None else (
            safe_decimal(candles[-1]["close"]) if candles else None)
        spread = ask - bid if ask is not None and bid is not None else None
        spread_bps = spread / price * Decimal("10000") if spread is not None and price else None
        closed = [row for row in candles if row["closed"]]
        change = None
        if len(closed) >= 2 and closed[-2]["close"]:
            change = (closed[-1]["close"] / closed[-2]["close"] - 1) * 100
        timestamp = (tick or {}).get("received_at") or last_received
        stale_seconds = None
        if timestamp:
            try:
                stale_seconds = max(0.0, (utc_now() - datetime.fromisoformat(timestamp)).total_seconds())
            except ValueError:
                pass
        return {"symbol": symbol, "price": number(price), "bid": number(bid), "ask": number(ask),
                "spread": number(spread), "spread_bps": number(spread_bps),
                "change_percent_1m": change, "last_update": timestamp,
                "stale_seconds": stale_seconds, "stream_state": "stale" if stale_seconds is None or stale_seconds > 15 else "connected",
                "candles": candles, "candle_source": "stored Binance Demo kline_1m",
                "markers": self.operation_markers(symbol)}

    def markets(self) -> dict:
        return {symbol: self.market(symbol) for symbol in UNIVERSE}

    def _order_rows(self) -> list[dict]:
        path = self.root / "runtime/phase_6_2/execution.sqlite"
        if not path.exists():
            return []
        with self._readonly(path) as db:
            rows = db.execute("SELECT * FROM order_intents ORDER BY created_at DESC").fetchall()
        result = []
        for raw in rows:
            row = dict(raw)
            try:
                row["payload"] = json.loads(row.pop("payload_json"))
            except json.JSONDecodeError:
                row["payload"] = {}
                row.pop("payload_json", None)
            result.append(row)
        return result

    def _strategy_operations(self) -> list[dict]:
        path = self.root / "runtime/phase_6_4/autonomous.sqlite3"
        if not path.exists():
            return []
        with self._readonly(path) as db:
            rows = db.execute("SELECT * FROM positions ORDER BY COALESCE(opened_at,rowid) DESC").fetchall()
        operations = []
        for raw in rows:
            row = dict(raw)
            try:
                payload = json.loads(row.get("payload_json") or "{}")
            except json.JSONDecodeError:
                payload = {}
            entry_quote = safe_decimal(row.get("entry_quote"))
            exit_quote = safe_decimal(row.get("exit_quote"))
            gross = exit_quote - entry_quote if exit_quote is not None and entry_quote is not None else None
            fees = []
            for side in ("entry", "exit"):
                for fill in payload.get(side, {}).get("fills", []):
                    amount = safe_decimal(fill.get("commission"))
                    if amount is not None:
                        fees.append({"side": side, "asset": fill.get("commissionAsset"),
                                     "amount": number(amount)})
            operations.append({
                "operation_id": row["position_id"], "category": "demo_strategy",
                "strategy_category": "EXPERIMENTAL_DEMO", "policy": row["policy"],
                "symbol": row["symbol"], "evaluation_id": row["evaluation_id"],
                "entry_time": row["opened_at"], "exit_time": row["closed_at"],
                "entry_price": number(safe_decimal(row["entry_price"])),
                "exit_price": number(safe_decimal(row["exit_price"])),
                "quantity": number(safe_decimal(row["quantity"])), "fees": fees,
                "gross_result_quote": number(gross),
                "net_result_quote": number(safe_decimal(row["net_quote"])),
                "net_result_reason": ("actual Demo fills" if row["net_quote"] is not None
                                      else "position is open or fill economics are incomplete"),
                "stop_loss": None, "planned_duration_minutes": 5,
                "planned_close_at": row["planned_close_at"],
                "close_reason": row["close_reason"], "status": row["state"].lower(),
                "exchange_states": [], "strategy_evaluation_eligible": True,
            })
        return operations

    @staticmethod
    def _fill_metrics(payload: dict) -> dict:
        quantity = safe_decimal(payload.get("executedQty"))
        quote = safe_decimal(payload.get("cummulativeQuoteQty"))
        average = quote / quantity if quote is not None and quantity else None
        fees = []
        for fill in payload.get("fills", []):
            amount = safe_decimal(fill.get("commission"))
            if amount:
                fees.append({"asset": fill.get("commissionAsset"), "amount": number(amount)})
        return {"executed_quantity": number(quantity), "quote_quantity": number(quote),
                "average_price": number(average), "fees": fees}

    def operations(self) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in self._order_rows():
            grouped[row["diagnostic_id"]].append(row)
        operations = []
        for diagnostic_id, rows in grouped.items():
            buy = next((row for row in rows if row["side"] == "BUY"), None)
            sell = next((row for row in rows if row["side"] == "SELL"), None)
            buy_metrics = self._fill_metrics(buy["payload"]) if buy else {}
            sell_metrics = self._fill_metrics(sell["payload"]) if sell else {}
            gross = None
            net = None
            residual_base = None
            residual_quote = None
            symbol = (buy or sell or {}).get("symbol")
            base_asset = symbol[:-4] if symbol and symbol.endswith("USDT") else None
            quote_asset = "USDT" if symbol and symbol.endswith("USDT") else None
            fees = buy_metrics.get("fees", []) + sell_metrics.get("fees", [])
            fee_assets = {item["asset"] for item in fees}
            base_fee = sum(item["amount"] for item in fees if item["asset"] == base_asset)
            quote_fee = sum(item["amount"] for item in fees if item["asset"] == quote_asset)
            if (buy_metrics.get("executed_quantity") is not None and
                    sell_metrics.get("executed_quantity") is not None):
                residual_base = max(0.0, buy_metrics["executed_quantity"] - base_fee - sell_metrics["executed_quantity"])
                reference = sell_metrics.get("average_price") or buy_metrics.get("average_price")
                residual_quote = residual_base * reference if reference is not None else None
            if (buy_metrics.get("quote_quantity") is not None and
                    sell_metrics.get("quote_quantity") is not None and residual_quote is not None):
                gross = sell_metrics["quote_quantity"] + residual_quote - buy_metrics["quote_quantity"]
                if fee_assets.issubset({base_asset, quote_asset}):
                    net = gross - quote_fee
            operations.append({
                "operation_id": diagnostic_id, "category": "diagnostic", "policy": None,
                "symbol": symbol,
                "entry_time": (buy or {}).get("created_at"), "exit_time": (sell or {}).get("updated_at"),
                "entry_price": buy_metrics.get("average_price"), "exit_price": sell_metrics.get("average_price"),
                "quantity": buy_metrics.get("executed_quantity"),
                "fees": fees, "residual_base_quantity": residual_base,
                "residual_quote_value_at_exit": residual_quote,
                "gross_result_quote": gross, "net_result_quote": net,
                "net_result_reason": ("diagnostic only; includes residual valued at exit price"
                                      if net is not None else "fees or fill data require additional valuation"),
                "stop_loss": None, "planned_duration_minutes": None,
                "close_reason": "controlled_diagnostic_round_trip" if sell else None,
                "status": "reconciled" if rows and all(row["state"] == "RECONCILED" for row in rows) else "pending",
                "exchange_states": [{"side": row["side"], "state": row["state"],
                                     "client_order_id": row["client_order_id"]} for row in rows],
                "strategy_evaluation_eligible": False,
            })
        operations.extend(self._strategy_operations())
        return sorted(operations, key=lambda row: row["entry_time"] or "", reverse=True)

    def operation_markers(self, symbol: str) -> list[dict]:
        markers = []
        for row in self.operations():
            if row["symbol"] != symbol:
                continue
            if row["entry_time"] and row["entry_price"] is not None:
                markers.append({"time": row["entry_time"], "price": row["entry_price"], "type": "entry",
                                "category": row["category"], "operation_id": row["operation_id"]})
            if row["exit_time"] and row["exit_price"] is not None:
                markers.append({"time": row["exit_time"], "price": row["exit_price"], "type": "exit",
                                "category": row["category"], "operation_id": row["operation_id"]})
        return markers

    def performance(self) -> dict:
        operations = self.operations()
        diagnostic = [row for row in operations if row["category"] == "diagnostic"]
        strategy = [row for row in operations if row["category"] in {"paper", "demo_strategy"}]
        completed = [row for row in strategy if row["net_result_quote"] is not None]
        returns = [row["net_result_quote"] for row in completed]
        wins = [value for value in returns if value > 0]
        losses = [value for value in returns if value < 0]
        curve, peak, drawdown = 0.0, 0.0, 0.0
        points = []
        for row in sorted(completed, key=lambda item: item["exit_time"] or ""):
            curve += row["net_result_quote"]
            peak = max(peak, curve)
            drawdown = max(drawdown, peak - curve)
            points.append({"time": row["exit_time"], "value": curve})
        known = bool(completed)
        return {
            "strategy": {"trade_count": len(strategy), "completed_with_net_result": len(completed),
                         "net_result": sum(returns) if known else None,
                         "win_rate": len(wins) / len(returns) if known else None,
                         "profit_factor": sum(wins) / -sum(losses) if losses else None,
                         "expectancy": sum(returns) / len(returns) if known else None,
                         "average_win": sum(wins) / len(wins) if wins else None,
                         "average_loss": sum(losses) / len(losses) if losses else None,
                         "max_drawdown": drawdown if known else None, "equity_curve": points},
            "diagnostic": {"operation_count": len(diagnostic), "operations": diagnostic,
                           "included_in_strategy_metrics": False},
            "paper": {"available": False, "reason": "no persisted paper operations found"},
            "shadow": {"available": False, "reason": "no prospective paired decision ledger found"},
            "historical": {"available": True, "location": "reports/", "mixed_with_live": False},
        }

    def news(self, limit: int = 100, asset: str | None = None, source: str | None = None,
             sentiment: str | None = None) -> list[dict]:
        path = self.root / "runtime/phase_6/events.sqlite3"
        if not path.exists():
            return []
        with self._readonly(path) as db:
            rows = db.execute("SELECT payload FROM events ORDER BY first_received_at DESC LIMIT ?", (min(limit, 500),)).fetchall()
        events = []
        for row in rows:
            try:
                event = json.loads(row["payload"])
            except json.JSONDecodeError:
                continue
            assets = event.get("affected_assets", [])
            sentiments = set(event.get("sentiment_by_asset", {}).values())
            if asset and asset not in assets:
                continue
            if source and source != event.get("source"):
                continue
            if sentiment and sentiment not in sentiments:
                continue
            try:
                latency = (datetime.fromisoformat(event["analyzed_at"]) -
                           datetime.fromisoformat(event["first_received_at"])).total_seconds()
                age_at_analysis = (datetime.fromisoformat(event["analyzed_at"]) -
                                   datetime.fromisoformat(event["published_at"])).total_seconds()
            except (KeyError, ValueError):
                latency = age_at_analysis = None
            events.append({"event_id": event.get("event_id"), "source": event.get("source"),
                           "title": event.get("title"), "url": event.get("url"),
                           "published_at": event.get("published_at"),
                           "received_at": event.get("first_received_at"),
                           "analyzed_at": event.get("analyzed_at"), "assets": assets,
                           "category": event.get("event_category"),
                           "sentiment": event.get("sentiment_by_asset", {}),
                           "relevance": event.get("interpretation_confidence"),
                           "novelty": event.get("novelty"),
                           "possible_reaction": event.get("market_reaction_evidence") or None,
                           "status": event.get("confirmation_status"), "inference_latency_seconds": latency,
                           "late": age_at_analysis is not None and age_at_analysis > self.config["demo_execution"]["maximum_news_age_seconds"],
                           "summary_available": bool(event.get("summary")),
                           "qwen_classification_available": False})
        return events

    def intelligence(self) -> dict:
        ledger_paths = [self.root / "runtime/phase_6/decision_ledger.jsonl",
                        self.root / "runtime/phase_6_1/decision_ledger.jsonl"]
        ledger_records = []
        for path in ledger_paths:
            ledger_records.extend(read_jsonl(path, 100))
        ledger_records = sorted(ledger_records, key=lambda row: row.get("recorded_at", ""), reverse=True)
        decisions = []
        database = self.root / "runtime/phase_6_1/evaluations.sqlite3"
        if database.exists():
            with self._readonly(database) as db:
                rows = db.execute("""
                    SELECT evaluation_id,cycle_id,evaluated_at,market_time,symbol,policy,
                           worker_state,prediction_json,estimated_cost_bps,expected_gross_bps,
                           expected_net_bps,decision,reasons_json,market_json,news_json,orders_sent
                    FROM evaluations WHERE causal_valid=1
                    ORDER BY evaluated_at DESC, symbol, policy LIMIT 200
                """).fetchall()
                invalidated = db.execute(
                    "SELECT COUNT(*) FROM evaluations WHERE causal_valid=0").fetchone()[0]
            for row in rows:
                decisions.append({
                    "evaluation_id": row[0], "cycle_id": row[1], "evaluated_at": row[2],
                    "market_time": row[3], "symbol": row[4], "policy": row[5],
                    "worker_state": row[6], "prediction": json.loads(row[7]),
                    "estimated_cost_bps": row[8], "expected_gross_bps": row[9],
                    "expected_net_bps": row[10], "decision": row[11],
                    "reasons": json.loads(row[12]), "market": json.loads(row[13]),
                    "news": json.loads(row[14]), "orders_sent": bool(row[15]),
                })
        policies = {
            "A_quantitative": {"description": "somente sinais quantitativos", "latest": None},
            "B_conservative_news": {"description": "notícias como veto conservador", "latest": None},
            "C_qwen3_structured_news": {"description": "Qwen3 estruturado", "latest": None},
            "D_event_market_reaction": {"description": "Qwen3 com confirmação de mercado", "latest": None},
        }
        for decision in decisions:
            if decision["policy"] in policies and policies[decision["policy"]]["latest"] is None:
                policies[decision["policy"]]["latest"] = decision
        heartbeat = read_json(self.root / "runtime/phase_6_1/heartbeat.json") or {}
        worker = dict(heartbeat.get("decision_worker") or
                      {"state": "not_running", "orders_sent": False})
        worker["service_state"] = heartbeat.get("state", "not_running")
        if heartbeat.get("state") != "running":
            worker["last_state"] = worker.get("state")
            worker["state"] = "not_running"
        return {"policies": policies, "recent_decisions": decisions[:50],
                "decision_data_available": bool(decisions),
                "worker": worker, "ledger_records": len(ledger_records),
                "invalidated_evaluations": invalidated if database.exists() else 0,
                "explanation_source": "recorded decision ledger only",
                "internal_chain_of_thought_exposed": False,
                "active_demo_policy": self.config["autonomous"]["frozen_policy"],
                "autonomous": autonomous_readiness(self.root)}

    def health(self) -> dict:
        heartbeat = read_json(self.root / "runtime/phase_6_1/heartbeat.json")
        observer = read_json(self.root / "reports/phase_6_2/observer_smoke.json")
        env = environment_diagnostic(self.root)
        event_counts = {"events": 0, "revisions": 0}
        events_path = self.root / "runtime/phase_6/events.sqlite3"
        if events_path.exists():
            with self._readonly(events_path) as db:
                event_counts = {"events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                                "revisions": db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]}
        try:
            import psutil
            process = psutil.Process()
            resources = {"cpu_percent": process.cpu_percent(interval=None),
                         "memory_rss_bytes": process.memory_info().rss}
        except Exception:
            resources = {"cpu_percent": None, "memory_rss_bytes": None}
        unresolved_count = 0
        journal_path = self.root / "runtime/phase_6_2/execution.sqlite"
        if journal_path.exists():
            terminal = ("FILLED", "CANCELED", "REJECTED", "EXPIRED", "RECONCILED")
            placeholders = ",".join("?" for _ in terminal)
            with self._readonly(journal_path) as db:
                unresolved_count = db.execute(
                    f"SELECT COUNT(*) FROM order_intents WHERE state NOT IN ({placeholders})", terminal
                ).fetchone()[0]
        return {
            "binance_demo_rest": {"state": "available" if self.account.get() else "unavailable",
                                  "last_error": self.account.last_error},
            "market_websocket": observer or {"all_healthy": None, "reason": "no smoke record"},
            "heartbeat": heartbeat,
            "qwen3": ((heartbeat or {}).get("decision_worker", {}).get("qwen3") or
                      {"state": "unknown", "reason": "no active worker telemetry"}),
            "news_queue": {"size": None, "reason": "no active worker telemetry"},
            "news_store": event_counts, "reconciliation": {"unresolved": unresolved_count,
                                                            "state": "ok" if not unresolved_count else "attention"},
            "kill_switch": self.kill.status(), "environment": env,
            "resources": resources, "checked_at": iso_now(),
        }

    def autonomous(self) -> dict:
        config_path = self.root / "configs/phase_6_4.json"
        if not config_path.exists():
            return {"state": "not_configured", "authorization": "cli_only",
                    "orders_enabled": False}
        config = load_phase64_config(self.root)
        engine = read_json(self.root / "runtime/phase_6_4/engine.json") or {
            "state": "not_running", "orders_enabled": False, "boot_id": None,
            "last_error": None, "updated_at": None}
        store = AutonomousStore(self.root / "runtime/phase_6_4/autonomous.sqlite3")
        state = store.status()
        if state["session"]:
            state["session"].pop("confirmation_hash", None)
        observation = ObservationStore(
            self.root / "runtime/phase_6_4/observation.sqlite3", config).status()
        economics = read_json(self.root / "reports/phase_6_4/economic_status.json") or {
            "economically_validated": False, "resolved_outcomes": 0,
            "limitations": ["economic report has not been generated"]}
        demo = config["experimental_demo"]
        limits = {key: demo[key] for key in (
            "symbol", "policy", "horizon_minutes", "minimum_up_probability",
            "quote_amount", "maximum_open_positions", "maximum_entries_per_session",
            "maximum_entries_per_day", "maximum_daily_loss_quote", "maximum_spread_bps",
            "maximum_slippage_bps", "cooldown_minutes", "planned_holding_minutes", "stop_loss_bps",
            "session_maximum_minutes")}
        account = self.account_snapshot()
        market = self.market("BTCUSDT")
        operations = self._strategy_operations()
        completed = [row for row in operations if row["net_result_quote"] is not None]
        realized = sum((row["net_result_quote"] for row in completed), 0.0) if completed else None
        fee_totals: dict[str, float] = defaultdict(float)
        for operation in operations:
            for fee in operation.get("fees", []):
                if fee.get("asset") and fee.get("amount") is not None:
                    fee_totals[str(fee["asset"])] += float(fee["amount"])
        position = state.get("open_position")
        unrealized = None
        if position:
            entry = safe_decimal(position.get("entry_price"))
            quantity = safe_decimal(position.get("quantity"))
            current = safe_decimal(market.get("price"))
            if entry is not None and quantity is not None and current is not None:
                unrealized = number((current - entry) * quantity)
        connectivity_report = read_json(
            self.root / "reports/phase_6_4_1/connectivity_status.json") or {}
        rest_connected = bool(account.get("available"))
        stream_connected = market.get("stream_state") == "connected"
        signal_summary = self._autonomous_signal_summary(observation.get("started_at"))
        return {"state": engine.get("state", "not_running"), "engine": engine,
                "mode": ("EXPERIMENTAL_DEMO" if engine.get("state") == "AUTHORIZED_DEMO"
                         else "OBSERVE"),
                "authorization": "cli_only", "session_and_positions": state,
                "observation": observation, "economic": economics, "limits": limits,
                "kill_switch": self.kill.status(), "environment": "Binance Spot Demo",
                "connection": {
                    "state": ("connected" if rest_connected and stream_connected else
                              "degraded" if rest_connected or connectivity_report.get(
                                  "public_connectivity_available") else "unavailable"),
                    "rest_authenticated": rest_connected,
                    "rest_error": account.get("error"),
                    "market_stream": market.get("stream_state"),
                    "market_last_update": market.get("last_update"),
                    "last_full_diagnostic_at": connectivity_report.get("checked_at"),
                    "last_full_diagnostic_public_ok": connectivity_report.get(
                        "public_connectivity_available"),
                    "last_full_diagnostic_auth_ok": connectivity_report.get(
                        "authenticated_connectivity_available"),
                },
                "account": account,
                "operations": operations[:100],
                "performance": {
                    "realized_net_usdt": realized,
                    "unrealized_gross_usdt_estimate": unrealized,
                    "unrealized_source": ("stored Binance Demo market stream midpoint"
                                          if unrealized is not None else None),
                    "fees_by_asset": dict(sorted(fee_totals.items())),
                    "completed_operations": len(completed),
                    "open_positions": 1 if position else 0,
                },
                "signals": signal_summary,
                "production_trading_supported": False,
                "economically_validated_category_available": bool(
                    economics.get("economically_validated", False)),
                "experimental_demo_ready_for_explicit_authorization": True}

    def _autonomous_signal_summary(self, since: str | None) -> dict:
        generated = 0
        by_signal: dict[str, int] = defaultdict(int)
        policy_abstentions = 0
        policy_reasons: dict[str, int] = defaultdict(int)
        evaluations_path = self.root / "runtime/phase_6_1/evaluations.sqlite3"
        if evaluations_path.exists():
            with self._readonly(evaluations_path) as db:
                query = ("SELECT prediction_json,decision,reasons_json FROM evaluations WHERE causal_valid=1 "
                         "AND symbol='BTCUSDT' AND policy='A_quantitative'")
                params: tuple[Any, ...] = ()
                if since:
                    query += " AND evaluated_at>=?"
                    params = (since,)
                for row in db.execute(query, params).fetchall():
                    generated += 1
                    try:
                        prediction = json.loads(row["prediction_json"])
                        signal = prediction.get("horizons", {}).get("5", {}).get("signal")
                    except (TypeError, json.JSONDecodeError):
                        signal = None
                    by_signal[str(signal or "unknown")] += 1
                    if row["decision"] == "abstain":
                        policy_abstentions += 1
                        try:
                            reasons = json.loads(row["reasons_json"])
                        except (TypeError, json.JSONDecodeError):
                            reasons = []
                        for reason in reasons:
                            policy_reasons[str(reason)] += 1
        consumed: dict[str, int] = {}
        ignored_reasons: dict[str, int] = defaultdict(int)
        store_path = self.root / "runtime/phase_6_4/autonomous.sqlite3"
        if store_path.exists():
            with self._readonly(store_path) as db:
                consumed = dict(db.execute(
                    "SELECT outcome,COUNT(*) FROM consumed_evaluations GROUP BY outcome").fetchall())
                rows = db.execute(
                    "SELECT payload_json FROM activity WHERE event_type='entry_abstention'").fetchall()
                for row in rows:
                    try:
                        payload = json.loads(row["payload_json"])
                    except (TypeError, json.JSONDecodeError):
                        continue
                    for reason in payload.get("reasons", []):
                        ignored_reasons[str(reason)] += 1
        processed = sum(int(value) for value in consumed.values())
        return {
            "generated_quantitative_evaluations": generated,
            "generated_by_5m_signal": dict(sorted(by_signal.items())),
            "processed_by_autonomous_engine": processed,
            "entry_attempts": int(consumed.get("entry_attempt", 0)),
            "ignored": policy_abstentions,
            "ignored_reasons": dict(sorted(policy_reasons.items())),
            "executor_abstentions": int(consumed.get("abstention", 0)),
            "executor_abstention_reasons": dict(sorted(ignored_reasons.items())),
            "not_processed_by_autonomous_engine": max(0, generated - processed),
            "scope": "BTCUSDT / A_quantitative / 5 minutes / prospective observation",
        }

    def logs(self, limit: int = 100) -> list[dict]:
        rows = []
        for path in (self.root / "runtime/phase_6_1/service.jsonl",
                     self.root / "runtime/phase_6_2/decision_ledger.jsonl"):
            for row in read_jsonl(path, limit):
                rows.append({"source": str(path.relative_to(self.root)),
                             "time": row.get("time") or row.get("recorded_at"),
                             "level": row.get("level", "INFO"),
                             "message": row.get("message") or row.get("record_type") or "record",
                             "details": {key: value for key, value in row.items()
                                         if key not in {"payload", "signature", "api_key", "secret"}}})
        return sorted(rows, key=lambda row: row.get("time") or "", reverse=True)[:limit]

    def overview(self) -> dict:
        account = self.account_snapshot()
        operations = self.operations()
        performance = self.performance()
        health = self.health()
        autonomous = self.autonomous()
        open_position = autonomous.get("session_and_positions", {}).get("open_position")
        mode = "DEMO_AUTONOMOUS_EXPERIMENTAL" if autonomous.get("state") == "AUTHORIZED_DEMO" else "OBSERVE"
        return {"system_state": "blocked" if self.kill.status()["engaged"] and not open_position else autonomous.get("state", "observation"),
                "environment": "DEMO", "mode": mode,
                "kill_switch": self.kill.status(), "autonomous": autonomous_readiness(self.root),
                "account": account, "strategy_performance": performance["strategy"],
                "diagnostic_operation_count": len([x for x in operations if x["category"] == "diagnostic"]),
                "positions": [open_position] if open_position else [],
                "positions_reason": None if open_position else "no intentional open strategy position recorded",
                "connectors": {"binance_rest": health["binance_demo_rest"],
                               "market_websocket": {"state": "healthy" if health["market_websocket"].get("all_healthy") else "unknown"},
                               "news_store": health["news_store"]},
                "last_update": iso_now()}

    def snapshot(self) -> dict:
        return {"overview": self.overview(), "markets": self.markets(), "health": self.health()}


def create_app(settings: DashboardSettings | None = None,
               account_loader: Callable[[], dict] | None = None) -> FastAPI:
    settings = settings or DashboardSettings()
    sessions = SessionStore(settings.session_ttl_seconds)
    repository = DashboardRepository(settings, account_loader)
    app = FastAPI(title="Bitcoin AI Trader Dashboard API", version="6.3.0",
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.repository = repository
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins),
                       allow_credentials=True, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "X-CSRF-Token", "X-Dashboard-Token"])

    def valid_origin(origin: str | None) -> bool:
        return origin in settings.origins

    def local_client(request: Request) -> bool:
        host = request.client.host if request.client else ""
        return host in {"127.0.0.1", "::1", "localhost"} or (settings.allow_test_client and host == "testclient")

    def authenticated(bai_session: str | None = Cookie(default=None)) -> str:
        if not sessions.validate(bai_session):
            raise HTTPException(status_code=401, detail="sessão local inválida ou expirada")
        return bai_session

    def authenticated_read(
        request: Request,
        bai_session: str | None = Cookie(default=None),
        dashboard_token: str | None = Header(default=None, alias="X-Dashboard-Token"),
    ) -> str:
        """Authorize read routes when an embedded browser rejects loopback cookies."""
        if sessions.validate(bai_session):
            return bai_session or "cookie"
        if not dashboard_token:
            raise HTTPException(status_code=401, detail="sessão local inválida ou expirada")
        if not local_client(request) or not valid_origin(request.headers.get("origin")):
            raise HTTPException(status_code=403, detail="acesso permitido somente pela interface local")
        if sessions.validate_stream_token(dashboard_token):
            return "read-token"
        raise HTTPException(status_code=401, detail="sessão local inválida ou expirada")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "mode": "local-observation", "trading_enabled": False}

    @app.post("/api/session", response_model=SessionResponse)
    def create_session(request: Request, response: Response,
                       origin: str | None = Header(default=None)) -> SessionResponse:
        if not local_client(request) or not valid_origin(origin):
            raise HTTPException(status_code=403, detail="acesso permitido somente pela interface local")
        token, csrf = sessions.create()
        response.set_cookie("bai_session", token, httponly=True, samesite="strict",
                            secure=False, max_age=settings.session_ttl_seconds, path="/")
        return SessionResponse(authenticated=True, csrf_token=csrf,
                               expires_in_seconds=settings.session_ttl_seconds)

    def envelope(data: dict) -> Envelope:
        return Envelope(generated_at=iso_now(), data=data)

    @app.get("/api/overview", response_model=Envelope)
    async def overview(_: str = Depends(authenticated_read)) -> Envelope:
        return envelope(await asyncio.to_thread(repository.overview))

    @app.get("/api/markets", response_model=Envelope)
    async def markets(symbol: str | None = Query(default=None),
                      _: str = Depends(authenticated_read)) -> Envelope:
        try:
            data = await asyncio.to_thread(repository.market, symbol) if symbol else await asyncio.to_thread(repository.markets)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return envelope(data if isinstance(data, dict) else {"items": data})

    @app.get("/api/operations", response_model=Envelope)
    async def operations(_: str = Depends(authenticated_read)) -> Envelope:
        return envelope({"items": await asyncio.to_thread(repository.operations)})

    @app.get("/api/performance", response_model=Envelope)
    async def performance(_: str = Depends(authenticated_read)) -> Envelope:
        return envelope(await asyncio.to_thread(repository.performance))

    @app.get("/api/intelligence", response_model=Envelope)
    async def intelligence(_: str = Depends(authenticated_read)) -> Envelope:
        return envelope(await asyncio.to_thread(repository.intelligence))

    @app.get("/api/autonomous", response_model=Envelope)
    async def autonomous(_: str = Depends(authenticated_read)) -> Envelope:
        return envelope(await asyncio.to_thread(repository.autonomous))

    @app.get("/api/news", response_model=Envelope)
    async def news(limit: int = Query(100, ge=1, le=500), asset: str | None = None,
                   source: str | None = None, sentiment: str | None = None,
                   _: str = Depends(authenticated_read)) -> Envelope:
        items = await asyncio.to_thread(repository.news, limit, asset, source, sentiment)
        return envelope({"items": items, "count": len(items)})

    @app.get("/api/system-health", response_model=Envelope)
    async def system_health(_: str = Depends(authenticated_read)) -> Envelope:
        return envelope(await asyncio.to_thread(repository.health))

    @app.get("/api/logs", response_model=Envelope)
    async def logs(limit: int = Query(100, ge=1, le=500),
                   _: str = Depends(authenticated_read)) -> Envelope:
        return envelope({"items": await asyncio.to_thread(repository.logs, limit)})

    @app.post("/api/control/kill-switch", response_model=Envelope)
    async def engage_kill_switch(payload: KillSwitchRequest,
                                 session: str = Depends(authenticated),
                                 csrf: str | None = Header(default=None, alias="X-CSRF-Token"),
                                 origin: str | None = Header(default=None)) -> Envelope:
        if not valid_origin(origin) or not csrf or not sessions.validate(session, csrf):
            raise HTTPException(status_code=403, detail="origem ou token CSRF inválido")
        state = await asyncio.to_thread(repository.kill.engage, f"dashboard:{payload.reason}")
        return envelope({"kill_switch": state, "new_entries_blocked": True})

    @app.get("/api/export/{dataset}.csv")
    async def export_csv(dataset: Literal["operations", "news"],
                         _: str = Depends(authenticated_read)) -> StreamingResponse:
        rows = await asyncio.to_thread(repository.operations if dataset == "operations" else repository.news)
        output = io.StringIO()
        if rows:
            fieldnames = sorted({key for row in rows for key in row})
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                                 for key, value in row.items()})
        response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8")
        response.headers["Content-Disposition"] = f'attachment; filename="phase6_3_{dataset}.csv"'
        return response

    @app.websocket("/api/ws")
    async def websocket(websocket: WebSocket) -> None:
        origin = websocket.headers.get("origin")
        csrf = websocket.query_params.get("csrf")
        if not valid_origin(origin) or not sessions.validate_stream_token(csrf):
            await websocket.close(code=4403)
            return
        await websocket.accept()
        try:
            while True:
                data = await asyncio.to_thread(repository.snapshot)
                await websocket.send_json({"type": "snapshot", "generated_at": iso_now(), "data": data})
                await asyncio.sleep(2)
        except WebSocketDisconnect:
            return

    return app


app = create_app()

