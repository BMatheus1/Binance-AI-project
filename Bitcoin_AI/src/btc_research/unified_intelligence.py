"""Single, persisted operational proposal contract; no broker or order transport.

Research policies B/C/D remain observations. The frozen A/5m specialist is the
only execution candidate. Optional research context cannot silently change it.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from .active_demo import MODE, active_entry_reasons

UTC = timezone.utc
SCHEMA_VERSION = "unified-v1"
DecisionAction = Literal["COMPRAR", "NAO_COMPRAR", "AGUARDAR_DADOS", "INDISPONIVEL_SEGURANCA"]


def finite(value) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("UTC/offset timestamp required")
    return result.astimezone(UTC)


def frozen_entry_reasons(prediction: dict, market: dict, limits: dict) -> list[str]:
    """The pre-existing A/5m signal and liquidity gates, shared by risk checks."""
    reasons = []
    if prediction.get("state") != "ready":
        reasons.append("forecast_unavailable")
    forecast = prediction.get("horizons", {}).get(str(limits["horizon_minutes"]), {})
    probabilities = forecast.get("probabilities", {})
    probability = finite(probabilities.get("up"))
    values = [finite(probabilities.get(key)) for key in ("down", "tie", "up")]
    if (any(value is None or not 0 <= value <= 1 for value in values)
            or abs(sum(value or 0 for value in values) - 1) > 1e-5):
        reasons.append("invalid_probability_distribution")
    if forecast.get("signal") != "up":
        reasons.append("frozen_signal_not_up")
    if probability is None or probability < limits["minimum_up_probability"]:
        reasons.append("up_probability_below_frozen_threshold")
    if not market.get("data_complete"):
        reasons.append("market_data_incomplete")
    bid, ask = finite(market.get("bid")), finite(market.get("ask"))
    if bid is None or ask is None or bid <= 0 or ask < bid:
        reasons.append("invalid_executable_quote")
    spread = finite(market.get("spread_bps"))
    if spread is None or spread < 0 or spread > limits["maximum_spread_bps"]:
        reasons.append("spread_limit")
    depth = [finite(market.get(key)) for key in ("bid_depth_quote", "ask_depth_quote")]
    if any(value is None or value < limits["minimum_depth_quote"] for value in depth):
        reasons.append("depth_limit")
    return reasons


@dataclass(frozen=True)
class UnifiedDecision:
    decision_id: str
    evaluation_id: str
    evaluated_at: str
    data_available_at: str | None
    symbol: str
    policy_version: str
    model_versions: dict[str, str]
    features_valid: bool
    horizon_minutes: int
    prediction: dict
    uncertainty: dict
    costs: dict
    planned_risk: dict
    context: dict
    decision: DecisionAction
    reasons: list[str]
    valid_until: str
    execution_state: str = "PROPOSAL_ONLY_REQUIRES_SESSION_AND_RISK"
    schema_version: str = SCHEMA_VERSION
    mode: str = "EXPERIMENTAL_DEMO"
    entry_category: str = "AI_SIGNAL"
    session_id: str | None = None

    def record(self) -> dict:
        return asdict(self)


class UnifiedTradingIntelligenceEngine:
    """One operational interface over existing frozen forecasts and stores."""
    def __init__(self, limits: dict, policy_version: str):
        self.limits = limits
        self.policy_version = policy_version

    def evaluate(self, *, evaluation_id: str, symbol: str, evaluated_at: str,
                 prediction: dict, market: dict, estimated_cost_bps: float | None,
                 context: dict | None = None, experiment: dict | None = None) -> UnifiedDecision:
        now = timestamp(evaluated_at)
        available_at = market.get("data_available_at")
        reasons = []
        temporal_valid = False
        try:
            close_at = timestamp(market["candle_close_time"])
            available = timestamp(available_at)
            quote_at = timestamp(market["quote_received_at"])
            book_at = timestamp(market["book_received_at"])
            temporal_valid = (max(close_at, quote_at, book_at) <= available <= now and
                              0 <= (now - close_at).total_seconds() <= self.limits["maximum_signal_age_seconds"]
                              and 0 <= (now - quote_at).total_seconds() <= 5
                              and 0 <= (now - book_at).total_seconds() <= 5)
        except (KeyError, TypeError, ValueError, AttributeError):
            pass
        if not temporal_valid:
            reasons.append("market_temporal_integrity_or_freshness")
        if symbol != self.limits["symbol"]:
            reasons.append("frozen_model_scope_is_btc_only")
        reasons.extend(frozen_entry_reasons(prediction, market, self.limits))
        horizon = str(self.limits["horizon_minutes"])
        forecast = prediction.get("horizons", {}).get(horizon, {})
        category = "AI_SIGNAL"
        if experiment is not None:
            reasons = [reason for reason in reasons if reason not in {
                "frozen_signal_not_up", "up_probability_below_frozen_threshold"}]
            reasons.extend(active_entry_reasons(prediction, market, self.limits))
            probabilities = forecast.get("probabilities", {})
            up, down = finite(probabilities.get("up")), finite(probabilities.get("down"))
            momentum = finite(market.get("momentum_5m_bps"))
            ai_entry = (up is not None and down is not None and up >= self.limits["minimum_up_probability"]
                        and up > down and momentum is not None and momentum > 0)
            if not ai_entry:
                profile = experiment["profile"]
                category = "EXPLORATORY_PROBE"
                if not profile["allow_probes"]:
                    reasons.append("exploration_not_authorized")
                if not experiment["authorized"]:
                    reasons.append("active_session_not_authorized")
                if experiment["seconds_since_entry_anchor"] < self.limits["probe_after_seconds"]:
                    reasons.append("probe_waiting_for_abstention_window")
                if experiment["probe_entries"] >= self.limits["maximum_probes_per_session"]:
                    reasons.append("probe_entry_limit")
            estimated_cost_bps = (finite(market.get("spread_bps")) or 0) + 2 * (
                self.limits["planning_fee_ceiling_bps_per_side"] + self.limits["maximum_slippage_bps"])
        # Gross return and calibrated favorable-move probability are deliberately
        # unknown. Directional p_up is not P(profit after costs).
        cost = finite(estimated_cost_bps)
        if cost is not None and cost < 0:
            cost = None
        probability = forecast.get("probabilities", {})
        entropy = -sum(p * math.log(p) for p in (finite(v) for v in probability.values())
                       if p is not None and 0 < p <= 1)
        reason_data = {"market_temporal_integrity_or_freshness", "market_data_incomplete", "forecast_unavailable",
                       "invalid_executable_quote", "frozen_model_scope_is_btc_only"}
        action = ("AGUARDAR_DADOS" if reason_data.intersection(reasons) else
                  "NAO_COMPRAR" if reasons else "COMPRAR")
        quote = float(self.limits["quote_amount"])
        risk = {"quote_amount": quote, "stop_loss_bps": self.limits["stop_loss_bps"],
                "planned_holding_minutes": self.limits["planned_holding_minutes"],
                "absolute_holding_minutes": self.limits["maximum_absolute_minutes"],
                "planned_stop_loss_quote_excluding_costs": quote * self.limits["stop_loss_bps"] / 10000,
                "planned_loss_quote_including_estimated_costs": (
                    quote * (self.limits["stop_loss_bps"] + cost) / 10000 if cost is not None else None),
                "loss_is_guaranteed": False, "risk_reward_ratio": None}
        if experiment is not None:
            risk.update(maximum_loss_per_operation_quote=self.limits["maximum_loss_per_operation_quote"],
                        maximum_session_loss_quote=self.limits["maximum_session_loss_quote"],
                        take_profit_net_quote=self.limits["take_profit_net_quote"])
            if risk["planned_loss_quote_including_estimated_costs"] is None or risk["planned_loss_quote_including_estimated_costs"] > self.limits["maximum_loss_per_operation_quote"]:
                reasons.append("planned_operation_loss_limit")
                action = "NAO_COMPRAR"
        details = dict(context or {})
        details.update(regime={"state": "unvalidated", "operational": False},
                       fusion={"method": "frozen_single_specialist", "weights_fitted": False,
                               "news_optional": True, "context_changes_entry": False})
        if experiment is not None:
            details["experimental_criteria"] = {"minimum_up_probability": self.limits["minimum_up_probability"],
                "momentum_5m_must_be_positive_for_ai": True, "entry_category": category,
                "probe_elapsed_seconds": experiment["seconds_since_entry_anchor"],
                "probe_wait_seconds": self.limits["probe_after_seconds"],
                "economic_advantage_required": False}
            action = "AGUARDAR_DADOS" if reason_data.intersection(reasons) else "NAO_COMPRAR" if reasons else "COMPRAR"
        identity = hashlib.sha256(f"{SCHEMA_VERSION}:{self.policy_version}:{evaluation_id}".encode()).hexdigest()
        return UnifiedDecision(
            identity, evaluation_id, now.isoformat(), available_at, symbol, self.policy_version,
            {key: value.get("model_version", "unavailable")
             for key, value in prediction.get("horizons", {}).items()},
            temporal_valid and prediction.get("state") == "ready",
            self.limits["horizon_minutes"], prediction,
            {"directional_entropy_nats": entropy if probability else None,
             "favorable_net_move_probability": None, "confidence_interval": None},
            {"estimated_round_trip_bps": cost, "source": "existing_selector_estimate",
             "spread_bps": finite(market.get("spread_bps")), "fees_are_actual": False,
             "expected_gross_bps": None, "expected_net_bps": None,
             "economically_validated": False, "category": MODE if experiment else "EXPERIMENTAL_DEMO",
             "planning_fee_ceiling_bps_per_side": self.limits.get("planning_fee_ceiling_bps_per_side")},
            risk, details, action, list(dict.fromkeys(reasons)) or [
                "authorized_controlled_probe_not_ai_alpha" if experiment and category == "EXPLORATORY_PROBE"
                else "versioned_active_ai_criteria_met" if experiment else "frozen_experimental_signal_eligible"],
            (now + timedelta(seconds=self.limits["maximum_signal_age_seconds"])).isoformat(),
            mode=MODE if experiment else "EXPERIMENTAL_DEMO", entry_category=category,
            session_id=experiment["session_id"] if experiment else None)


class UnifiedDecisionStore:
    """Canonical operational proposals in the existing evaluation SQLite DB."""
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=20) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS unified_decisions(
                    decision_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL UNIQUE,
                    evaluated_at TEXT NOT NULL, symbol TEXT NOT NULL,
                    decision TEXT NOT NULL, payload_json TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_unified_recent ON unified_decisions(evaluated_at DESC);
            """)

    def add(self, decision: UnifiedDecision) -> bool:
        with sqlite3.connect(self.path, timeout=20) as db:
            cursor = db.execute("INSERT OR IGNORE INTO unified_decisions VALUES(?,?,?,?,?,?)",
                                (decision.decision_id, decision.evaluation_id, decision.evaluated_at,
                                 decision.symbol, decision.decision,
                                 json.dumps(decision.record(), allow_nan=False, sort_keys=True)))
        return bool(cursor.rowcount)

    @staticmethod
    def recent(path: Path, limit: int = 50, symbol: str | None = None) -> list[dict]:
        if not path.exists():
            return []
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='unified_decisions'").fetchone():
                return []  # Never silently execute legacy research decisions.
            where, parameters = ("WHERE symbol=?", [symbol]) if symbol else ("", [])
            rows = db.execute(f"SELECT payload_json FROM unified_decisions {where} "
                              "ORDER BY evaluated_at DESC LIMIT ?", [*parameters, limit]).fetchall()
        return [json.loads(row[0]) for row in rows]
