"""Phase 6.4 prospective validation and supervised Binance Demo execution.

Nothing in this module sends an order on import.  The autonomous engine is
fail-closed and requires a short-lived authorization bound to its current
process boot identifier.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import sqlite3
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiohttp
import numpy as np

from .common import ROOT, digest, save_json
from .phase6_2 import (KILL_SWITCH_CONFIRMATION, PersistentKillSwitch,
                       SymbolRules, build_demo_service)
from .phase6_trading import (BinanceDemoAPIError, DecisionLedger, MarketSnapshot,
                             Opportunity, RiskLimits, RiskManager)
from .unified_intelligence import UnifiedDecisionStore, frozen_entry_reasons, timestamp


UTC = timezone.utc
PHASE64_CONFIG = Path("configs/phase_6_4.json")
TERMINAL_ORDER_STATES = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}


def iso_now() -> str:
    return datetime.now(UTC).isoformat()


def load_phase64_config(root: Path = ROOT) -> dict:
    config = json.loads((root / PHASE64_CONFIG).read_text(encoding="utf-8"))
    if config.get("environment") != "DEMO" or config.get("default_mode") != "OBSERVE":
        raise ValueError("Phase 6.4 must start in DEMO/OBSERVE")
    endpoints = config.get("endpoints", {})
    if endpoints != {
        "rest": "https://demo-api.binance.com/api",
        "rest_root": "https://demo-api.binance.com",
        "websocket_api": "wss://demo-ws-api.binance.com/ws-api/v3",
        "market_stream": "wss://demo-stream.binance.com",
    }:
        raise ValueError("Phase 6.4 endpoints are outside the Binance Demo allowlist")
    if config.get("real_trading_supported") or config.get("automatic_promotion"):
        raise ValueError("real trading and automatic promotion are forbidden")
    if config["observation"]["required_seconds"] < 86_400:
        raise ValueError("prospective observation must last at least 24 hours")
    demo = config["experimental_demo"]
    if demo["symbol"] != "BTCUSDT" or demo["policy"] != "A_quantitative":
        raise ValueError("only the frozen BTC quantitative policy may be experimental")
    if Decimal(str(demo["quote_amount"])) != Decimal("10"):
        raise ValueError("initial experimental notional must be exactly 10 USDT")
    if demo["orders_enabled_by_default"]:
        raise ValueError("Demo orders must be disabled by default")
    return config


class ObservationStore:
    """Append-only samples for a resumable minimum-24-hour protocol."""
    def __init__(self, path: Path, config: dict):
        self.path = path
        self.config = config
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS observation_sessions(
                    session_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
                    required_seconds INTEGER NOT NULL, state TEXT NOT NULL,
                    initial_evaluations INTEGER NOT NULL, completed_at TEXT,
                    config_sha256 TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observation_samples(
                    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL, sampled_at TEXT NOT NULL,
                    elapsed_seconds REAL NOT NULL, worker_state TEXT NOT NULL,
                    valid_evaluations INTEGER NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_observation_samples_session
                    ON observation_samples(session_id, sampled_at);
            """)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def active_or_create(self, initial_evaluations: int) -> str:
        with self._connect() as db:
            row = db.execute("""SELECT session_id FROM observation_sessions
                                WHERE state='in_progress' ORDER BY started_at DESC LIMIT 1""").fetchone()
            if row:
                return str(row[0])
            session_id = f"obs-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
            db.execute("INSERT INTO observation_sessions VALUES (?,?,?,?,?,?,?)",
                       (session_id, iso_now(), self.config["observation"]["required_seconds"],
                        "in_progress", initial_evaluations, None,
                        digest(self.path.parents[2] / PHASE64_CONFIG)))
            return session_id

    def add_sample(self, session_id: str, payload: dict) -> None:
        with self._connect() as db:
            session = db.execute("SELECT started_at,required_seconds,state FROM observation_sessions "
                                 "WHERE session_id=?", (session_id,)).fetchone()
            if session is None:
                raise KeyError("observation session not found")
            now = datetime.now(UTC)
            elapsed = max(0.0, (now - datetime.fromisoformat(session[0])).total_seconds())
            db.execute("""INSERT INTO observation_samples(
                            session_id,sampled_at,elapsed_seconds,worker_state,
                            valid_evaluations,payload_json) VALUES (?,?,?,?,?,?)""",
                       (session_id, now.isoformat(), elapsed,
                        payload.get("decision_worker", {}).get("state", "unknown"),
                        int(payload.get("decision_worker", {}).get("evaluations_recorded", 0)),
                        json.dumps(payload, separators=(",", ":"), ensure_ascii=False)))
            if session[2] == "in_progress" and elapsed >= int(session[1]):
                db.execute("UPDATE observation_sessions SET state='completed',completed_at=? "
                           "WHERE session_id=?", (now.isoformat(), session_id))

    def status(self, session_id: str | None = None) -> dict:
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            if session_id is None:
                session = db.execute("SELECT * FROM observation_sessions ORDER BY started_at DESC LIMIT 1").fetchone()
            else:
                session = db.execute("SELECT * FROM observation_sessions WHERE session_id=?",
                                     (session_id,)).fetchone()
            if session is None:
                return {"state": "not_started", "minimum_24h_completed": False}
            samples = db.execute("SELECT * FROM observation_samples WHERE session_id=? ORDER BY sampled_at",
                                 (session["session_id"],)).fetchall()
        now = datetime.now(UTC)
        start = datetime.fromisoformat(session["started_at"])
        elapsed = max(0.0, (now - start).total_seconds())
        timestamps = [datetime.fromisoformat(row["sampled_at"]) for row in samples]
        gaps = [(b - a).total_seconds() for a, b in zip(timestamps, timestamps[1:])]
        expected_gap = self.config["observation"]["maximum_expected_sample_gap_seconds"]
        payloads = [json.loads(row["payload_json"]) for row in samples]
        collector_keys = ("reconnections", "aggtrade_gap_events", "aggtrade_missing_ids",
                          "depth_invalidations", "messages")
        collector_totals = {key: 0 for key in collector_keys}
        previous_by_symbol: dict[str, dict] = {}
        for payload in payloads:
            for symbol, item in payload.get("collectors", {}).items():
                previous = previous_by_symbol.get(symbol, {})
                for key in collector_keys:
                    value = int(item.get(key, 0) or 0)
                    prior = int(previous.get(key, 0) or 0)
                    collector_totals[key] += value if value < prior else value - prior
                previous_by_symbol[symbol] = item
        workers_available = sum(row["worker_state"] not in {"unavailable", "not_running", "unknown"}
                                for row in samples)
        qwen_available = sum(p.get("decision_worker", {}).get("qwen3", {}).get("state")
                             in {"ready", "available_not_loaded"} for p in payloads)
        demo_available = sum(p.get("demo_public", {}).get("available", False) for p in payloads)
        demo_latencies = [float(p["demo_public"]["latency_ms"]) for p in payloads
                          if p.get("demo_public", {}).get("available") and
                          p["demo_public"].get("latency_ms") is not None]
        cpu = [float(p["resources"]["cpu_percent"]) for p in payloads
               if p.get("resources", {}).get("cpu_percent") is not None]
        memory = [int(p["resources"]["memory_rss_bytes"]) for p in payloads
                  if p.get("resources", {}).get("memory_rss_bytes") is not None]
        initial = int(session["initial_evaluations"])
        final_evaluations = int(samples[-1]["valid_evaluations"]) if samples else initial
        complete = session["state"] == "completed" and elapsed >= int(session["required_seconds"])
        problems = []
        if any(gap > expected_gap for gap in gaps):
            problems.append("heartbeat_gap_above_expected_interval")
        if any(row["worker_state"] in {"unavailable", "degraded"} for row in samples):
            problems.append("decision_worker_degradation_observed")
        if any(not p.get("demo_public", {}).get("available", False) for p in payloads):
            problems.append("binance_demo_public_failure_observed")
        # Keep the original whole-protocol evidence while exposing recovery
        # separately. A historical failure must never disappear from the audit.
        recent_payloads = [p for p in payloads if p.get("sampled_at") and
                           datetime.fromisoformat(p["sampled_at"]) >= now - timedelta(hours=1)]
        current_pid = payloads[-1].get("pid") if payloads else None
        current_payloads = []
        for payload in reversed(payloads):
            if payload.get("pid") != current_pid:
                break
            current_payloads.append(payload)
        current_payloads.reverse()

        def availability_window(items: list[dict]) -> dict:
            ready_states = {"waiting_for_closed_candles", "abstaining", "signal_ready", "analyzing"}
            count = len(items)
            return {
                "first_sample_at": items[0].get("sampled_at") if items else None,
                "last_sample_at": items[-1].get("sampled_at") if items else None,
                "samples": count,
                "worker_availability_fraction": (sum(p.get("decision_worker", {}).get("state")
                                                     in ready_states for p in items) / count if count else None),
                "demo_public_availability_fraction": (sum(bool(p.get("demo_public", {}).get("available"))
                                                          for p in items) / count if count else None),
                "latest_collectors": items[-1].get("collectors", {}) if items else {},
                "latest_engine": items[-1].get("autonomous_engine", {}) if items else {},
                "basis": "sampled availability; whole-protocol failures remain preserved",
            }
        policy_counts: dict[str, int] = {}
        symbol_counts: dict[str, int] = {}
        abstentions = temporal_violations = 0
        evaluations_path = self.path.parents[2] / "runtime/phase_6_1/evaluations.sqlite3"
        if evaluations_path.exists():
            uri = f"file:{evaluations_path.resolve().as_posix()}?mode=ro"
            with sqlite3.connect(uri, uri=True) as evaluations:
                policy_counts = dict(evaluations.execute(
                    "SELECT policy,COUNT(*) FROM evaluations WHERE causal_valid=1 AND evaluated_at>=? GROUP BY policy",
                    (session["started_at"],)).fetchall())
                symbol_counts = dict(evaluations.execute(
                    "SELECT symbol,COUNT(*) FROM evaluations WHERE causal_valid=1 AND evaluated_at>=? GROUP BY symbol",
                    (session["started_at"],)).fetchall())
                abstentions = int(evaluations.execute(
                    "SELECT COUNT(*) FROM evaluations WHERE causal_valid=1 AND evaluated_at>=? AND decision='abstain'",
                    (session["started_at"],)).fetchone()[0])
                temporal_violations = int(evaluations.execute(
                    "SELECT COUNT(*) FROM evaluations WHERE evaluated_at>=? AND causal_valid=0",
                    (session["started_at"],)).fetchone()[0])
        return {
            "session_id": session["session_id"], "state": session["state"],
            "started_at": session["started_at"], "completed_at": session["completed_at"],
            "required_seconds": int(session["required_seconds"]), "elapsed_seconds": elapsed,
            "remaining_seconds": max(0.0, int(session["required_seconds"]) - elapsed),
            "minimum_24h_completed": complete, "samples": len(samples),
            "maximum_sample_gap_seconds": max(gaps) if gaps else None,
            "sample_gaps_above_expected": sum(gap > expected_gap for gap in gaps),
            "worker_availability_fraction": workers_available / len(samples) if samples else None,
            "qwen_availability_fraction": qwen_available / len(samples) if samples else None,
            "binance_demo_public_availability_fraction": demo_available / len(samples) if samples else None,
            "binance_demo_latency_ms_p95": (float(np.quantile(demo_latencies, .95))
                                             if demo_latencies else None),
            "resource_usage": {"cpu_percent_mean": float(np.mean(cpu)) if cpu else None,
                               "cpu_percent_max": max(cpu) if cpu else None,
                               "memory_rss_bytes_mean": float(np.mean(memory)) if memory else None,
                               "memory_rss_bytes_max": max(memory) if memory else None},
            "valid_evaluations_added": max(0, final_evaluations - initial),
            "evaluations_by_policy": policy_counts, "evaluations_by_symbol": symbol_counts,
            "abstentions_recorded": abstentions,
            "temporal_integrity_violations": temporal_violations,
            "collector_totals": collector_totals, "problems": sorted(set(problems)),
            "recent_60m": availability_window(recent_payloads),
            "current_process": {"pid": current_pid, **availability_window(current_payloads)},
            "claim": ("minimum elapsed time completed; inspect availability and problems"
                      if complete else "24-hour validation is still in progress"),
        }


class ObservationMonitor:
    def __init__(self, *, root: Path, decision_worker, market_service,
                 sample_seconds: float | None = None, autonomous_engine=None):
        self.root = root
        self.config = load_phase64_config(root)
        self.worker = decision_worker
        self.market = market_service
        self.autonomous_engine = autonomous_engine
        self.sample_seconds = sample_seconds or self.config["observation"]["sample_seconds"]
        self.store = ObservationStore(root / "runtime/phase_6_4/observation.sqlite3", self.config)
        self.session_id: str | None = None
        self._resource_process = None
        self._stop = asyncio.Event()

    async def _demo_public_health(self) -> dict:
        started = asyncio.get_running_loop().time()
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.config["endpoints"]["rest"] + "/v3/ping") as response:
                    response.raise_for_status()
                    await response.json()
            return {"available": True,
                    "latency_ms": (asyncio.get_running_loop().time() - started) * 1000,
                    "error": None}
        except Exception as exc:
            return {"available": False,
                    "latency_ms": (asyncio.get_running_loop().time() - started) * 1000,
                    "error": type(exc).__name__}

    def _resources(self) -> dict:
        try:
            import psutil
            if self._resource_process is None:
                self._resource_process = psutil.Process(os.getpid())
                self._resource_process.cpu_percent(interval=None)
                return {"cpu_percent": None, "memory_rss_bytes": self._resource_process.memory_info().rss,
                        "reason": "first_cpu_sample_requires_previous_observation"}
            process = self._resource_process
            return {"cpu_percent": process.cpu_percent(interval=None),
                    "memory_rss_bytes": process.memory_info().rss}
        except Exception as exc:
            return {"cpu_percent": None, "memory_rss_bytes": None,
                    "error": type(exc).__name__}

    async def run(self) -> None:
        self.session_id = self.store.active_or_create(self.worker.store.count())
        while not self._stop.is_set():
            payload = {"sampled_at": iso_now(), "pid": os.getpid(),
                       "decision_worker": self.worker.status(),
                       "autonomous_engine": (self.autonomous_engine.reconciliation
                                             if self.autonomous_engine is not None else {}),
                       "collectors": self.market.status(), "resources": self._resources(),
                       "demo_public": await self._demo_public_health()}
            await asyncio.to_thread(self.store.add_sample, self.session_id, payload)
            save_json(self.root / "reports/phase_6_4/observation_status.json",
                      self.store.status(self.session_id))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.sample_seconds)
            except asyncio.TimeoutError:
                pass

    def status(self) -> dict:
        return self.store.status(self.session_id)

    def stop(self) -> None:
        self._stop.set()


def _mean_ci(values: list[float], *, seed: int, samples: int) -> list[float] | None:
    if len(values) < 2:
        return None
    rng = np.random.default_rng(seed)
    data = np.asarray(values, dtype=float)
    chunks = []
    for start in range(0, samples, 50):
        width = min(50, samples - start)
        chunks.append(rng.choice(data, size=(width, len(data)), replace=True).mean(axis=1))
    means = np.concatenate(chunks)
    low, high = np.quantile(means, [.025, .975])
    return [float(low), float(high)]


def economic_report(root: Path = ROOT) -> dict:
    """Evaluate resolved prospective outcomes without fitting or tuning anything."""
    config = load_phase64_config(root)
    database = root / "runtime/phase_6_1/evaluations.sqlite3"
    rows: list[sqlite3.Row] = []
    if database.exists():
        uri = f"file:{database.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            db.row_factory = sqlite3.Row
            try:
                rows = db.execute("SELECT * FROM forecast_outcomes WHERE status='resolved' "
                                  "ORDER BY decision_at,horizon_minutes").fetchall()
                pending = db.execute("SELECT COUNT(*) FROM forecast_outcomes WHERE status='pending'").fetchone()[0]
                invalid = db.execute("SELECT COUNT(*) FROM forecast_outcomes WHERE status='invalid'").fetchone()[0]
            except sqlite3.OperationalError:
                rows, pending, invalid = [], 0, 0
    else:
        pending = invalid = 0
    settings = config["economic_validation"]
    horizons = {}
    for horizon in (1, 5, 15, 30):
        selected = [row for row in rows if row["horizon_minutes"] == horizon]
        probs = np.asarray([[row["p_down"], row["p_tie"], row["p_up"]] for row in selected])
        gross = [float(row["gross_return_bps"]) for row in selected]
        net_known = [float(row["net_return_bps"]) for row in selected if row["net_return_bps"] is not None]
        labels = np.asarray([0 if value < 0 else 2 if value > 0 else 1 for value in gross], dtype=int)
        predicted = probs.argmax(axis=1) if len(selected) else np.asarray([], dtype=int)
        log_loss = None
        brier = None
        ece = None
        if len(selected):
            chosen = np.clip(probs[np.arange(len(labels)), labels], 1e-15, 1)
            log_loss = float(-np.log(chosen).mean())
            onehot = np.eye(3)[labels]
            brier = float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))
            confidence = probs.max(axis=1)
            correctness = (predicted == labels).astype(float)
            ece_value = 0.0
            for low in np.linspace(0, 1, 11)[:-1]:
                mask = (confidence >= low) & (confidence < low + .1 if low < .9 else confidence <= 1)
                if mask.any():
                    ece_value += float(mask.mean() * abs(correctness[mask].mean() - confidence[mask].mean()))
            ece = ece_value
        entries = [row for row in selected if row["signal"] in {"up", "down"}]
        long_net = [float(row["net_return_bps"]) for row in selected
                    if row["signal"] == "up" and row["net_return_bps"] is not None]
        horizons[str(horizon)] = {
            "resolved_observations": len(selected),
            "directional_accuracy": float((predicted == labels).mean()) if len(selected) else None,
            "multiclass_log_loss": log_loss, "multiclass_brier": brier,
            "expected_calibration_error": ece,
            "mean_gross_return_bps": float(np.mean(gross)) if gross else None,
            "mean_net_return_bps_all_observations": float(np.mean(net_known)) if net_known else None,
            "mean_net_return_bps_long_signals": float(np.mean(long_net)) if long_net else None,
            "mean_net_return_bps_long_signals_ci95": _mean_ci(
                long_net, seed=settings["bootstrap_seed"] + horizon,
                samples=settings["bootstrap_samples"]),
            "economically_eligible_signal_frequency": len(entries) / len(selected) if selected else None,
            "abstention_rate": 1 - len(entries) / len(selected) if selected else None,
            "baselines": {
                "always_abstain_net_bps": 0.0,
                "long_every_observation_mean_net_bps": float(np.mean(net_known)) if net_known else None,
                "pre_registered_momentum": None,
                "pre_registered_mean_reversion": None,
                "unavailable_reason": "no causal baseline signal was pre-registered for these live instants",
            },
        }
    decision_times = [datetime.fromisoformat(row["decision_at"]) for row in rows]
    elapsed_days = ((max(decision_times) - min(decision_times)).total_seconds() / 86400
                    if len(decision_times) >= 2 else 0.0)
    five = horizons["5"]
    ci = five["mean_net_return_bps_long_signals_ci95"]
    enough = (five["resolved_observations"] >= settings["minimum_resolved_opportunities"] and
              elapsed_days >= settings["minimum_elapsed_days"])
    economically_validated = bool(enough and ci and ci[0] > 0)
    result = {
        "generated_at": iso_now(), "source": settings["source"],
        "training_performed": False, "calibration_parameters_fitted": False,
        "strategy_selection_performed": False,
        "reserved_2026_07_to_09_holdout_consumed": False,
        "resolved_outcomes": len(rows), "pending_outcomes": int(pending),
        "invalid_outcomes": int(invalid), "elapsed_prospective_days": elapsed_days,
        "horizons": horizons, "economically_validated": economically_validated,
        "category_ECONOMICALLY_VALIDATED_available": economically_validated,
        "category_EXPERIMENTAL_DEMO_available_for_authorized_sessions": True,
        "limitations": [
            "Results are prospective estimates and do not prove profitability.",
            "Costs use the decision-time estimate until actual Demo fills exist.",
            "Unknown expected financial values remain null in the decision ledger.",
        ],
    }
    save_json(root / "reports/phase_6_4/economic_status.json", result)
    return result


class AutonomousStore:
    """Persistent session, position and activity state for Demo-only experiments."""
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions(
                    session_id TEXT PRIMARY KEY, boot_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, authorized_at TEXT, expires_at TEXT,
                    state TEXT NOT NULL, policy TEXT NOT NULL, symbol TEXT NOT NULL,
                    quote_amount TEXT NOT NULL, confirmation_hash TEXT,
                    entries INTEGER NOT NULL DEFAULT 0, stop_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS positions(
                    position_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    symbol TEXT NOT NULL, policy TEXT NOT NULL, state TEXT NOT NULL,
                    evaluation_id TEXT NOT NULL, opened_at TEXT, planned_close_at TEXT,
                    closed_at TEXT, quantity TEXT, entry_quote TEXT, exit_quote TEXT,
                    entry_price TEXT, exit_price TEXT, fees_json TEXT NOT NULL,
                    net_quote TEXT, entry_client_id TEXT, exit_client_id TEXT,
                    close_reason TEXT, payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activity(
                    activity_id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL,
                    session_id TEXT, event_type TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consumed_evaluations(
                    evaluation_id TEXT PRIMARY KEY, consumed_at TEXT NOT NULL, outcome TEXT NOT NULL
                );
            """)

    def activity(self, event_type: str, payload: dict, session_id: str | None = None) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO activity(recorded_at,session_id,event_type,payload_json) VALUES(?,?,?,?)",
                       (iso_now(), session_id, event_type,
                        json.dumps(payload, separators=(",", ":"), ensure_ascii=False)))

    def active_session(self) -> dict | None:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM sessions WHERE state IN ('prepared','authorized','running') "
                             "ORDER BY created_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def open_position(self) -> dict | None:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM positions WHERE state IN "
                             "('PREPARED','ENTRY_SUBMITTING','OPEN','EXIT_SUBMITTING','RECOVERY_REQUIRED') "
                             "ORDER BY rowid DESC LIMIT 1").fetchone()
        if not row:
            return None
        result = dict(row)
        result["fees"] = json.loads(result.pop("fees_json"))
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def status(self) -> dict:
        session = self.active_session()
        position = self.open_position()
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            recent = [dict(row) for row in db.execute(
                "SELECT activity_id,recorded_at,session_id,event_type,payload_json FROM activity "
                "ORDER BY activity_id DESC LIMIT 100").fetchall()]
            closed = [dict(row) for row in db.execute(
                "SELECT * FROM positions WHERE state='CLOSED' ORDER BY closed_at DESC LIMIT 100").fetchall()]
        for row in recent:
            row["payload"] = json.loads(row.pop("payload_json"))
        return {"session": session, "open_position": position, "recent_activity": recent,
                "closed_positions": closed}


class SupervisedDemoEngine:
    """One-policy Demo executor; remains inert until per-boot authorization."""
    def __init__(self, root: Path = ROOT, *, service_factory=build_demo_service,
                 market_status=None):
        self.root = root
        self.config = load_phase64_config(root)
        self.demo = self.config["experimental_demo"]
        self.store = AutonomousStore(root / "runtime/phase_6_4/autonomous.sqlite3")
        self.ledger = DecisionLedger(root / "runtime/phase_6_4/autonomous_ledger.jsonl")
        self.kill = PersistentKillSwitch(root / "runtime/phase_6_2/kill_switch.json")
        self.service_factory = service_factory
        self._cached_service = None
        self.market_status = market_status
        self.boot_id = uuid.uuid4().hex
        self.state = "OBSERVE"
        self.last_error: str | None = None
        self._reconciled = False
        self._last_reconcile_monotonic = 0.0
        self._next_reconcile_monotonic = 0.0
        self._reconcile_failures = 0
        self._reconciliation_blocked = False
        self._clock_offset_ms = 0
        self.reconciliation = {
            "state": "pending", "last_attempt_at": None, "last_success_at": None,
            "failure_count": 0, "transient": None, "category": None,
            "next_retry_at": None, "error": None,
        }
        self._stop = asyncio.Event()
        self.control_path = root / "runtime/phase_6_4/engine.json"

    def _service(self):
        if self._cached_service is None:
            self._cached_service = self.service_factory(self.root)
        service = self._cached_service
        # Reuse the latest read-only clock synchronization for every broker
        # instance, including position monitoring and exits.
        service.broker.clock_ms = lambda: int(datetime.now(UTC).timestamp() * 1000) + self._clock_offset_ms
        return service

    def _write_control(self) -> None:
        orders_enabled = (self.state == "AUTHORIZED_DEMO" and
                          not self.kill.status()["engaged"] and
                          self.reconciliation.get("state") == "healthy")
        save_json(self.control_path, {"boot_id": self.boot_id, "pid": os.getpid(),
                  "state": self.state, "last_error": self.last_error,
                  "updated_at": iso_now(), "orders_enabled": orders_enabled,
                  "reconciliation": self.reconciliation,
                  "environment": "DEMO", "real_trading_supported": False})

    def _authorization(self) -> dict | None:
        session = self.store.active_session()
        if not session or session["state"] not in {"authorized", "running"}:
            return None
        if session["boot_id"] != self.boot_id:
            self.store.activity("authorization_rejected_boot_mismatch", {}, session["session_id"])
            self._stop_session(session["session_id"], "engine_restarted_authorization_invalidated")
            return None
        if not session["expires_at"] or datetime.fromisoformat(session["expires_at"]) <= datetime.now(UTC):
            self._stop_session(session["session_id"], "authorization_expired")
            return None
        return session

    def _stop_session(self, session_id: str, reason: str) -> None:
        with sqlite3.connect(self.store.path) as db:
            db.execute("UPDATE sessions SET state='stopped',stop_reason=? WHERE session_id=?",
                       (reason, session_id))
        self.kill.engage(reason)
        self.store.activity("session_stopped", {"reason": reason}, session_id)
        self.state = "OBSERVE"

    def _latest_candidate(self) -> dict | None:
        path = self.root / "runtime/phase_6_1/evaluations.sqlite3"
        decisions = UnifiedDecisionStore.recent(path, limit=1, symbol=self.demo["symbol"])
        if not decisions:
            return None  # Historical research evaluations cannot authorize orders.
        unified = decisions[0]
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("""SELECT evaluation_id,evaluated_at,prediction_json,market_json
                                FROM evaluations WHERE causal_valid=1 AND symbol='BTCUSDT'
                                AND policy='A_quantitative' AND evaluation_id=?""",
                             (unified["evaluation_id"],)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["prediction"] = json.loads(result.pop("prediction_json"))
        result["market"] = json.loads(result.pop("market_json"))
        result["unified"] = unified
        return result

    def _gate(self, session: dict, candidate: dict | None) -> tuple[bool, list[str]]:
        reasons = []
        reasons.extend(self._market_entry_reasons())
        if self.kill.status()["engaged"]:
            reasons.append("kill_switch_engaged")
        if self.store.open_position() is not None:
            reasons.append("position_already_open")
        if session["entries"] >= self.demo["maximum_entries_per_session"]:
            reasons.append("session_entry_limit")
        if candidate is None:
            reasons.append("no_quantitative_evaluation")
            return False, reasons
        age = (datetime.now(UTC) - datetime.fromisoformat(candidate["evaluated_at"])).total_seconds()
        if not 0 <= age <= self.demo["maximum_signal_age_seconds"]:
            reasons.append("signal_stale")
        unified = candidate.get("unified") or {}
        current_policy_version = f"{self.config['protocol_version']}:{digest(self.root / PHASE64_CONFIG)}"
        if unified.get("policy_version") != current_policy_version:
            reasons.append("unified_policy_version_mismatch")
        if unified.get("decision") != "COMPRAR":
            reasons.append("unified_proposal_not_eligible")
        reasons.extend(frozen_entry_reasons(candidate["prediction"], candidate["market"], self.demo))
        try:
            if timestamp(unified["valid_until"]) <= datetime.now(UTC):
                reasons.append("unified_proposal_expired")
        except (KeyError, TypeError, ValueError):
            reasons.append("unified_proposal_invalid")
        with sqlite3.connect(self.store.path) as db:
            consumed = db.execute("SELECT 1 FROM consumed_evaluations WHERE evaluation_id=?",
                                  (candidate["evaluation_id"],)).fetchone()
            today = datetime.now(UTC).date().isoformat()
            daily = db.execute("SELECT COUNT(*) FROM positions WHERE opened_at LIKE ?", (today + "%",)).fetchone()[0]
            pnl = db.execute("SELECT COALESCE(SUM(CAST(net_quote AS REAL)),0) FROM positions "
                             "WHERE state='CLOSED' AND closed_at LIKE ?", (today + "%",)).fetchone()[0]
            last_closed = db.execute("SELECT closed_at FROM positions WHERE state='CLOSED' "
                                     "ORDER BY closed_at DESC LIMIT 1").fetchone()
        if consumed:
            reasons.append("evaluation_already_consumed")
        if daily >= self.demo["maximum_entries_per_day"]:
            reasons.append("daily_entry_limit")
        if float(pnl) <= -float(self.demo["maximum_daily_loss_quote"]):
            reasons.append("daily_loss_limit")
        risk = RiskManager(RiskLimits(
            maximum_open_positions=self.demo["maximum_open_positions"],
            maximum_asset_exposure_quote=self.demo["quote_amount"],
            maximum_total_exposure_quote=self.demo["maximum_total_exposure_quote"],
            maximum_daily_loss_quote=self.demo["maximum_daily_loss_quote"],
            maximum_spread_bps=self.demo["maximum_spread_bps"],
            minimum_depth_quote=self.demo["minimum_depth_quote"]))
        risk.state.kill_switch = self.kill.status()["engaged"]
        risk.state.realized_pnl_today = float(pnl)
        current_position = self.store.open_position()
        if current_position:
            risk.state.open_positions[current_position["symbol"]] = float(current_position.get("entry_quote") or 10)
        market = candidate["market"]
        if not reasons:
            snapshot = MarketSnapshot(
                "BTCUSDT", datetime.now(UTC), float(market["bid"]), float(market["ask"]),
                float(market.get("quote_volume_24h") or 0), float(market["bid_depth_quote"]),
                float(market["ask_depth_quote"]), 0, 0, 0, bool(market.get("data_complete")))
            proposal = Opportunity("BTCUSDT", datetime.now(UTC), self.demo["policy"],
                                   True, "buy", 0, 0, 0, 0, ())
            _, vetoes = risk.can_enter(proposal, self.demo["quote_amount"], snapshot)
            reasons.extend(f"independent_risk:{reason}" for reason in vetoes)
        if last_closed and last_closed[0]:
            elapsed = (datetime.now(UTC) - datetime.fromisoformat(last_closed[0])).total_seconds()
            if elapsed < float(self.demo["cooldown_minutes"]) * 60:
                reasons.append("cooldown_active")
        return not reasons, reasons

    def _market_entry_reasons(self) -> list[str]:
        if self.market_status is None:
            return []  # Standalone tests/emergency tools do not construct a collector.
        status = self.market_status().get("BTCUSDT", {})
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(status["last_message_at"])).total_seconds()
        except (KeyError, ValueError, TypeError):
            age = math.inf
        if (status.get("connection_state") != "connected" or
                not status.get("book_valid") or not 0 <= age <= 15):
            return ["live_market_disconnected_or_stale"]
        return []

    @staticmethod
    def _classify_reconciliation_error(exc: BaseException) -> tuple[str, bool, dict]:
        """Classify conservatively; unknown, auth and state errors never auto-recover."""
        details: dict[str, Any] = {"error_type": type(exc).__name__}
        if isinstance(exc, BinanceDemoAPIError):
            details.update(http_status=exc.http_status, api_code=exc.api_code)
            if exc.http_status in {401, 403} or exc.api_code in {-2014, -2015}:
                return "authentication", False, details
            if (getattr(exc, "transport_error", None) in {"ConnectionError", "Timeout", "ConnectTimeout", "ReadTimeout"} or
                    exc.http_status in {408, 429} or
                    (exc.http_status is not None and exc.http_status >= 500) or
                    exc.api_code in {-1001, -1003, -1006, -1007, -1021}):
                return "demo_transport_transient", True, details
            return "demo_api_rejected", False, details
        if isinstance(exc, RuntimeError):
            message = str(exc).lower()
            if "credentials are incomplete" in message or "transport is incomplete" in message:
                return "runtime_configuration", False, details
            if "orders are disabled" in message:
                return "runtime_configuration", False, details
            return "runtime_state", False, details
        if isinstance(exc, PermissionError):
            return "permissions_or_authentication", False, details
        if isinstance(exc, (TimeoutError, ConnectionError)):
            details.update(errno=getattr(exc, "errno", None),
                           winerror=getattr(exc, "winerror", None))
            return "transport_transient", True, details
        return "unexpected_internal_error", False, details

    def _invalidate_session_for_recovery(self, session: dict | None, reason: str) -> None:
        if session and session.get("state") in {"authorized", "running"}:
            self._stop_session(session["session_id"], reason)

    def _block_reconciliation(self, category: str, details: dict,
                              session: dict | None, position: dict | None) -> bool:
        self._reconciled = False
        self._reconciliation_blocked = True
        self._next_reconcile_monotonic = math.inf
        self.last_error = f"reconciliation_blocked:{category}"
        self.kill.engage(self.last_error)
        self._invalidate_session_for_recovery(session, self.last_error)
        self.state = "RECOVERY_REQUIRED"
        self.reconciliation = {
            "state": "blocked", "last_attempt_at": iso_now(),
            "last_success_at": self.reconciliation.get("last_success_at"),
            "failure_count": self._reconcile_failures, "transient": False,
            "category": category, "next_retry_at": None, "error": details,
        }
        self.store.activity("reconciliation_blocked", {
            "category": category, "transient": False, **details,
            "position_present": bool(position), "authorization_invalidated": bool(session),
        }, position.get("session_id") if position else (session or {}).get("session_id"))
        return False

    def _reconciliation_failure(self, exc: BaseException, session: dict | None,
                                position: dict | None) -> bool:
        category, transient, details = self._classify_reconciliation_error(exc)
        frames = traceback.extract_tb(exc.__traceback__)[-6:]
        details["traceback"] = [{"file": Path(frame.filename).name, "line": frame.lineno,
                                  "function": frame.name} for frame in frames]
        self._reconciled = False
        self._reconcile_failures += 1
        delays = (5, 15, 30, 60)
        delay = delays[min(self._reconcile_failures - 1, len(delays) - 1)] if transient else None
        self._next_reconcile_monotonic = time.monotonic() + delay if delay else math.inf
        next_retry = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat() if delay else None
        self.last_error = f"reconciliation_failed:{type(exc).__name__}:{category}"
        self.kill.engage(self.last_error)
        self._invalidate_session_for_recovery(session, self.last_error)
        self._reconciliation_blocked = not transient
        self.state = "RECOVERY_RETRY_WAIT" if transient else "RECOVERY_REQUIRED"
        self.reconciliation = {
            "state": "retry_wait" if transient else "blocked",
            "last_attempt_at": iso_now(),
            "last_success_at": self.reconciliation.get("last_success_at"),
            "failure_count": self._reconcile_failures, "transient": transient,
            "category": category, "next_retry_at": next_retry, "error": details,
        }
        self.store.activity("reconciliation_failed", {
            "error": self.last_error, "category": category, "transient": transient,
            "next_retry_at": next_retry, "traceback": details["traceback"],
            "http_status": details.get("http_status"), "api_code": details.get("api_code"),
            "authorization_invalidated": bool(session),
        }, position.get("session_id") if position else (session or {}).get("session_id"))
        return False

    def _reconcile(self, session: dict | None, position: dict | None) -> bool:
        """Reconcile durable local state and authenticated Binance Demo reads."""
        attempted_at = iso_now()
        try:
            service = self._service()
            readiness = service.broker.readiness()
            if not readiness.get("authenticated_reads_ready"):
                raise RuntimeError("Binance Demo credentials are incomplete for reconciliation")
            unresolved = service.journal.unresolved()
            if unresolved:
                return self._block_reconciliation(
                    "unresolved_or_open_orders", {"unresolved_intents": len(unresolved)}, session, position)
            if position and position["state"] != "OPEN":
                return self._block_reconciliation(
                    "position_state_unknown", {"position_state": position["state"]}, session, position)
            server = service.broker.server_time()
            offset = int(server["serverTime"]) - int(datetime.now(UTC).timestamp() * 1000)
            self._clock_offset_ms = offset
            service.broker.clock_ms = lambda: int(datetime.now(UTC).timestamp() * 1000) + offset
            open_orders = service.broker.open_orders("BTCUSDT")
            account = service.broker.balances()
            if unresolved or open_orders:
                return self._block_reconciliation(
                    "unresolved_or_open_orders",
                    {"unresolved_intents": len(unresolved), "open_orders": len(open_orders)},
                    session, position)
            if not account.get("canTrade"):
                return self._block_reconciliation(
                    "account_trading_permission", {"can_trade": False}, session, position)
            available = next((Decimal(str(row.get("free", "0")))
                              for row in account.get("balances", [])
                              if row.get("asset") == "BTC"), Decimal("0"))
            if position and position["state"] == "OPEN" and available < Decimal(position["quantity"]):
                return self._block_reconciliation(
                    "balance_divergence",
                    {"reason": "available_base_below_recorded_position",
                     "recorded_quantity": position["quantity"],
                     "available_quantity": str(available)}, session, position)
            self._reconciled = True
            self._reconciliation_blocked = False
            self._reconcile_failures = 0
            self._last_reconcile_monotonic = time.monotonic()
            self._next_reconcile_monotonic = self._last_reconcile_monotonic + 30
            self.last_error = None
            self.reconciliation = {
                "state": "healthy", "last_attempt_at": attempted_at,
                "last_success_at": iso_now(), "failure_count": 0,
                "transient": None, "category": None,
                "next_retry_at": None, "error": None,
                "unresolved_intents": 0, "open_orders": 0,
                "account_can_trade": True, "position_present": bool(position),
                "credentials_present": bool(readiness.get("credentials_present")),
            }
            self.store.activity("reconciliation_completed", {
                "unresolved_intents": 0, "open_orders": 0,
                "account_can_trade": True, "position_present": bool(position),
                "authenticated_demo_read": True,
            }, position.get("session_id") if position else (session or {}).get("session_id"))
            return True
        except Exception as exc:
            return self._reconciliation_failure(exc, session, position)

    @staticmethod
    def _net_quantity(order: dict, base_asset: str) -> Decimal:
        quantity = Decimal(str(order.get("executedQty", "0")))
        for fill in order.get("fills", []):
            if fill.get("commissionAsset") == base_asset:
                quantity -= Decimal(str(fill.get("commission", "0")))
        return max(Decimal("0"), quantity)

    def _enter(self, session: dict, candidate: dict) -> None:
        service = self._service()
        plan = service.plan("BTCUSDT", Decimal("10"))
        rules = SymbolRules.from_exchange_info(service.broker.exchange_info("BTCUSDT"), "BTCUSDT")
        latest_price = Decimal(str(service.broker.book_ticker("BTCUSDT")["askPrice"]))
        if not latest_price.is_finite() or latest_price <= 0:
            raise RuntimeError("executable Demo ask unavailable")
        # Avoid sizing from the rolling average when the executable ask moved.
        quantity_to_buy = rules.quantity_for_quote(Decimal("10"), latest_price)
        if Decimal(plan.available_quote_balance) < quantity_to_buy * latest_price:
            raise RuntimeError("virtual quote balance is insufficient at executable ask")
        decision_ask = Decimal(str(candidate["market"].get("ask") or "0"))
        if decision_ask <= 0:
            raise RuntimeError("decision-time ask is unavailable")
        price_move_bps = abs(latest_price / decision_ask - 1) * Decimal("10000")
        if price_move_bps > Decimal(str(self.demo["maximum_slippage_bps"])):
            raise RuntimeError("pre-submit price movement exceeds the frozen slippage limit")
        current_session = self._authorization()
        if (self.kill.status()["engaged"] or self._market_entry_reasons() or
                not current_session or current_session["session_id"] != session["session_id"]):
            raise PermissionError("Demo entry authorization or live market was invalidated")
        allowed, vetoes = self._gate(current_session, candidate)
        if not allowed:
            raise PermissionError("Demo entry revalidation failed: " + ",".join(vetoes))
        position_id = f"pos-{uuid.uuid4().hex}"
        client_id = f"bai64-b-{uuid.uuid4().hex[:20]}"
        now = datetime.now(UTC)
        with sqlite3.connect(self.store.path) as db:
            db.execute("""INSERT INTO positions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       (position_id, session["session_id"], "BTCUSDT", "A_quantitative",
                        "ENTRY_SUBMITTING", candidate["evaluation_id"], None, None, None,
                        None, None, None, None, None, "[]", None, client_id, None, None,
                        json.dumps({"decision": {"evaluated_at": candidate["evaluated_at"],
                                   "market": candidate["market"],
                                   "prediction": candidate["prediction"],
                                   "unified_decision_id": candidate["unified"]["decision_id"],
                                   "planned_risk": candidate["unified"]["planned_risk"],
                                   "pre_submit_price": str(latest_price),
                                   "pre_submit_price_move_bps": str(price_move_bps)}})))
            db.execute("INSERT INTO consumed_evaluations VALUES(?,?,?)",
                       (candidate["evaluation_id"], now.isoformat(), "entry_attempt"))
        self.store.activity("risk_approved", {"position_id": position_id,
                            "evaluation_id": candidate["evaluation_id"],
                            "quote_amount": "10", "orders_sent": False}, session["session_id"])
        self.ledger.append("experimental_demo_entry_approved", {
            "session_id": session["session_id"], "position_id": position_id,
            "evaluation_id": candidate["evaluation_id"], "symbol": "BTCUSDT",
            "unified_decision_id": candidate["unified"]["decision_id"],
            "policy": "A_quantitative", "quote_amount": "10",
            "category": "EXPERIMENTAL_DEMO", "order_sent_at_record_time": False})
        order = service._submit(diagnostic_id=position_id, symbol="BTCUSDT", side="BUY",
                                quantity=str(quantity_to_buy), client_id=client_id)
        if order.get("status") != "FILLED":
            self.kill.engage("phase64_entry_not_fully_filled")
            with sqlite3.connect(self.store.path) as db:
                db.execute("UPDATE positions SET state='RECOVERY_REQUIRED',payload_json=? WHERE position_id=?",
                           (json.dumps({"entry": order}), position_id))
            raise RuntimeError("entry not fully filled; recovery required")
        quantity = self._net_quantity(order, rules.base_asset)
        quote = Decimal(str(order.get("cummulativeQuoteQty", "0")))
        price = quote / Decimal(str(order["executedQty"])) if Decimal(str(order["executedQty"])) else Decimal("0")
        planned = now + timedelta(minutes=self.demo["planned_holding_minutes"])
        with sqlite3.connect(self.store.path) as db:
            db.execute("""UPDATE positions SET state='OPEN',opened_at=?,planned_close_at=?,quantity=?,
                          entry_quote=?,entry_price=?,fees_json=?,payload_json=? WHERE position_id=?""",
                       (now.isoformat(), planned.isoformat(), str(quantity), str(quote), str(price),
                        json.dumps(order.get("fills", [])),
                        json.dumps({"decision": {"evaluated_at": candidate["evaluated_at"],
                                   "market": candidate["market"],
                                   "prediction": candidate["prediction"],
                                   "unified_decision_id": candidate["unified"]["decision_id"],
                                   "planned_risk": candidate["unified"]["planned_risk"],
                                   "pre_submit_price": str(latest_price),
                                   "pre_submit_price_move_bps": str(price_move_bps)},
                                    "entry": order}), position_id))
            db.execute("UPDATE sessions SET state='running',entries=entries+1 WHERE session_id=?",
                       (session["session_id"],))
        self.store.activity("demo_position_opened", {"position_id": position_id,
                            "quote_amount": "10", "category": "EXPERIMENTAL_DEMO"}, session["session_id"])
        self.ledger.append("experimental_demo_position_opened", {
            "session_id": session["session_id"], "position_id": position_id,
            "client_order_id": client_id, "exchange_status": order.get("status"),
            "executed_quantity": str(quantity), "entry_quote": str(quote)})

    def _exit_reason(self, position: dict, candidate: dict | None, service) -> str | None:
        now = datetime.now(UTC)
        if self.kill.status()["engaged"]:
            return "kill_switch"
        opened = datetime.fromisoformat(position["opened_at"])
        if now >= opened + timedelta(minutes=self.demo["maximum_absolute_minutes"]):
            return "absolute_duration_limit"
        current = Decimal(str(service.broker.book_ticker("BTCUSDT")["bidPrice"]))
        if not current.is_finite() or current <= 0:
            raise RuntimeError("executable Demo bid unavailable")
        entry = Decimal(position["entry_price"])
        if entry and (current / entry - 1) * Decimal("10000") <= -Decimal(str(self.demo["stop_loss_bps"])):
            return "stop_loss"
        if now >= datetime.fromisoformat(position["planned_close_at"]):
            return "planned_horizon"
        if candidate:
            signal = candidate["prediction"].get("horizons", {}).get(
                str(self.demo["horizon_minutes"]), {}).get("signal")
            if signal == "down":
                return "signal_invalidation"
        return None

    def _close(self, position: dict, reason: str) -> None:
        service = self._service()
        rules = SymbolRules.from_exchange_info(service.broker.exchange_info("BTCUSDT"), "BTCUSDT")
        bid = Decimal(str(service.broker.book_ticker("BTCUSDT")["bidPrice"]))
        if not bid.is_finite() or bid <= 0:
            raise RuntimeError("executable Demo bid unavailable")
        quantity = rules.quantity_for_quote(Decimal(position["quantity"]) * bid, bid)
        client_id = f"bai64-s-{uuid.uuid4().hex[:20]}"
        with sqlite3.connect(self.store.path) as db:
            db.execute("UPDATE positions SET state='EXIT_SUBMITTING',exit_client_id=?,close_reason=? "
                       "WHERE position_id=?", (client_id, reason, position["position_id"]))
        order = service._submit(diagnostic_id=position["position_id"], symbol="BTCUSDT", side="SELL",
                                quantity=str(quantity), client_id=client_id)
        if order.get("status") != "FILLED":
            self.kill.engage("phase64_exit_not_fully_filled")
            with sqlite3.connect(self.store.path) as db:
                db.execute("UPDATE positions SET state='RECOVERY_REQUIRED',payload_json=? WHERE position_id=?",
                           (json.dumps({"exit": order}), position["position_id"]))
            raise RuntimeError("exit not fully filled; recovery required")
        exit_quote = Decimal(str(order.get("cummulativeQuoteQty", "0")))
        sold = Decimal(str(order.get("executedQty", "0")))
        price = exit_quote / sold if sold else Decimal("0")
        entry_order = position.get("payload", {}).get("entry", {})
        fills = [*entry_order.get("fills", []), *order.get("fills", [])]
        quote_fees = sum(Decimal(str(fill.get("commission", "0"))) for fill in fills
                         if fill.get("commissionAsset") == "USDT")
        unknown_fee_assets = sorted({fill.get("commissionAsset") for fill in fills
                                     if fill.get("commissionAsset") not in {None, "USDT", "BTC"}
                                     and Decimal(str(fill.get("commission", "0"))) != 0})
        net = exit_quote - Decimal(position["entry_quote"]) - quote_fees
        payload = dict(position.get("payload", {})) | {"exit": order}
        residual = max(Decimal("0"), Decimal(position["quantity"]) - sold)
        payload["economics"] = {"net_quote_complete": not unknown_fee_assets,
                                "unknown_fee_assets": unknown_fee_assets,
                                "basis": "cash_flow_after_quote_fees_residual_not_marked_to_profit",
                                "residual_base_quantity": str(residual),
                                "residual_mark_to_bid_quote": None}
        with sqlite3.connect(self.store.path) as db:
            db.execute("""UPDATE positions SET state='CLOSED',closed_at=?,exit_quote=?,exit_price=?,
                          net_quote=?,payload_json=? WHERE position_id=?""",
                       (iso_now(), str(exit_quote), str(price),
                        str(net) if not unknown_fee_assets else None, json.dumps(payload),
                        position["position_id"]))
        self.store.activity("demo_position_closed", {"position_id": position["position_id"],
                            "reason": reason, "net_quote": str(net) if not unknown_fee_assets else None,
                            "residual_base_quantity": str(residual)}, position["session_id"])
        self.ledger.append("experimental_demo_position_closed", {
            "session_id": position["session_id"], "position_id": position["position_id"],
            "client_order_id": client_id, "exchange_status": order.get("status"),
            "reason": reason, "net_quote": str(net) if not unknown_fee_assets else None,
            "unknown_fee_assets": unknown_fee_assets})

    def _consume_abstention(self, session: dict, candidate: dict, reasons: list[str]) -> None:
        with sqlite3.connect(self.store.path) as db:
            cursor = db.execute("INSERT OR IGNORE INTO consumed_evaluations VALUES(?,?,?)",
                                (candidate["evaluation_id"], iso_now(), "abstention"))
        if cursor.rowcount:
            payload = {"evaluation_id": candidate["evaluation_id"], "reasons": reasons,
                       "symbol": "BTCUSDT", "policy": "A_quantitative",
                       "category": "EXPERIMENTAL_DEMO", "orders_sent": False}
            self.store.activity("entry_abstention", payload, session["session_id"])
            self.ledger.append("experimental_demo_entry_abstention", payload)

    def cycle(self) -> None:
        session = self._authorization()
        position = self.store.open_position()
        if position and position["state"] != "OPEN":
            if not self._reconciliation_blocked:
                self._block_reconciliation(
                    "position_state_unknown", {"position_state": position["state"]}, session, position)
            return
        now_monotonic = time.monotonic()
        reconciliation_due = (
            not self._reconciliation_blocked and
            now_monotonic >= self._next_reconcile_monotonic)
        if self._reconciliation_blocked:
            self.state = "RECOVERY_REQUIRED"
            return
        if not self._reconciled and not reconciliation_due:
            self.state = "RECOVERY_RETRY_WAIT"
            return
        if reconciliation_due and not self._reconcile(session, position):
            return
        if position:
            try:
                service = self._service()
                # Exit limits/kill switch remain usable even if inference SQLite is busy.
                reason = self._exit_reason(position, None, service)
                candidate = self._latest_candidate() if reason is None else None
                if reason is None:
                    reason = self._exit_reason(position, candidate, service)
                if reason:
                    self._close(position, reason)
            except Exception as exc:
                self._reconciliation_failure(exc, session, position)
            return
        if not session:
            self.state = "OBSERVE"
            return
        candidate = self._latest_candidate()
        self.state = "AUTHORIZED_DEMO"
        allowed, reasons = self._gate(session, candidate)
        if not allowed:
            if candidate is not None:
                self._consume_abstention(session, candidate, reasons)
            return
        try:
            self._enter(session, candidate)
        except Exception as exc:
            self.last_error = f"entry_failure:{type(exc).__name__}"
            self.kill.engage(self.last_error)
            self.store.activity("entry_failure", {"error": self.last_error}, session["session_id"])

    async def run(self) -> None:
        self._write_control()
        self.store.activity("engine_started", {"boot_id": self.boot_id, "orders_sent": False})
        # Dedicated capacity: a slow Qwen/news job in asyncio's default pool
        # cannot queue ahead of position management. Cycles never overlap.
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="demo-position-manager") as executor:
            while not self._stop.is_set():
                try:
                    await asyncio.get_running_loop().run_in_executor(executor, self.cycle)
                except Exception as exc:
                    self._reconciliation_failure(exc, self.store.active_session(),
                                                 self.store.open_position())
                self._write_control()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

    def stop(self) -> None:
        self._stop.set()


def _fresh_engine_control(root: Path) -> dict:
    control = root / "runtime/phase_6_4/engine.json"
    if not control.exists():
        raise RuntimeError("Phase 6.4 engine is not running")
    engine = json.loads(control.read_text(encoding="utf-8"))
    try:
        age = (datetime.now(UTC) - datetime.fromisoformat(engine["updated_at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("Phase 6.4 engine heartbeat is invalid") from None
    if age > 15:
        raise RuntimeError("Phase 6.4 engine heartbeat is stale")
    return engine


def _healthy_engine_control(root: Path) -> dict:
    engine = _fresh_engine_control(root)
    reconciliation = engine.get("reconciliation") or {}
    if engine.get("state") != "OBSERVE" or reconciliation.get("state") != "healthy":
        raise RuntimeError("engine reconciliation is not healthy; keep the kill switch engaged")
    try:
        reconciliation_age = (datetime.now(UTC) - datetime.fromisoformat(
            reconciliation["last_success_at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("engine reconciliation evidence is invalid") from None
    if not 0 <= reconciliation_age <= 45:
        raise RuntimeError("engine reconciliation evidence is stale")
    return engine


def prepare_authorization(root: Path = ROOT) -> dict:
    config = load_phase64_config(root)
    engine = _healthy_engine_control(root)
    store = AutonomousStore(root / "runtime/phase_6_4/autonomous.sqlite3")
    if store.open_position():
        raise RuntimeError("an open or unresolved position already exists")
    session_id = f"demo-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    demo = config["experimental_demo"]
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE sessions SET state='stopped',stop_reason='superseded' "
                   "WHERE state IN ('prepared','authorized','running')")
        db.execute("INSERT INTO sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (session_id, engine["boot_id"], iso_now(), None, None, "prepared",
                    demo["policy"], demo["symbol"], str(demo["quote_amount"]), None, 0, None))
    store.activity("session_prepared", {"boot_id": engine["boot_id"],
                   "quote_amount": str(demo["quote_amount"]), "orders_sent": False}, session_id)
    return {"session_id": session_id, "boot_id": engine["boot_id"], "state": "prepared",
            "policy": demo["policy"], "symbol": demo["symbol"],
            "quote_amount": demo["quote_amount"], "orders_sent": False,
            "next_step": "explicit authorization is still required"}


def authorize_session(session_id: str, confirmation: str, root: Path = ROOT,
                      service_factory=None) -> dict:
    config = load_phase64_config(root)
    expected = config["experimental_demo"]["authorization_confirmation"]
    if confirmation != expected:
        raise PermissionError("explicit Phase 6.4 Demo authorization is invalid")
    if os.getenv("BITCOIN_AI_ENABLE_DEMO_ORDERS") != "I_UNDERSTAND_DEMO_ONLY":
        raise PermissionError("BITCOIN_AI_ENABLE_DEMO_ORDERS is not enabled for Demo")
    control = _healthy_engine_control(root)
    store = AutonomousStore(root / "runtime/phase_6_4/autonomous.sqlite3")
    with sqlite3.connect(store.path) as db:
        db.row_factory = sqlite3.Row
        session = db.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not session or session["state"] != "prepared":
            raise RuntimeError("session is not prepared")
        if session["boot_id"] != control["boot_id"]:
            raise RuntimeError("engine restarted; prepare a new session")
        service = (service_factory or build_demo_service)(root)
        server = service.broker.server_time()
        offset = int(server["serverTime"]) - int(datetime.now(UTC).timestamp() * 1000)
        service.broker.clock_ms = lambda: int(datetime.now(UTC).timestamp() * 1000) + offset
        account = service.broker.balances()
        if not account.get("canTrade"):
            raise PermissionError("Binance Demo account cannot trade")
        if service.journal.unresolved() or service.broker.open_orders("BTCUSDT"):
            raise RuntimeError("Demo reconciliation is not clean")
        service.plan("BTCUSDT", Decimal("10"))
        latest = _healthy_engine_control(root)
        if latest["boot_id"] != control["boot_id"] or store.open_position():
            raise RuntimeError("engine or position changed during authorization checks")
        expires = datetime.now(UTC) + timedelta(minutes=config["experimental_demo"]["session_maximum_minutes"])
        confirmation_hash = hashlib.sha256(confirmation.encode()).hexdigest()
        db.execute("UPDATE sessions SET state='authorized',authorized_at=?,expires_at=?,confirmation_hash=? "
                   "WHERE session_id=?", (iso_now(), expires.isoformat(), confirmation_hash, session_id))
    PersistentKillSwitch(root / "runtime/phase_6_2/kill_switch.json").clear(KILL_SWITCH_CONFIRMATION)
    store.activity("session_authorized", {"expires_at": expires.isoformat(),
                   "authorization_bound_to_boot": True}, session_id)
    return {"session_id": session_id, "state": "authorized", "expires_at": expires.isoformat(),
            "environment": "DEMO", "quote_amount": 10.0,
            "warning": "the running engine may now submit Demo orders when every frozen gate passes"}


def stop_session(root: Path = ROOT, reason: str = "manual_stop") -> dict:
    store = AutonomousStore(root / "runtime/phase_6_4/autonomous.sqlite3")
    session = store.active_session()
    if session:
        with sqlite3.connect(store.path) as db:
            db.execute("UPDATE sessions SET state='stopped',stop_reason=? WHERE session_id=?",
                       (reason, session["session_id"]))
        store.activity("session_stopped", {"reason": reason}, session["session_id"])
    kill = PersistentKillSwitch(root / "runtime/phase_6_2/kill_switch.json").engage(reason)
    return {"session_id": session["session_id"] if session else None,
            "new_entries_blocked": True, "kill_switch": kill,
            "open_position": store.open_position(),
            "note": "an open position remains under the engine exit monitor"}


def emergency_close(root: Path, confirmation: str) -> dict:
    """Explicit CLI-only emergency exit; this can send one Demo SELL order."""
    if confirmation != "I_AUTHORIZE_DEMO_EMERGENCY_CLOSE":
        raise PermissionError("explicit Demo emergency-close confirmation is invalid")
    store = AutonomousStore(root / "runtime/phase_6_4/autonomous.sqlite3")
    position = store.open_position()
    if not position or position["state"] != "OPEN":
        return {"closed": False, "reason": "no_open_strategy_position", "orders_sent": False}
    engine = SupervisedDemoEngine(root)
    engine._close(position, "explicit_emergency_close")
    engine.kill.engage("emergency_close_completed")
    return {"closed": True, "position_id": position["position_id"],
            "environment": "DEMO", "new_entries_blocked": True}


def preservation_manifest(root: Path = ROOT) -> dict:
    paths = ["reports/final_evaluation.json", "reports/phase_2/validation.json",
             "reports/phase_3/validation.json", "reports/phase_4/validation.json",
             "reports/phase_5/validation.json", "reports/phase_6/validation.json",
             "reports/phase_6_1/validation.json", "reports/phase_6_2/validation.json",
             "reports/phase_6_3/validation.json", "reports/test_registry.json"]
    result = {path: digest(root / path) for path in paths if (root / path).exists()}
    result.update(historical_artifacts_modified=False,
                  july_september_2026_holdout_reused=False,
                  generated_at=iso_now())
    return result
