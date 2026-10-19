"""Causal, unpromoted pattern hypotheses and paired exit experiments.

These functions never authorize trades. Parameters are explicit inputs for
chronological research; the live frozen strategy does not call exit_candidate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd


def executable_net(*, quantity: Decimal, entry_ask: Decimal, exit_bid: Decimal,
                   buy_fee_rate: Decimal | None, sell_fee_rate: Decimal | None,
                   exit_slippage_rate: Decimal | None) -> dict:
    """Spread is already in ask/bid, and must not be subtracted twice."""
    if quantity <= 0 or min(entry_ask, exit_bid) <= 0:
        raise ValueError("positive executable prices and quantity required")
    rates = (buy_fee_rate, sell_fee_rate, exit_slippage_rate)
    if any(rate is not None and (not rate.is_finite() or not 0 <= rate < 1) for rate in rates):
        raise ValueError("invalid fee/slippage rate")
    gross = quantity * (exit_bid - entry_ask)
    if any(rate is None for rate in rates):
        return {"gross_quote": str(gross), "net_quote": None, "source": "unknown_costs"}
    buy_cost = quantity * entry_ask * (1 + buy_fee_rate)
    sell_receipt = quantity * exit_bid * (1 - exit_slippage_rate) * (1 - sell_fee_rate)
    return {"gross_quote": str(gross), "net_quote": str(sell_receipt - buy_cost),
            "entry_total_quote": str(buy_cost), "exit_receipt_quote": str(sell_receipt),
            "source": "executable_quote_estimate", "is_realized": False}


def pattern_hypotheses(candles: pd.DataFrame, market: dict, *, as_of: pd.Timestamp) -> dict:
    """Definitions use only closed, contiguous candles; never future labels.

    Descriptive threshold-free features are recorded. A sign/crossing is a
    hypothesis identifier, not an approved trade rule or calibrated regime.
    """
    required = {"open_time", "close_time", "open", "high", "low", "close", "volume"}
    unavailable = {"state": "unavailable", "operational": False, "patterns": []}
    if not required.issubset(candles) or len(candles) < 61 or as_of.tzinfo is None:
        return unavailable
    recent = candles.tail(61).copy()
    if (recent.close_time.max() > as_of or
            recent.open_time.diff().dropna().ne(pd.Timedelta(minutes=1)).any()):
        return unavailable
    close = recent.close.astype(float)
    values = recent[["open", "high", "low", "close", "volume"]].to_numpy(float)
    if not np.isfinite(values).all() or (close <= 0).any():
        return unavailable
    returns = np.log(close).diff()
    mean20, std20 = close.iloc[-21:-1].mean(), close.iloc[-21:-1].std()
    momentum5 = float(np.log(close.iloc[-1] / close.iloc[-6]) * 10000)
    trend20 = float(np.log(close.iloc[-1] / close.iloc[-21]) * 10000)
    previous_momentum5 = float(np.log(close.iloc[-6] / close.iloc[-11]) * 10000)
    vol5 = float(returns.tail(5).std())
    vol60 = float(returns.tail(60).std())
    bid_depth, ask_depth = market.get("bid_depth_quote"), market.get("ask_depth_quote")
    imbalance = ((bid_depth - ask_depth) / (bid_depth + ask_depth)
                 if bid_depth is not None and ask_depth is not None and bid_depth + ask_depth > 0 else None)
    records = [
        ("trend_continuation", trend20 > 0 and momentum5 > 0,
         {"log_return_20_bps": trend20, "log_return_5_bps": momentum5}),
        ("pullback", trend20 > 0 and momentum5 < 0,
         {"log_return_20_bps": trend20, "log_return_5_bps": momentum5}),
        ("breakout", close.iloc[-1] > recent.high.iloc[-21:-1].max(),
         {"previous_20_high": float(recent.high.iloc[-21:-1].max()),
          "volume_ratio": float(recent.volume.iloc[-1] / recent.volume.iloc[-21:-1].mean())
          if recent.volume.iloc[-21:-1].mean() > 0 else None}),
        ("mean_reversion", close.iloc[-1] < mean20,
         {"zscore_previous_20": float((close.iloc[-1] - mean20) / std20) if std20 > 0 else None}),
        ("volatility_expansion", vol5 > vol60, {"vol5": vol5, "vol60": vol60}),
        ("momentum_acceleration", momentum5 > previous_momentum5,
         {"delta_log_return_5_bps": momentum5 - previous_momentum5}),
        ("book_imbalance", imbalance is not None and imbalance > 0, {"imbalance": imbalance}),
        ("aggressor_imbalance", None, {"reason": "no_synchronized_aggtrade_window_in_contract"}),
        ("event_reaction", None, {"reason": "no_validated_temporal_event_effect_model"}),
    ]
    return {"state": "research_only", "operational": False, "features_available_at": as_of.isoformat(),
            "patterns": [{"name": name, "detected": bool(detected) if detected is not None else None,
                          "features": features, "horizons_minutes": [1, 5, 15, 30],
                          "invalidated_by": "new_closed_candle_or_stale_market_data",
                          "oos_net_result": None, "risk_reward": None,
                          "promotion": "requires_chronological_cost_aware_validation"}
                         for name, detected, features in records]}


@dataclass(frozen=True)
class ExitExperiment:
    stop_loss_bps: float
    profit_target_quote: float
    trailing_fraction: float
    planned_seconds: int
    maximum_extension_seconds: int = 0

    def __post_init__(self):
        if (not 0 < self.stop_loss_bps < 10000 or self.profit_target_quote <= 0
                or not 0 < self.trailing_fraction < 1 or not 60 <= self.planned_seconds <= 1200
                or not 0 <= self.maximum_extension_seconds <= 180):
            raise ValueError("invalid preregistered exit experiment")


def exit_candidate(*, config: ExitExperiment, elapsed_seconds: float, gross_bps: float,
                   net_quote: float | None, peak_net_quote: float | None,
                   continuity_confirmed: bool = False, reversal_validated: bool = False,
                   liquidity_deteriorated: bool = False) -> str | None:
    """Offline alternative exits. A stop/protective exit may realize a loss."""
    if not math.isfinite(gross_bps) or elapsed_seconds < 0:
        raise ValueError("invalid observed exit values")
    if gross_bps <= -config.stop_loss_bps:
        return "stop_loss"
    if liquidity_deteriorated:
        return "liquidity_protection"
    if reversal_validated:
        return "validated_reversal"
    profitable = net_quote is not None and math.isfinite(net_quote) and net_quote > 0
    if elapsed_seconds >= config.planned_seconds:
        if not (elapsed_seconds < config.planned_seconds + config.maximum_extension_seconds
                and profitable and continuity_confirmed):
            return "planned_horizon"
    if profitable and peak_net_quote is not None and peak_net_quote >= config.profit_target_quote:
        if net_quote <= peak_net_quote * (1 - config.trailing_fraction):
            return "trailing_net_profit"
    if profitable and net_quote >= config.profit_target_quote and not continuity_confirmed:
        return "take_profit_after_costs"
    return None


def chronological_roles(rows: pd.DataFrame, boundaries: tuple[str, str, str, str]) -> dict[str, pd.DataFrame]:
    """Disjoint training/calibration/selection/evaluation blocks with label purge.

    Inputs must contain observed_at, available_at and label_end. Already consumed
    July--September 2026 data is rejected, including labels crossing its boundary.
    """
    ordered = rows.sort_values("observed_at").copy()
    for column in ("observed_at", "available_at", "label_end"):
        ordered[column] = pd.to_datetime(ordered[column], utc=True)
    if ordered.observed_at.duplicated().any() or (ordered.available_at > ordered.observed_at).any():
        raise ValueError("duplicate or noncausal observations")
    if (ordered.label_end <= ordered.observed_at).any():
        raise ValueError("label_end must follow the decision")
    forbidden_start, forbidden_end = pd.Timestamp("2026-07-01", tz="UTC"), pd.Timestamp("2026-10-01", tz="UTC")
    if ((ordered.observed_at < forbidden_end) & (ordered.label_end >= forbidden_start)).any():
        raise ValueError("consumed/forbidden holdout overlap")
    cuts = [pd.Timestamp(value) for value in boundaries]
    if any(value.tzinfo is None for value in cuts) or cuts != sorted(set(cuts)):
        raise ValueError("four increasing timezone-aware block boundaries required")
    roles, lower = {}, pd.Timestamp.min.tz_localize("UTC")
    for name, upper in zip(("train", "calibration", "selection", "evaluation"), cuts):
        roles[name] = ordered[(ordered.observed_at >= lower) & (ordered.observed_at < upper)
                              & (ordered.label_end < upper)].copy()
        lower = upper
    return roles
