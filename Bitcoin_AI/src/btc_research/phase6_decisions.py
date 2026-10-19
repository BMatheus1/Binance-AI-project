"""Continuous causal decision worker for Phase 6.1 observation mode.

The worker consumes public Binance events, evaluates only synchronized closed
one-minute candles and cannot access an order transport.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import aiohttp
import joblib
import numpy as np
import pandas as pd

from .common import ROOT, digest
from .decision import decisions
from .features import SPECS, make_features
from .phase4_live import _rest_klines, _stream_kline
from .phase6_1 import FourPolicyEngine, POLICIES
from .phase6_news import EventStore
from .phase6_nlp import (FinancialNewsAnalysis, NewsInterpretationResult,
                         QWEN3_MODEL_ID, QWEN3_REVISION, Qwen3Interpreter,
                         load_phase61_config, model_directory)
from .phase6_trading import DecisionLedger, MarketSnapshot


UTC = timezone.utc
UNIVERSE = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


class LazyQwen3Interpreter:
    """Load Qwen only when a causally available news item needs interpretation."""
    def __init__(self, root: Path):
        self.root = root
        self.config = load_phase61_config(root)["nlp"]
        self._interpreter = None
        self.state = "available_not_loaded" if model_directory(root).exists() else "unavailable"
        self.last_error: str | None = None

    @property
    def identity(self) -> dict:
        if self._interpreter is not None:
            return self._interpreter.identity
        return {"model_id": QWEN3_MODEL_ID, "revision": QWEN3_REVISION,
                "device": "not_loaded", "state": self.state}

    def _failure(self, text: str) -> NewsInterpretationResult:
        code = self.last_error or "qwen3_unavailable"
        return NewsInterpretationResult(
            hashlib.sha256(text.encode()).hexdigest(),
            FinancialNewsAnalysis.safe_failure(code), QWEN3_MODEL_ID,
            QWEN3_REVISION, "unavailable", 0.0, False, code)

    def interpret(self, texts: Sequence[str]) -> list[NewsInterpretationResult]:
        if not texts:
            return []
        if self._interpreter is None and self.state != "unavailable":
            try:
                cfg = self.config
                self.state = "loading"
                self._interpreter = Qwen3Interpreter(
                    model_directory(self.root), device=cfg["preferred_device"],
                    maximum_input_tokens=cfg["maximum_input_tokens"],
                    maximum_new_tokens=cfg["maximum_new_tokens"],
                    maximum_input_characters=cfg["maximum_input_characters"],
                    memory_limit_bytes=cfg["memory_limit_bytes"],
                    cache_entries=cfg["cache_entries"])
                self.state = "ready"
            except Exception as exc:  # safe degradation; policies A/B remain active
                self.last_error = f"qwen3_load_failed:{type(exc).__name__}"
                self.state = "unavailable"
        if self._interpreter is None:
            return [self._failure(text) for text in texts]
        try:
            return self._interpreter.interpret(texts)
        except Exception as exc:  # an NLP failure is a veto only for dependent policies
            self.last_error = f"qwen3_inference_failed:{type(exc).__name__}"
            self.state = "degraded"
            return [self._failure(text) for text in texts]

    def status(self) -> dict:
        return {"state": self.state, "last_error": self.last_error,
                "identity": self.identity}


class DecisionStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS evaluations (
                    evaluation_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL, market_time TEXT NOT NULL,
                    symbol TEXT NOT NULL, policy TEXT NOT NULL,
                    worker_state TEXT NOT NULL, prediction_json TEXT NOT NULL,
                    estimated_cost_bps REAL, expected_gross_bps REAL,
                    expected_net_bps REAL, decision TEXT NOT NULL,
                    reasons_json TEXT NOT NULL, market_json TEXT NOT NULL,
                    news_json TEXT NOT NULL, orders_sent INTEGER NOT NULL DEFAULT 0,
                    causal_valid INTEGER NOT NULL DEFAULT 1,
                    invalidated_reason TEXT,
                    UNIQUE(cycle_id, symbol, policy)
                );
                CREATE INDEX IF NOT EXISTS idx_evaluations_recent
                    ON evaluations(evaluated_at DESC);
                CREATE TABLE IF NOT EXISTS forecast_outcomes (
                    cycle_id TEXT NOT NULL, horizon_minutes INTEGER NOT NULL,
                    decision_at TEXT NOT NULL, feature_open_time TEXT NOT NULL,
                    entry_open_time TEXT NOT NULL, exit_open_time TEXT NOT NULL,
                    p_down REAL NOT NULL, p_tie REAL NOT NULL, p_up REAL NOT NULL,
                    signal TEXT NOT NULL, estimated_cost_bps REAL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    entry_price REAL, exit_price REAL, gross_return_bps REAL,
                    net_return_bps REAL, resolved_at TEXT, invalid_reason TEXT,
                    PRIMARY KEY(cycle_id, horizon_minutes)
                );
                CREATE INDEX IF NOT EXISTS idx_forecast_outcomes_status
                    ON forecast_outcomes(status, exit_open_time);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(evaluations)")}
            if "causal_valid" not in columns:
                db.execute("ALTER TABLE evaluations ADD COLUMN causal_valid INTEGER NOT NULL DEFAULT 1")
            if "invalidated_reason" not in columns:
                db.execute("ALTER TABLE evaluations ADD COLUMN invalidated_reason TEXT")
            db.execute("UPDATE evaluations SET expected_gross_bps=NULL, expected_net_bps=NULL "
                       "WHERE json_extract(prediction_json, '$.expected_gross_return_bps') IS NULL")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def add_cycle(self, cycle_id: str, result: dict, market: dict[str, dict]) -> int:
        rows = []
        forecasts = result.get("forecasts", {})
        for policy, block in result["policies"].items():
            for opportunity in block["opportunities"]:
                symbol = opportunity["symbol"]
                evaluation_id = hashlib.sha256(
                    f"{cycle_id}:{symbol}:{policy}".encode()).hexdigest()
                rows.append((
                    evaluation_id, cycle_id, result["as_of"],
                    market[symbol]["candle_close_time"], symbol, policy,
                    "abstaining" if opportunity["decision"] == "abstain" else "signal_ready",
                    json.dumps(forecasts.get(symbol, {}), sort_keys=True),
                    opportunity["cost_bps"], opportunity["expected_gross_bps"],
                    opportunity["expected_net_bps"], opportunity["decision"],
                    json.dumps(opportunity["reasons"], sort_keys=True),
                    json.dumps(market[symbol], sort_keys=True),
                    json.dumps({"event_ids": opportunity["news_event_ids"]}, sort_keys=True), 0,
                ))
        with self._connect() as db:
            db.executemany("""
                INSERT OR IGNORE INTO evaluations(
                    evaluation_id,cycle_id,evaluated_at,market_time,symbol,policy,
                    worker_state,prediction_json,estimated_cost_bps,expected_gross_bps,
                    expected_net_bps,decision,reasons_json,market_json,news_json,orders_sent)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, rows)
            btc = forecasts.get("BTCUSDT", {})
            opened = market.get("BTCUSDT", {}).get("candle_open_time")
            if btc.get("state") == "ready" and opened:
                feature_time = pd.Timestamp(opened)
                costs = [row[8] for row in rows if row[4] == "BTCUSDT" and row[8] is not None]
                cost = min(costs) if costs else None
                pending = []
                for key, forecast in btc.get("horizons", {}).items():
                    horizon = int(key)
                    probabilities = forecast["probabilities"]
                    pending.append((cycle_id, horizon, result["as_of"], feature_time.isoformat(),
                                    (feature_time + pd.Timedelta(minutes=1)).isoformat(),
                                    (feature_time + pd.Timedelta(minutes=horizon)).isoformat(),
                                    probabilities["down"], probabilities["tie"], probabilities["up"],
                                    forecast["signal"], cost))
                db.executemany("""
                    INSERT OR IGNORE INTO forecast_outcomes(
                        cycle_id,horizon_minutes,decision_at,feature_open_time,
                        entry_open_time,exit_open_time,p_down,p_tie,p_up,signal,estimated_cost_bps)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, pending)
        return len(rows)

    def resolve_outcomes(self, candles: pd.DataFrame) -> dict:
        """Resolve labels only after the required candles have closed."""
        if candles.empty:
            return {"resolved": 0, "invalid": 0}
        indexed = candles.drop_duplicates("open_time", keep="last").set_index("open_time")
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            pending = db.execute(
                "SELECT * FROM forecast_outcomes WHERE status='pending' ORDER BY exit_open_time"
            ).fetchall()
            resolved = invalid = 0
            now = datetime.now(UTC).isoformat()
            for row in pending:
                entry_time = pd.Timestamp(row["entry_open_time"])
                exit_time = pd.Timestamp(row["exit_open_time"])
                if exit_time not in indexed.index:
                    continue
                expected = pd.date_range(entry_time, exit_time, freq="1min")
                if any(instant not in indexed.index for instant in expected):
                    db.execute("""UPDATE forecast_outcomes SET status='invalid',invalid_reason=?,resolved_at=?
                                  WHERE cycle_id=? AND horizon_minutes=?""",
                               ("missing_candle_in_forward_window", now, row["cycle_id"],
                                row["horizon_minutes"]))
                    invalid += 1
                    continue
                entry_price = float(indexed.loc[entry_time, "open"])
                exit_price = float(indexed.loc[exit_time, "close"])
                gross = (exit_price / entry_price - 1.0) * 10_000.0
                cost = row["estimated_cost_bps"]
                net = gross - float(cost) if cost is not None else None
                db.execute("""UPDATE forecast_outcomes SET status='resolved',entry_price=?,exit_price=?,
                              gross_return_bps=?,net_return_bps=?,resolved_at=?
                              WHERE cycle_id=? AND horizon_minutes=?""",
                           (entry_price, exit_price, gross, net, now, row["cycle_id"],
                            row["horizon_minutes"]))
                resolved += 1
        return {"resolved": resolved, "invalid": invalid}

    def count(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM evaluations WHERE causal_valid=1").fetchone()[0])

    def invalidate_noncausal(self) -> list[str]:
        with self._connect() as db:
            cycles = [row[0] for row in db.execute(
                "SELECT DISTINCT cycle_id FROM evaluations WHERE causal_valid=1 AND evaluated_at<market_time"
            ).fetchall()]
            if cycles:
                placeholders = ",".join("?" for _ in cycles)
                db.execute(f"UPDATE evaluations SET causal_valid=0, invalidated_reason=? "
                           f"WHERE cycle_id IN ({placeholders})",
                           ("evaluation_preceded_candle_close", *cycles))
        return cycles


class ContinuousDecisionWorker:
    """Turn synchronized public market events into auditable abstentions/signals."""
    def __init__(self, root: Path = ROOT, *, rest_base: str = "https://data-api.binance.vision"):
        self.root = root
        self.rest_base = rest_base.rstrip("/")
        self.queue: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=20_000)
        self._stop = asyncio.Event()
        self.state = "created"
        self.started_at: str | None = None
        self.last_evaluation_at: str | None = None
        self.last_error: str | None = None
        self.cycles_completed = 0
        self.evaluations_recorded = 0
        self.dropped_events = 0
        self.gap_repairs_succeeded = 0
        self.gap_repairs_failed = 0
        self.missing_candles_observed = 0
        self.symbol_errors: dict[str, str] = {}
        self.warmup_attempts = 0
        self.warmup_failures = 0
        self.last_warmup_attempt_at: str | None = None
        self.candles = {symbol: pd.DataFrame() for symbol in UNIVERSE}
        self.quotes: dict[str, dict] = {}
        self.books: dict[str, dict] = {}
        self.quote_volume_24h: dict[str, float] = {}
        self.last_closed_open_time: dict[str, pd.Timestamp] = {}
        self.last_cycle_open_time: pd.Timestamp | None = None
        self.models: dict[int, object] = {}
        self.model_versions: dict[int, str] = {}
        self.threshold = .60
        self.payout = .80
        self.neural = LazyQwen3Interpreter(root)
        self.store = DecisionStore(root / "runtime/phase_6_1/evaluations.sqlite3")
        self.engine = FourPolicyEngine(
            event_store=EventStore(root / "runtime/phase_6/events.sqlite3"),
            ledger=DecisionLedger(root / "runtime/phase_6_1/decision_ledger.jsonl"),
            neural_classifier=self.neural, root=root)
        for cycle_id in self.store.invalidate_noncausal():
            self.engine.ledger.append("phase6_1_evaluation_invalidation", {
                "cycle_id": cycle_id, "reason": "evaluation_preceded_candle_close",
                "excluded_from_dashboard_and_analysis": True, "orders_sent": False})
        ledger_rows = self.engine.ledger.records()
        if (any(row.get("record_type") == "phase6_1_four_policy_decision" for row in ledger_rows)
                and not any(row.get("record_type") == "phase6_1_expected_value_correction"
                            for row in ledger_rows)):
            self.engine.ledger.append("phase6_1_expected_value_correction", {
                "scope": "earlier_phase6_1_four_policy_decision_records",
                "correction": "expected_gross_bps_and_expected_net_bps_are_null_when_forecast_is_uncalibrated",
                "cost_bps_remains_observed_and_valid": True,
                "orders_sent": False})
        self._load_models()

    def _load_models(self) -> None:
        pointer = json.loads((self.root / "reports/phase_4/latest.json").read_text(encoding="utf-8"))
        results = json.loads((self.root / pointer["results"]).read_text(encoding="utf-8"))
        for horizon in (1, 5, 15, 30):
            item = results["horizons"][str(horizon)]
            selected = item["selected_for_shadow"]
            artifact = item["candidates"][selected]
            path = self.root / artifact["artifact"]
            if digest(path) != artifact["sha256"]:
                raise ValueError(f"phase4 model hash mismatch for {horizon}m")
            model = joblib.load(path)
            if not getattr(model, "columns", None) or not hasattr(model, "predict_proba"):
                raise ValueError(f"incompatible phase4 model for {horizon}m")
            self.models[horizon] = model
            self.model_versions[horizon] = f"{pointer['run_id']}:{horizon}m:{selected}"

    def on_event(self, record: dict) -> None:
        symbol = self._symbol(record)
        if symbol is None:
            return
        payload = record.get("payload", {})
        if "b" in payload and "a" in payload and (payload.get("e") == "bookTicker" or
                                                    record["stream"].endswith("@bookTicker")):
            self.quotes[symbol] = {"bid": float(payload["b"]), "ask": float(payload["a"]),
                                   "received_at": record["received_at"]}
            return
        if payload.get("e") == "depthUpdate":
            if record.get("local_book", {}).get("valid"):
                self.books[symbol] = record["local_book"] | {"received_at": record["received_at"]}
            return
        if payload.get("e") != "kline" or not payload.get("k", {}).get("x", False):
            return
        try:
            self.queue.put_nowait(record)
        except asyncio.QueueFull:
            self.dropped_events += 1

    async def warmup(self) -> None:
        self.warmup_attempts += 1
        self.last_warmup_attempt_at = datetime.now(UTC).isoformat()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            for symbol in UNIVERSE:
                async with session.get(f"{self.rest_base}/api/v3/klines",
                                       params={"symbol": symbol, "interval": "1m", "limit": 250}) as response:
                    response.raise_for_status()
                    frame = _rest_klines(await response.json())
                now = pd.Timestamp.now(tz="UTC")
                frame = frame[frame.close_time < now].tail(240).reset_index(drop=True)
                if len(frame) < 180 or frame.open_time.diff().dropna().ne(pd.Timedelta(minutes=1)).any():
                    raise ValueError(f"insufficient causal warmup for {symbol}")
                self.candles[symbol] = frame
                self.last_closed_open_time[symbol] = frame.open_time.iloc[-1]
                async with session.get(f"{self.rest_base}/api/v3/ticker/24hr",
                                       params={"symbol": symbol}) as response:
                    response.raise_for_status()
                    ticker = await response.json()
                self.quote_volume_24h[symbol] = float(ticker["quoteVolume"])

    @staticmethod
    def _symbol(record: dict) -> str | None:
        stream = str(record.get("stream", ""))
        symbol = stream.split("@", 1)[0].upper()
        return symbol if symbol in UNIVERSE else None

    def _update(self, record: dict) -> bool:
        symbol = self._symbol(record)
        if symbol is None:
            return False
        payload = record.get("payload", {})
        if "b" in payload and "a" in payload and (payload.get("e") == "bookTicker" or
                                                    record["stream"].endswith("@bookTicker")):
            self.quotes[symbol] = {"bid": float(payload["b"]), "ask": float(payload["a"]),
                                   "received_at": record["received_at"]}
        if payload.get("e") == "depthUpdate" and record.get("local_book", {}).get("valid"):
            self.books[symbol] = record["local_book"] | {"received_at": record["received_at"]}
        if payload.get("e") != "kline" or not payload.get("k", {}).get("x", False):
            return False
        candle = _stream_kline(payload)
        open_time = candle.open_time.iloc[0]
        current = self.candles[symbol]
        if not current.empty and open_time <= current.open_time.iloc[-1]:
            return False
        self.candles[symbol] = pd.concat([current, candle], ignore_index=True).tail(240).reset_index(drop=True)
        self.last_closed_open_time[symbol] = open_time
        return True

    async def _repair_gap(self, record: dict) -> bool:
        symbol = self._symbol(record)
        payload = record.get("payload", {})
        if symbol is None or payload.get("e") != "kline":
            return True
        incoming = pd.to_datetime(payload["k"]["t"], unit="ms", utc=True)
        current = self.candles[symbol]
        if current.empty:
            return True
        expected = current.open_time.iloc[-1] + pd.Timedelta(minutes=1)
        if incoming <= expected:
            return True
        missing = max(1, int((incoming - expected) / pd.Timedelta(minutes=1)))
        self.missing_candles_observed += missing
        params = {"symbol": symbol, "interval": "1m",
                  "startTime": int(expected.timestamp() * 1000),
                  "endTime": int(incoming.timestamp() * 1000) - 1, "limit": 1000}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get(f"{self.rest_base}/api/v3/klines", params=params) as response:
                    response.raise_for_status()
                    rows = await response.json()
        except Exception as exc:
            self.gap_repairs_failed += 1
            self.symbol_errors[symbol] = f"gap_repair_failed:{type(exc).__name__}"
            return False
        if not rows:
            self.gap_repairs_failed += 1
            self.symbol_errors[symbol] = "gap_repair_failed:empty_response"
            return False
        repair = _rest_klines(rows)
        now = pd.Timestamp.now(tz="UTC")
        repair = repair[(repair.close_time < now) & (repair.open_time < incoming)]
        if not repair.empty:
            self.candles[symbol] = pd.concat([current, repair], ignore_index=True).drop_duplicates(
                "open_time", keep="last").sort_values("open_time").tail(240).reset_index(drop=True)
            self.last_closed_open_time[symbol] = self.candles[symbol].open_time.iloc[-1]
        repaired_times = set(repair.open_time) if not repair.empty else set()
        required = set(pd.date_range(expected, incoming - pd.Timedelta(minutes=1), freq="1min"))
        if not required.issubset(repaired_times):
            self.gap_repairs_failed += 1
            self.symbol_errors[symbol] = "gap_repair_failed:incomplete_response"
            return False
        self.gap_repairs_succeeded += 1
        self.symbol_errors.pop(symbol, None)
        return True

    async def _wait_for_nominal_close(self, record: dict) -> None:
        payload = record.get("payload", {})
        if payload.get("e") != "kline" or not payload.get("k", {}).get("x", False):
            return
        close_at = datetime.fromtimestamp(float(payload["k"]["T"]) / 1000, UTC)
        delay = (close_at - datetime.now(UTC)).total_seconds()
        if delay > 2:
            raise ValueError("exchange candle close is too far in the future")
        if delay > 0:
            await asyncio.sleep(delay + .01)

    def _ready_cycle(self) -> pd.Timestamp | None:
        if set(self.last_closed_open_time) != set(UNIVERSE):
            return None
        values = set(self.last_closed_open_time.values())
        if len(values) != 1:
            return None
        instant = next(iter(values))
        return instant if self.last_cycle_open_time is None or instant > self.last_cycle_open_time else None

    def _forecast_btc(self) -> tuple[dict, tuple[str, ...]]:
        recent = self.candles["BTCUSDT"].tail(max(61, max(SPECS[name].lookback for name in SPECS)))
        if (len(recent) < 61 or
                recent.open_time.diff().dropna().ne(pd.Timedelta(minutes=1)).any()):
            return {"state": "unavailable", "reason": "candle_continuity_not_recovered"}, (
                "forecast_unavailable_after_market_gap",)
        frame = make_features(self.candles["BTCUSDT"])
        row = frame.iloc[[-1]]
        if row[list(SPECS)].isna().any(axis=None) or not np.isfinite(row[list(SPECS)].to_numpy()).all():
            return {"state": "unavailable", "reason": "non_finite_features"}, ("forecast_unavailable",)
        horizons = {}
        primary_signal = "unavailable"
        for horizon, model in self.models.items():
            probability = np.asarray(model.predict_proba(row)[0], dtype=float)
            signal = int(decisions(probability[None, :], self.threshold, self.payout)[0])
            label = {-1: "abstain", 0: "down", 2: "up"}[signal]
            horizons[str(horizon)] = {
                "model_version": self.model_versions[horizon],
                "probabilities": {"down": float(probability[0]), "tie": float(probability[1]),
                                  "up": float(probability[2])},
                "signal": label, "threshold": self.threshold,
            }
            if horizon == 1:
                primary_signal = label
        reason = ("expected_gross_return_not_live_calibrated",) if primary_signal == "up" else (
            "quantitative_threshold_abstention",) if primary_signal == "abstain" else (
            "quantitative_signal_not_long",)
        return {"state": "ready", "asset_scope": "BTCUSDT_only", "primary_horizon_minutes": 1,
                "primary_signal": primary_signal, "horizons": horizons,
                "expected_gross_return_bps": None}, reason

    def _build_cycle(self, open_time: pd.Timestamp) -> tuple[list[MarketSnapshot], dict, dict, dict]:
        as_of = datetime.now(UTC)
        forecasts: dict[str, dict] = {}
        reasons: dict[str, tuple[str, ...]] = {}
        snapshots = []
        market = {}
        btc_forecast, btc_reasons = self._forecast_btc()
        for symbol in UNIVERSE:
            quote = self.quotes.get(symbol, {})
            book = self.books.get(symbol, {})
            candles = self.candles[symbol]
            candle = candles.iloc[-1]
            forecast = btc_forecast if symbol == "BTCUSDT" else {
                "state": "unavailable", "reason": "frozen_model_scope_is_btc_only",
                "expected_gross_return_bps": None}
            technical = btc_reasons if symbol == "BTCUSDT" else ("model_scope_unavailable_for_asset",)
            quote_time = datetime.fromisoformat(quote["received_at"]) if quote.get("received_at") else None
            stale = (as_of - quote_time).total_seconds() if quote_time else math.inf
            complete = bool(quote and book.get("valid") and symbol in self.quote_volume_24h and stale <= 5)
            bid, ask = float(quote.get("bid", 0)), float(quote.get("ask", 0))
            if not quote:
                bid = ask = float(candle.close)
                technical += ("live_quote_unavailable",)
            returns = np.log(candles.close.astype(float)).diff().tail(20)
            volatility = float(returns.std() * 10_000) if returns.notna().any() else 0.0
            snapshots.append(MarketSnapshot(
                symbol=symbol, observed_at=as_of, bid=bid, ask=ask,
                quote_volume_24h=float(self.quote_volume_24h.get(symbol, 0)),
                bid_depth_quote=float(book.get("bid_depth_quote", 0)),
                ask_depth_quote=float(book.get("ask_depth_quote", 0)),
                volatility_bps=volatility, expected_gross_return_bps=0.0,
                signal_confidence=(max(btc_forecast.get("horizons", {}).get("1", {})
                                       .get("probabilities", {"none": 0}).values())
                                   if symbol == "BTCUSDT" else 0.0),
                data_complete=complete, stale_seconds=max(0.0, stale) if math.isfinite(stale) else 1e9))
            forecasts[symbol] = forecast
            reasons[symbol] = tuple(dict.fromkeys(technical))
            market[symbol] = {
                "candle_open_time": open_time.isoformat(),
                "candle_close_time": pd.Timestamp(candle.close_time).isoformat(),
                "close": float(candle.close), "bid": bid if quote else None,
                "ask": ask if quote else None, "spread_bps": book.get("spread_bps"),
                "bid_depth_quote": book.get("bid_depth_quote"),
                "ask_depth_quote": book.get("ask_depth_quote"),
                "quote_volume_24h": self.quote_volume_24h.get(symbol),
                "data_complete": complete, "stale_seconds": stale if math.isfinite(stale) else None,
                "closed_candle": True,
            }
        return snapshots, forecasts, reasons, market

    def _evaluate_cycle(self, open_time: pd.Timestamp) -> None:
        snapshots, forecasts, reasons, market = self._build_cycle(open_time)
        as_of = datetime.now(UTC)
        result = self.engine.evaluate(snapshots, as_of=as_of, forecasts=forecasts,
                                      technical_reasons=reasons)
        cycle_id = hashlib.sha256(f"{open_time.isoformat()}:phase6.1".encode()).hexdigest()
        self.evaluations_recorded += self.store.add_cycle(cycle_id, result, market)
        self.cycles_completed += 1
        self.last_evaluation_at = result["as_of"]
        self.last_cycle_open_time = open_time
        self.store.resolve_outcomes(self.candles["BTCUSDT"])
        self.state = "abstaining" if all(
            block["selected"] is None for block in result["policies"].values()) else "signal_ready"

    async def run(self) -> None:
        self.started_at = datetime.now(UTC).isoformat()
        self.state = "warming_up"
        try:
            await self.warmup()
            self.state = "waiting_for_closed_candles"
        except Exception as exc:
            self.warmup_failures += 1
            self.last_error = f"warmup_failed:{type(exc).__name__}"
            self.state = "unavailable"
        next_warmup_retry = asyncio.get_running_loop().time() + 60
        while not self._stop.is_set():
            try:
                record = await asyncio.wait_for(self.queue.get(), timeout=1)
            except asyncio.TimeoutError:
                if (len(self.last_closed_open_time) < len(UNIVERSE) and
                        asyncio.get_running_loop().time() >= next_warmup_retry):
                    self.state = "recovering_warmup"
                    try:
                        await asyncio.wait_for(self.warmup(), timeout=35)
                        self.state = "waiting_for_closed_candles"
                        self.last_error = None
                    except Exception as exc:
                        self.warmup_failures += 1
                        self.last_error = f"warmup_retry_failed:{type(exc).__name__}"
                        self.state = "unavailable"
                    next_warmup_retry = asyncio.get_running_loop().time() + 60
                continue
            if record is None:
                break
            try:
                await self._wait_for_nominal_close(record)
                repaired = await self._repair_gap(record)
                closed = self._update(record)
                instant = self._ready_cycle() if closed else None
                if instant is not None:
                    self.state = "analyzing"
                    await asyncio.to_thread(self._evaluate_cycle, instant)
                    if not repaired:
                        self.state = "degraded"
            except Exception as exc:
                self.last_error = f"evaluation_failed:{type(exc).__name__}:{exc}"
                self.state = "degraded"

    def status(self) -> dict:
        return {"state": self.state, "started_at": self.started_at,
                "last_evaluation_at": self.last_evaluation_at,
                "last_error": self.last_error, "cycles_completed": self.cycles_completed,
                "evaluations_recorded": self.store.count(), "queue_size": self.queue.qsize(),
                "dropped_events": self.dropped_events,
                "gap_repairs_succeeded": self.gap_repairs_succeeded,
                "gap_repairs_failed": self.gap_repairs_failed,
                "missing_candles_observed": self.missing_candles_observed,
                "symbol_errors": dict(self.symbol_errors),
                "warmup_attempts": self.warmup_attempts,
                "warmup_failures": self.warmup_failures,
                "last_warmup_attempt_at": self.last_warmup_attempt_at,
                "symbols": {symbol: {"warmup_candles": len(self.candles[symbol]),
                                      "last_closed_open_time": (self.last_closed_open_time[symbol].isoformat()
                                                                if symbol in self.last_closed_open_time else None),
                                      "quote_available": symbol in self.quotes,
                                      "depth_available": symbol in self.books}
                            for symbol in UNIVERSE},
                "qwen3": self.neural.status(), "orders_sent": False}

    def stop(self) -> None:
        self._stop.set()
        try:
            self.queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
