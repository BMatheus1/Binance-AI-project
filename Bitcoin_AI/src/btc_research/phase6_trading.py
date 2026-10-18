"""Asset selection, risk, paper execution and demo-only broker boundaries."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urlencode, urlparse


UTC = timezone.utc
UNIVERSE = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DEMO_REST_BASE = "https://demo-api.binance.com/api"
PRODUCTION_HOSTS = {"api.binance.com", "api-gcp.binance.com", "api1.binance.com", "api2.binance.com", "api3.binance.com", "api4.binance.com"}


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    observed_at: datetime
    bid: float
    ask: float
    quote_volume_24h: float
    bid_depth_quote: float
    ask_depth_quote: float
    volatility_bps: float
    expected_gross_return_bps: float
    signal_confidence: float
    data_complete: bool = True
    stale_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.symbol not in UNIVERSE or self.observed_at.tzinfo is None:
            raise ValueError("snapshot outside frozen universe or without timezone")
        if min(self.bid, self.ask, self.quote_volume_24h, self.bid_depth_quote, self.ask_depth_quote) < 0 or self.ask < self.bid:
            raise ValueError("invalid market values")
        if not 0 <= self.signal_confidence <= 1:
            raise ValueError("signal confidence must be in [0,1]")

    @property
    def spread_bps(self) -> float:
        mid = (self.bid + self.ask) / 2
        return (self.ask - self.bid) / mid * 10_000 if mid else math.inf


@dataclass(frozen=True)
class SelectionConfig:
    minimum_quote_volume: float = 1_000_000
    minimum_depth_quote: float = 10_000
    maximum_spread_bps: float = 10
    maximum_stale_seconds: float = 5
    fee_bps_per_side: float = 5
    slippage_bps_per_side: float = 2
    minimum_net_edge_bps: float = 2


@dataclass(frozen=True)
class Opportunity:
    symbol: str
    evaluated_at: datetime
    policy: str
    eligible: bool
    decision: str
    expected_gross_bps: float
    expected_net_bps: float
    cost_bps: float
    confidence: float
    reasons: tuple[str, ...]
    news_event_ids: tuple[str, ...] = ()


class AssetSelector:
    def __init__(self, config: SelectionConfig = SelectionConfig()):
        self.config = config

    def evaluate(self, snapshot: MarketSnapshot, *, policy: str, news_event_ids: tuple[str, ...] = (),
                 news_force_abstention: bool = False, news_adjustment_bps: float = 0.0) -> Opportunity:
        allowed_policies = {"A_without_news", "B_with_news", "A_quantitative",
                            "B_conservative_news", "C_finbert_sentiment",
                            "C_qwen3_structured_news",
                            "D_event_market_reaction"}
        if policy not in allowed_policies:
            raise ValueError("unknown experiment policy")
        if policy in {"A_without_news", "A_quantitative"} and (news_event_ids or news_force_abstention or news_adjustment_bps):
            raise ValueError("policy A cannot consume news")
        reasons = []
        if not snapshot.data_complete:
            reasons.append("incomplete_market_data")
        if snapshot.stale_seconds > self.config.maximum_stale_seconds:
            reasons.append("stale_market_data")
        if snapshot.spread_bps > self.config.maximum_spread_bps:
            reasons.append("spread_too_wide")
        if snapshot.quote_volume_24h < self.config.minimum_quote_volume:
            reasons.append("insufficient_volume")
        if min(snapshot.bid_depth_quote, snapshot.ask_depth_quote) < self.config.minimum_depth_quote:
            reasons.append("insufficient_depth")
        if news_force_abstention:
            reasons.append("news_risk_veto")
        cost = snapshot.spread_bps + 2 * (self.config.fee_bps_per_side + self.config.slippage_bps_per_side)
        net = snapshot.expected_gross_return_bps + news_adjustment_bps - cost
        if net < self.config.minimum_net_edge_bps:
            reasons.append("no_positive_net_edge")
        eligible = not reasons
        return Opportunity(snapshot.symbol, snapshot.observed_at, policy, eligible,
                           "buy" if eligible else "abstain", snapshot.expected_gross_return_bps,
                           net, cost, snapshot.signal_confidence, tuple(reasons), news_event_ids)

    @staticmethod
    def choose(opportunities: list[Opportunity]) -> Opportunity | None:
        eligible = [item for item in opportunities if item.eligible]
        return max(eligible, key=lambda item: (item.expected_net_bps, item.confidence), default=None)


@dataclass(frozen=True)
class RiskLimits:
    maximum_open_positions: int = 1
    maximum_asset_exposure_quote: float = 100
    maximum_total_exposure_quote: float = 200
    maximum_daily_loss_quote: float = 10
    maximum_drawdown_quote: float = 20
    maximum_pair_correlation: float = .85
    maximum_spread_bps: float = 10
    minimum_depth_quote: float = 10_000
    maximum_planned_minutes: int = 20
    maximum_extension_minutes: int = 3
    maximum_absolute_minutes: int = 23


@dataclass
class RiskState:
    open_positions: dict[str, float] = field(default_factory=dict)
    realized_pnl_today: float = 0.0
    equity_peak: float = 0.0
    equity: float = 0.0
    data_healthy: bool = True
    kill_switch: bool = False
    day: date = field(default_factory=lambda: datetime.now(UTC).date())


class RiskManager:
    def __init__(self, limits: RiskLimits = RiskLimits()):
        self.limits = limits
        self.state = RiskState()

    def engage_kill_switch(self) -> None:
        self.state.kill_switch = True

    def can_enter(self, opportunity: Opportunity, notional: float, snapshot: MarketSnapshot,
                  correlations: dict[tuple[str, str], float] | None = None) -> tuple[bool, tuple[str, ...]]:
        reasons = []
        if self.state.kill_switch:
            reasons.append("kill_switch")
        if not self.state.data_healthy or not snapshot.data_complete:
            reasons.append("data_unhealthy")
        if not opportunity.eligible or opportunity.decision != "buy":
            reasons.append("opportunity_ineligible")
        if len(self.state.open_positions) >= self.limits.maximum_open_positions:
            reasons.append("position_limit")
        if notional > self.limits.maximum_asset_exposure_quote:
            reasons.append("asset_exposure_limit")
        if sum(self.state.open_positions.values()) + notional > self.limits.maximum_total_exposure_quote:
            reasons.append("total_exposure_limit")
        for existing in self.state.open_positions:
            pair = tuple(sorted((existing, opportunity.symbol)))
            if correlations and abs(correlations.get(pair, 0.0)) > self.limits.maximum_pair_correlation:
                reasons.append("correlation_limit")
                break
        if self.state.realized_pnl_today <= -self.limits.maximum_daily_loss_quote:
            reasons.append("daily_loss_limit")
        if self.state.equity_peak - self.state.equity >= self.limits.maximum_drawdown_quote:
            reasons.append("drawdown_limit")
        if snapshot.spread_bps > self.limits.maximum_spread_bps:
            reasons.append("spread_limit")
        if min(snapshot.bid_depth_quote, snapshot.ask_depth_quote) < self.limits.minimum_depth_quote:
            reasons.append("liquidity_limit")
        return not reasons, tuple(reasons)

    def may_extend(self, *, opened_at: datetime, planned_close_at: datetime, now: datetime,
                   unrealized_net_quote: float, signal_favorable: bool,
                   estimated_benefit_quote: float, additional_risk_quote: float) -> tuple[bool, str]:
        for value in (opened_at, planned_close_at, now):
            if value.tzinfo is None:
                raise ValueError("position times require timezone")
        planned = (planned_close_at - opened_at).total_seconds() / 60
        elapsed = (now - opened_at).total_seconds() / 60
        if planned < 1 or planned > self.limits.maximum_planned_minutes:
            return False, "invalid_original_horizon"
        if elapsed >= self.limits.maximum_absolute_minutes:
            return False, "absolute_duration_limit"
        if now < planned_close_at:
            return False, "original_horizon_not_reached"
        if now > planned_close_at + timedelta(minutes=self.limits.maximum_extension_minutes):
            return False, "extension_window_expired"
        if unrealized_net_quote <= 0:
            return False, "position_not_net_profitable"
        if not signal_favorable:
            return False, "signal_deteriorated"
        if estimated_benefit_quote <= additional_risk_quote:
            return False, "benefit_not_above_risk"
        if self.state.kill_switch or not self.state.data_healthy:
            return False, "risk_state_blocks_extension"
        return True, "extension_allowed"

    def close_reason(self, *, opened_at: datetime, planned_close_at: datetime, now: datetime,
                     stop_loss_hit: bool = False, signal_deteriorated: bool = False,
                     spread_abnormal: bool = False) -> str | None:
        if self.state.kill_switch:
            return "kill_switch"
        if not self.state.data_healthy:
            return "data_failure"
        if stop_loss_hit:
            return "stop_loss"
        if spread_abnormal:
            return "spread_abnormal"
        if signal_deteriorated:
            return "signal_deteriorated"
        if now >= opened_at + timedelta(minutes=self.limits.maximum_absolute_minutes):
            return "absolute_duration_limit"
        if now >= planned_close_at:
            return "planned_horizon"
        return None


@dataclass(frozen=True)
class PaperOrder:
    client_order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    fee_quote: float
    status: str
    created_at: datetime
    paper: bool = True


class LocalPaperBroker:
    def __init__(self, fee_bps: float = 5):
        self.fee_bps = fee_bps
        self.orders: dict[str, PaperOrder] = {}

    def submit_market(self, *, client_order_id: str, symbol: str, side: str,
                      quantity: float, bid: float, ask: float, now: datetime | None = None) -> PaperOrder:
        if client_order_id in self.orders:
            return self.orders[client_order_id]
        if symbol not in UNIVERSE or side not in {"BUY", "SELL"} or quantity <= 0 or min(bid, ask) <= 0:
            raise ValueError("invalid paper order")
        price = ask if side == "BUY" else bid
        order = PaperOrder(client_order_id, symbol, side, quantity, price,
                           price * quantity * self.fee_bps / 10_000, "FILLED", now or datetime.now(UTC))
        self.orders[client_order_id] = order
        return order

    def cancel(self, client_order_id: str) -> PaperOrder:
        order = self.orders[client_order_id]
        if order.status == "FILLED":
            raise ValueError("filled paper order cannot be cancelled")
        return order


class DemoTransport(Protocol):
    def __call__(self, method: str, url: str, headers: dict[str, str], params: dict) -> dict: ...


class BinanceDemoBroker:
    """Demo-only API adapter. There is deliberately no production endpoint fallback."""
    def __init__(self, *, enabled: bool = False, base_url: str = DEMO_REST_BASE,
                 api_key: str | None = None, api_secret: str | None = None,
                 transport: DemoTransport | None = None, clock_ms: Callable[[], int] | None = None):
        parsed = urlparse(base_url)
        if base_url.rstrip("/") != DEMO_REST_BASE or parsed.hostname in PRODUCTION_HOSTS:
            raise ValueError("only the official Binance Demo REST endpoint is permitted")
        self.base_url = DEMO_REST_BASE
        self.enabled = enabled
        self.api_key = api_key
        self._api_secret = api_secret
        self.transport = transport
        self.clock_ms = clock_ms or (lambda: int(datetime.now(UTC).timestamp() * 1000))
        self._submitted_ids: set[str] = set()

    @classmethod
    def from_environment(cls, transport: DemoTransport | None = None) -> "BinanceDemoBroker":
        enabled = os.getenv("BITCOIN_AI_ENABLE_DEMO_ORDERS") == "I_UNDERSTAND_DEMO_ONLY"
        return cls(enabled=enabled, api_key=os.getenv("BINANCE_DEMO_API_KEY"),
                   api_secret=os.getenv("BINANCE_DEMO_API_SECRET"), transport=transport)

    def readiness(self) -> dict:
        return {"mode": "binance_demo", "enabled": self.enabled,
                "credentials_present": bool(self.api_key and self._api_secret),
                "transport_present": self.transport is not None,
                "base_url": self.base_url, "production_endpoint_accessible": False,
                "ready": bool(self.enabled and self.api_key and self._api_secret and self.transport)}

    def _call(self, method: str, path: str, params: dict, *, signed: bool = True) -> dict:
        if not self.enabled:
            raise RuntimeError("Binance Demo orders are disabled")
        if not self.api_key or not self._api_secret or self.transport is None:
            raise RuntimeError("Binance Demo credentials/transport are incomplete")
        values = dict(params)
        if signed:
            values.update(timestamp=self.clock_ms(), recvWindow=5000)
            signature = hmac.new(self._api_secret.encode(), urlencode(values).encode(), hashlib.sha256).hexdigest()
            values["signature"] = signature
        return self.transport(method, f"{self.base_url}{path}", {"X-MBX-APIKEY": self.api_key}, values)

    def balances(self) -> dict:
        return self._call("GET", "/v3/account", {})

    def exchange_info(self, symbol: str) -> dict:
        return self._call("GET", "/v3/exchangeInfo", {"symbol": symbol}, signed=False)

    def submit_market(self, *, symbol: str, side: str, quantity: str, client_order_id: str) -> dict:
        if symbol not in UNIVERSE or side not in {"BUY", "SELL"}:
            raise ValueError("invalid demo order")
        if client_order_id in self._submitted_ids:
            raise ValueError("duplicate client order id")
        result = self._call("POST", "/v3/order", {"symbol": symbol, "side": side, "type": "MARKET",
                                                    "quantity": quantity, "newClientOrderId": client_order_id})
        self._submitted_ids.add(client_order_id)
        return self.classify_order_response(result)

    def order_status(self, *, symbol: str, client_order_id: str) -> dict:
        return self._call("GET", "/v3/order", {"symbol": symbol, "origClientOrderId": client_order_id})

    def cancel(self, *, symbol: str, client_order_id: str) -> dict:
        return self._call("DELETE", "/v3/order", {"symbol": symbol, "origClientOrderId": client_order_id})

    @staticmethod
    def classify_order_response(response: dict) -> dict:
        status = response.get("status")
        known = {"NEW", "PENDING_NEW", "PARTIALLY_FILLED", "FILLED", "PENDING_CANCEL",
                 "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}
        if status not in known:
            raise ValueError("unknown or missing demo order status")
        return {**response, "execution_state": (
            "filled" if status == "FILLED" else
            "partial" if status == "PARTIALLY_FILLED" else
            "rejected" if status in {"REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"} else
            "cancelled" if status == "CANCELED" else "pending"
        ), "assumed_filled": status == "FILLED"}


class DecisionLedger:
    """Generic append-only hash chain for every opportunity, abstention, order and fill."""
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    @staticmethod
    def _hash(row: dict) -> str:
        return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

    def verify(self) -> dict:
        previous = "GENESIS"
        ids = set()
        for index, row in enumerate(self.records()):
            stored = row.get("record_hash")
            body = {k: v for k, v in row.items() if k != "record_hash"}
            if row.get("previous_hash") != previous or stored != self._hash(body):
                raise ValueError(f"ledger tampered at record {index}")
            if row["record_id"] in ids:
                raise ValueError("duplicate ledger record id")
            ids.add(row["record_id"])
            previous = stored
        return {"records": len(ids), "head_hash": previous}

    def append(self, record_type: str, payload: dict, recorded_at: datetime | None = None) -> dict:
        state = self.verify()
        row = {"record_id": str(uuid.uuid4()), "record_type": record_type,
               "recorded_at": (recorded_at or datetime.now(UTC)).isoformat(),
               "payload": payload, "previous_hash": state["head_hash"]}
        row["record_hash"] = self._hash(row)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return row


def _performance(returns: list[float], decisions: int) -> dict:
    wins = [x for x in returns if x > 0]
    losses = [x for x in returns if x < 0]
    curve, peak, drawdown = 0.0, 0.0, 0.0
    for value in returns:
        curve += value
        peak = max(peak, curve)
        drawdown = max(drawdown, peak - curve)
    return {"decisions": decisions, "trades": len(returns), "abstentions": decisions - len(returns),
            "abstention_rate": (decisions - len(returns)) / decisions if decisions else None,
            "net_return": sum(returns), "expectancy": sum(returns) / len(returns) if returns else None,
            "win_rate": len(wins) / len(returns) if returns else None,
            "average_win": sum(wins) / len(wins) if wins else None,
            "average_loss": sum(losses) / len(losses) if losses else None,
            "profit_factor": sum(wins) / -sum(losses) if losses else None,
            "max_drawdown": drawdown}


def evaluate_paired(rows: list[dict]) -> dict:
    """Evaluate policies on identical pre-registered instants only."""
    required = {"instant", "return_a", "return_b"}
    if any(not required.issubset(row) for row in rows):
        raise ValueError("paired experiment row is incomplete")
    if len({row["instant"] for row in rows}) != len(rows):
        raise ValueError("duplicate experiment instant")
    a = [float(row["return_a"]) for row in rows if row["return_a"] is not None]
    b = [float(row["return_b"]) for row in rows if row["return_b"] is not None]
    paired_delta = [float(row["return_b"] or 0) - float(row["return_a"] or 0) for row in rows]
    return {"same_observations": True, "A_without_news": _performance(a, len(rows)),
            "B_with_news": _performance(b, len(rows)),
            "paired_net_delta": sum(paired_delta),
            "paired_mean_delta": sum(paired_delta) / len(paired_delta) if paired_delta else None,
            "prospective_claim_allowed": False,
            "limitation": "No inference until the frozen minimum of future days and resolved trades is reached."}


def evaluate_simple_benchmarks(rows: list[dict], seed: int = 42) -> dict:
    """Reproducible long-only benchmarks on precomputed causal signals and costed returns."""
    required = {"net_forward_return", "reference_trade", "momentum_signal", "reversal_signal"}
    if any(not required.issubset(row) for row in rows):
        raise ValueError("benchmark row is incomplete")
    n_reference = sum(bool(row["reference_trade"]) for row in rows)
    eligible_indices = list(range(len(rows)))
    rng = random.Random(seed)
    random_indices = set(rng.sample(eligible_indices, min(n_reference, len(eligible_indices))))
    policies = {
        "reference_frequency_random": [float(row["net_forward_return"]) for i, row in enumerate(rows) if i in random_indices],
        "buy_and_hold_each_interval": [float(row["net_forward_return"]) for row in rows],
        "momentum_long_only": [float(row["net_forward_return"]) for row in rows if float(row["momentum_signal"]) > 0],
        "mean_reversion_long_only": [float(row["net_forward_return"]) for row in rows if float(row["reversal_signal"]) > 0],
    }
    return {name: _performance(values, len(rows)) for name, values in policies.items()}
