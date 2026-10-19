"""Versioned active Demo protocol, shared by CLI, intelligence and executor.

No broker, secrets, random entries or model fitting. Profiles are immutable
session snapshots. Research benchmark datasets are never read here.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

MODE = "DEMO_ACTIVE_EXPERIMENTAL"
PROFILE_PATH = Path("configs/phase_6_4_3.json")
UTC = timezone.utc


def profile_hash(profile: dict) -> str:
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_profile(root: Path, allow_probes: bool = False) -> dict:
    value = json.loads((root / PROFILE_PATH).read_text(encoding="utf-8"))
    limits = value["limits"]
    if value["mode"] != MODE or value["environment"] != "DEMO" or limits["symbol"] != "BTCUSDT":
        raise ValueError("active experiment is strictly BTC Spot Demo")
    caps = {"quote_amount": 10, "maximum_entries_per_session": 6, "session_maximum_minutes": 60,
            "maximum_loss_per_operation_quote": .1, "maximum_session_loss_quote": .5,
            "maximum_open_positions": 1, "maximum_total_exposure_quote": 10}
    if any(not 0 < float(limits[key]) <= cap for key, cap in caps.items()):
        raise ValueError("active Demo safety limit exceeded")
    if not 3 <= limits["planned_holding_minutes"] <= limits["maximum_absolute_minutes"] <= 8:
        raise ValueError("initial active holding window must be between three and eight minutes")
    if limits["maximum_extension_minutes"] != 0 or limits["stop_loss_bps"] <= 0:
        raise ValueError("v1 has a fixed stop and no holding extension")
    if not .5 < limits["minimum_up_probability"] <= 1 or not 0 < limits["probe_after_seconds"] <= 600:
        raise ValueError("invalid versioned entry criteria")
    value["allow_probes"] = bool(allow_probes)
    return value


def create_profile_tables(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS session_profiles(
            session_id TEXT PRIMARY KEY, mode TEXT NOT NULL,
            profile_json TEXT NOT NULL, profile_sha256 TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS demo_residuals(
            position_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, symbol TEXT NOT NULL,
            quantity TEXT NOT NULL, cost_basis_quote TEXT, recorded_at TEXT NOT NULL);
    """)


def session_profile(path: Path, session_id: str) -> dict | None:
    if not path.exists():
        return None
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=.5) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='session_profiles'").fetchone():
            return None
        row = db.execute("SELECT profile_json,profile_sha256 FROM session_profiles WHERE session_id=?", (session_id,)).fetchone()
    if row is None:
        return None
    profile = json.loads(row[0])
    if profile_hash(profile) != row[1]:
        raise ValueError("session profile integrity failure")
    return profile


def experiment_context(path: Path, as_of: datetime) -> dict | None:
    """Only currently authorized sessions can produce exploratory proposals."""
    if not path.exists():
        return None
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=.5) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM sessions WHERE state IN ('prepared','authorized','running') ORDER BY created_at DESC LIMIT 1").fetchone()
        if row is None:
            return None
        session = dict(row)
        profile = session_profile(path, session["session_id"])
        if profile is None:
            return None
        closed = db.execute("SELECT MAX(closed_at) FROM positions WHERE session_id=?", (session["session_id"],)).fetchone()[0]
        positions = db.execute("SELECT payload_json FROM positions WHERE session_id=?", (session["session_id"],)).fetchall()
    probes = sum(json.loads(item[0]).get("decision", {}).get("entry_category") == "EXPLORATORY_PROBE" for item in positions)
    anchor = closed or session.get("authorized_at")
    elapsed = (as_of - datetime.fromisoformat(anchor)).total_seconds() if anchor else 0
    authorized = (session["state"] in {"authorized", "running"} and session.get("expires_at")
                  and datetime.fromisoformat(session["expires_at"]) > as_of)
    return {"profile": profile, "session_id": session["session_id"],
            "authorized": bool(authorized), "seconds_since_entry_anchor": max(0, elapsed),
            "probe_entries": probes}


def active_entry_reasons(prediction: dict, market: dict, limits: dict) -> list[str]:
    """Additional engineering gates; never an assertion of economic advantage."""
    reasons = []
    for key in ("momentum_5m_bps", "volatility_bps"):
        value = market.get(key)
        if value is None or not math.isfinite(float(value)):
            reasons.append(f"active_{key}_unavailable")
    if float(market.get("volatility_bps") or 0) > limits["maximum_volatility_bps"]:
        reasons.append("active_volatility_limit")
    return reasons


def commission_rates(payload: dict) -> dict:
    """Undiscounted rates are conservative when an optional BNB discount exists."""
    result = {}
    for side, role in (("buy", "buyer"), ("sell", "seller")):
        rate = Decimal("0")
        for category in ("standardCommission", "specialCommission", "taxCommission"):
            block = payload.get(category)
            if not isinstance(block, dict) or "taker" not in block or role not in block:
                raise ValueError("commission schedule is incomplete")
            for key in ("taker", role):
                value = Decimal(str(block[key]))
                if not value.is_finite() or not 0 <= value < 1:
                    raise ValueError("invalid commission rate")
                rate += value
        result[side] = str(rate)
    return {**result, "source": "authenticated_undiscounted_commission_schedule_estimate", "actual_fees": False}


def mark_position(position: dict, bid: Decimal, step: Decimal, rates: dict, slippage_bps: float) -> dict:
    """Mark only a sellable lot; retain unsellable dust and its cost basis."""
    quantity = Decimal(position["quantity"])
    sellable = (quantity // step) * step
    entry = Decimal(position["entry_quote"])
    entry_fees = sum(Decimal(str(f.get("commission", "0"))) for f in position.get("payload", {}).get("entry", {}).get("fills", []) if f.get("commissionAsset") == "USDT")
    basis = (entry + entry_fees) * sellable / quantity
    receipt = sellable * bid * (1 - Decimal(rates["sell"])) * (1 - Decimal(str(slippage_bps)) / 10000)
    return {"sellable_quantity": str(sellable), "allocated_cost_basis_quote": str(basis),
            "estimated_net_quote": str(receipt - basis), "bid": str(bid),
            "residual_quantity": str(quantity - sellable), "actual_fees": False,
            "source": "executable_bid_after_estimated_exit_costs"}
