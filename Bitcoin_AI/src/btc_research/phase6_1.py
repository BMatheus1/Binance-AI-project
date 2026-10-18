"""Phase 6.1 four-policy research layer.

Neural interpretation is recorded as untrusted event context. It never becomes
a price probability and this module has no broker dependency.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .common import ROOT, save_json
from .phase6_news import EventStore, NewsEvent, context_for_decision
from .phase6_nlp import (FinancialNewsInterpreter, NewsInterpretationResult,
                         load_phase61_config)
from .phase6_trading import AssetSelector, DecisionLedger, MarketSnapshot, _performance


POLICIES = ("A_quantitative", "B_conservative_news", "C_qwen3_structured_news", "D_event_market_reaction")


@dataclass(frozen=True)
class EventSignal:
    symbol: str
    observed_at: datetime
    event_types: tuple[str, ...]
    priority_news_refresh: bool


class MarketEventDetector:
    """Detect changes using only the previous and current observed snapshots."""
    def __init__(self, *, abrupt_return_bps: float = 20, volume_ratio: float = 2,
                 spread_change_bps: float = 5, liquidity_drop_fraction: float = .5):
        self.abrupt_return_bps = abrupt_return_bps
        self.volume_ratio = volume_ratio
        self.spread_change_bps = spread_change_bps
        self.liquidity_drop_fraction = liquidity_drop_fraction

    def compare(self, previous: MarketSnapshot, current: MarketSnapshot) -> EventSignal:
        if previous.symbol != current.symbol or previous.observed_at >= current.observed_at:
            raise ValueError("market event snapshots are not chronological for one symbol")
        events = []
        previous_mid = (previous.bid + previous.ask) / 2
        current_mid = (current.bid + current.ask) / 2
        if abs((current_mid / previous_mid - 1) * 10_000) >= self.abrupt_return_bps:
            events.append("abrupt_price_move")
        if previous.quote_volume_24h > 0 and current.quote_volume_24h / previous.quote_volume_24h >= self.volume_ratio:
            events.append("abnormal_volume")
        if current.spread_bps - previous.spread_bps >= self.spread_change_bps:
            events.append("spread_expansion")
        previous_depth = min(previous.bid_depth_quote, previous.ask_depth_quote)
        current_depth = min(current.bid_depth_quote, current.ask_depth_quote)
        if previous_depth > 0 and current_depth / previous_depth <= self.liquidity_drop_fraction:
            events.append("liquidity_drop")
        return EventSignal(current.symbol, current.observed_at, tuple(events), bool(events))


class FourPolicyEngine:
    def __init__(self, *, event_store: EventStore, ledger: DecisionLedger,
                 neural_classifier: FinancialNewsInterpreter,
                 selector: AssetSelector | None = None, root: Path = ROOT):
        self.event_store = event_store
        self.ledger = ledger
        self.neural = neural_classifier
        self.selector = selector or AssetSelector()
        self.config = load_phase61_config(root)
        self._cache: dict[str, NewsInterpretationResult] = {}

    def _neural_scores(self, events: list[NewsEvent]) -> dict[str, NewsInterpretationResult]:
        missing = [event for event in events if event.content_fingerprint not in self._cache]
        if missing:
            results = self.neural.interpret([f"{event.title}. {event.summary}" for event in missing])
            for event, result in zip(missing, results):
                self._cache[event.content_fingerprint] = result
        return {event.event_id: self._cache[event.content_fingerprint] for event in events}

    @staticmethod
    def _neural_veto(score: NewsInterpretationResult, symbol: str, config: dict) -> bool:
        analysis = score.analysis
        if not score.valid_generation or analysis.insufficient_information or analysis.prompt_injection_detected:
            return bool(config["invalid_or_insufficient_result_forces_abstention"])
        return any(
            impact.asset == symbol
            and impact.direction == "negative"
            and impact.confidence >= config["minimum_negative_confidence"]
            and analysis.intensity >= config["minimum_event_intensity"]
            for impact in analysis.impacts
        )

    @staticmethod
    def _reaction_confirms(event: NewsEvent, config: dict) -> bool:
        evidence = event.market_reaction_evidence
        if not evidence or event.possibly_priced_in:
            return False
        return (float(evidence.get("post_receive_return_bps", 0)) >= config["minimum_post_receive_return_bps"]
                and float(evidence.get("volume_ratio", 0)) >= config["minimum_volume_ratio"]
                and float(evidence.get("spread_bps", float("inf"))) <= config["maximum_confirmation_spread_bps"])

    @staticmethod
    def _record_opportunity(value) -> dict:
        row = asdict(value)
        row["evaluated_at"] = row["evaluated_at"].isoformat()
        row["reasons"] = list(row["reasons"])
        row["news_event_ids"] = list(row["news_event_ids"])
        return row

    def evaluate(self, snapshots: list[MarketSnapshot], *, as_of: datetime) -> dict:
        if as_of.tzinfo is None or any(snapshot.observed_at > as_of for snapshot in snapshots):
            raise ValueError("future or timezone-free policy evaluation")
        policies = {name: [] for name in POLICIES}
        neural_records = {}
        for snapshot in snapshots:
            events = self.event_store.available(as_of, snapshot.symbol)
            conservative = context_for_decision(events, symbol=snapshot.symbol, as_of=as_of)
            scores = self._neural_scores(events)
            neural_records.update({event_id: score.as_record()
                                   for event_id, score in scores.items()})
            neural_veto = any(self._neural_veto(score, snapshot.symbol, self.config["policy_c"])
                              for score in scores.values())
            reaction_confirmed = any(self._reaction_confirms(event, self.config["policy_d"]) for event in events)
            reaction_veto = bool(events) and not reaction_confirmed
            policies["A_quantitative"].append(
                self.selector.evaluate(snapshot, policy="A_quantitative"))
            policies["B_conservative_news"].append(
                self.selector.evaluate(snapshot, policy="B_conservative_news",
                                       news_event_ids=conservative["event_ids"],
                                       news_force_abstention=conservative["force_abstention"]))
            policies["C_qwen3_structured_news"].append(
                self.selector.evaluate(snapshot, policy="C_qwen3_structured_news",
                                       news_event_ids=tuple(scores), news_force_abstention=neural_veto))
            policies["D_event_market_reaction"].append(
                self.selector.evaluate(snapshot, policy="D_event_market_reaction",
                                       news_event_ids=tuple(scores),
                                       news_force_abstention=(neural_veto or reaction_veto)))
        selected = {name: self.selector.choose(items) for name, items in policies.items()}
        payload = {
            "as_of": as_of.isoformat(), "policies": {
                name: {"opportunities": [self._record_opportunity(item) for item in items],
                       "selected": self._record_opportunity(selected[name]) if selected[name] else None}
                for name, items in policies.items()},
            "neural_interpretation": neural_records,
            "neural_confidence_is_price_probability": False,
            "orders_sent": False,
        }
        self.ledger.append("phase6_1_four_policy_decision", payload, as_of)
        return payload


def evaluate_four_policies(rows: list[dict]) -> dict:
    required = {"instant", *POLICIES}
    if any(not required.issubset(row) for row in rows):
        raise ValueError("four-policy row is incomplete")
    if len({row["instant"] for row in rows}) != len(rows):
        raise ValueError("duplicate policy instant")
    result = {"same_observations": True, "observations": len(rows), "policies": {}}
    for policy in POLICIES:
        returns = [float(row[policy]) for row in rows if row[policy] is not None]
        result["policies"][policy] = _performance(returns, len(rows))
    result.update(prospective_claim_allowed=False,
                  limitation="Engineering evaluator only; future observations are required.")
    return result


def extension_counterfactual(*, original_close_net: float, actual_close_net: float,
                             extended: bool, original_minutes: int, actual_minutes: int) -> dict:
    if not 1 <= original_minutes <= 20 or actual_minutes > 23 or actual_minutes < original_minutes:
        raise ValueError("invalid original/actual duration")
    if extended and actual_minutes == original_minutes:
        raise ValueError("extended position must have a later actual close")
    return {"extended": extended, "original_close_net": float(original_close_net),
            "actual_close_net": float(actual_close_net),
            "extension_incremental_net": float(actual_close_net - original_close_net),
            "original_minutes": original_minutes, "actual_minutes": actual_minutes}


def save_four_policy_evaluation(rows: list[dict], path: Path) -> dict:
    result = evaluate_four_policies(rows)
    save_json(path, result)
    return result
