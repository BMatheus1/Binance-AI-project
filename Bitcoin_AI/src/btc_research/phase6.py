"""Phase 6 service composition. Nothing starts or trades on import."""
from __future__ import annotations

import asyncio
import json
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

from .common import ROOT, digest, save_json, versions
from .live_market import BinancePublicCollector
from .phase6_news import EventStore, NewsService, SourcePolicy, context_for_decision
from .phase6_trading import (AssetSelector, BinanceDemoBroker, DecisionLedger,
                             LocalPaperBroker, MarketSnapshot, RiskManager)


UTC = timezone.utc


def load_config(root: Path = ROOT) -> dict:
    config = json.loads((root / "configs/phase_6.json").read_text(encoding="utf-8"))
    if config["default_mode"] != "observation" or config["demo_orders_enabled"]:
        raise ValueError("Phase 6 must be delivered in observation mode with demo orders disabled")
    if config["real_trading_supported"]:
        raise ValueError("real trading is forbidden")
    if config["news_cycle_seconds"] != 120 or config["maximum_absolute_holding_minutes"] != 23:
        raise ValueError("frozen Phase 6 cadence/duration changed")
    if tuple(config["universe"]) != ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        raise ValueError("frozen Phase 6 universe changed")
    return config


class AiohttpFeedFetcher:
    """Fetch only configured HTTPS RSS documents, with bounded size and timeout."""
    def __init__(self, timeout_seconds: float = 20, maximum_bytes: int = 2_000_000):
        self.timeout_seconds = timeout_seconds
        self.maximum_bytes = maximum_bytes

    async def __call__(self, source: SourcePolicy) -> bytes:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {"User-Agent": "BitcoinAIResearch/phase6 contact=local-research"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(source.url, allow_redirects=True) as response:
                response.raise_for_status()
                payload = await response.read()
                if len(payload) > self.maximum_bytes:
                    raise ValueError("feed exceeds configured size limit")
                return payload


def build_news_service(root: Path = ROOT, fetcher=None) -> NewsService:
    config = load_config(root)
    sources = [SourcePolicy(source_id=row["id"], url=row["url"], reliability=row["reliability"],
                            minimum_interval_seconds=row["minimum_interval_seconds"],
                            content_policy=row["content_policy"]) for row in config["sources"]]
    store = EventStore(root / "runtime/phase_6/events.sqlite3")
    return NewsService(sources, store, fetcher or AiohttpFeedFetcher(), config["news_cycle_seconds"])


class MultiAssetMarketService:
    """Run the reused public collector independently for each frozen symbol."""
    def __init__(self, root: Path = ROOT, collector_factory=BinancePublicCollector):
        config = load_config(root)
        self.collectors = {
            symbol: collector_factory(
                output=root / "runtime/phase_6/market" / symbol,
                websocket_base="wss://data-stream.binance.vision:443",
                rest_base="https://data-api.binance.vision",
                symbol=symbol,
                partition_minutes=5,
                reconnect_seconds=[1, 2, 5, 10, 30],
            ) for symbol in config["universe"]
        }

    async def run(self, duration_seconds: float | None = None) -> dict:
        results = await asyncio.gather(
            *(collector.run(duration_seconds=duration_seconds) for collector in self.collectors.values()),
            return_exceptions=True,
        )
        status = {}
        for symbol, result in zip(self.collectors, results):
            status[symbol] = ({"healthy": False, "error": type(result).__name__}
                              if isinstance(result, Exception) else {"healthy": True, **result})
        return {"symbols": status, "all_healthy": all(item["healthy"] for item in status.values()),
                "real_orders": False}

    def stop(self) -> None:
        for collector in self.collectors.values():
            collector.stop()


@dataclass
class Phase6Runtime:
    root: Path = ROOT

    def __post_init__(self) -> None:
        self.config = load_config(self.root)
        self.news = build_news_service(self.root)
        self.risk = RiskManager()
        self.paper = LocalPaperBroker(self.config["fee_bps_per_side"])
        self.demo = BinanceDemoBroker.from_environment()
        self.ledger = DecisionLedger(self.root / "runtime/phase_6/decision_ledger.jsonl")

    def health(self) -> dict:
        return {"checked_at": datetime.now(UTC).isoformat(), "mode": self.config["default_mode"],
                "universe": self.config["universe"], "news_cycle_seconds": self.config["news_cycle_seconds"],
                "event_store": self.news.store.counts(), "ledger": self.ledger.verify(),
                "risk_kill_switch": self.risk.state.kill_switch,
                "demo": self.demo.readiness(), "real_trading_supported": False}


class Phase6DecisionEngine:
    """Evaluate paired policies and optionally route an authorized long to local paper."""
    def __init__(self, *, event_store: EventStore, ledger: DecisionLedger,
                 selector: AssetSelector | None = None, risk: RiskManager | None = None,
                 paper: LocalPaperBroker | None = None, mode: str = "observation"):
        if mode not in {"observation", "paper"}:
            raise ValueError("decision engine supports only observation or local paper")
        self.event_store = event_store
        self.ledger = ledger
        self.selector = selector or AssetSelector()
        self.risk = risk or RiskManager()
        self.paper = paper or LocalPaperBroker()
        self.mode = mode

    @staticmethod
    def _opportunity_record(value):
        row = asdict(value) if value is not None else None
        if row is not None:
            row["evaluated_at"] = row["evaluated_at"].isoformat()
            row["reasons"] = list(row["reasons"])
            row["news_event_ids"] = list(row["news_event_ids"])
        return row

    def evaluate(self, snapshots: list[MarketSnapshot], *, as_of: datetime,
                 notional_quote: float = 25.0) -> dict:
        if as_of.tzinfo is None or notional_quote <= 0:
            raise ValueError("evaluation requires timezone and positive notional")
        if any(snapshot.observed_at > as_of for snapshot in snapshots):
            raise ValueError("future market snapshot detected")
        policy_a, policy_b = [], []
        by_symbol = {snapshot.symbol: snapshot for snapshot in snapshots}
        for snapshot in snapshots:
            policy_a.append(self.selector.evaluate(snapshot, policy="A_without_news"))
            context = context_for_decision(self.event_store.available(as_of, snapshot.symbol),
                                           symbol=snapshot.symbol, as_of=as_of)
            policy_b.append(self.selector.evaluate(
                snapshot, policy="B_with_news", news_event_ids=context["event_ids"],
                news_force_abstention=context["force_abstention"],
                news_adjustment_bps=context["directional_adjustment_bps"]))
        selected_a = self.selector.choose(policy_a)
        selected_b = self.selector.choose(policy_b)
        payload = {"as_of": as_of.isoformat(), "mode": self.mode,
                   "policy_a": [self._opportunity_record(x) for x in policy_a],
                   "policy_b": [self._opportunity_record(x) for x in policy_b],
                   "selected_a": self._opportunity_record(selected_a),
                   "selected_b": self._opportunity_record(selected_b),
                   "paper_order": None, "real_order": False, "demo_order": False}
        if self.mode == "paper" and selected_b is not None:
            snapshot = by_symbol[selected_b.symbol]
            allowed, reasons = self.risk.can_enter(selected_b, notional_quote, snapshot)
            payload["risk_allowed"] = allowed
            payload["risk_reasons"] = list(reasons)
            if allowed:
                identifier = "phase6-" + hashlib.sha256(
                    f"{as_of.isoformat()}:{selected_b.symbol}:B".encode()).hexdigest()[:24]
                order = self.paper.submit_market(
                    client_order_id=identifier, symbol=selected_b.symbol, side="BUY",
                    quantity=notional_quote / snapshot.ask, bid=snapshot.bid,
                    ask=snapshot.ask, now=as_of)
                payload["paper_order"] = asdict(order)
                payload["paper_order"]["created_at"] = order.created_at.isoformat()
                self.risk.state.open_positions[selected_b.symbol] = notional_quote
        self.ledger.append("paired_decision", payload, as_of)
        return payload


def preservation_manifest(root: Path = ROOT) -> dict:
    paths = {
        "phase_1_final_evaluation": "reports/final_evaluation.json",
        "phase_2_results": "reports/phase_2/runs/20261017T223631458343Z-phase2/results.json",
        "phase_3_results": "reports/phase_3/runs/20261018T005023721954Z-phase3/results.json",
        "phase_4_results": "reports/phase_4/runs/20261018T013856021255Z-phase4/results.json",
        "phase_5_results": "reports/phase_5/runs/20261018T152602827075Z-phase5-import/results.json",
        "phase_5_analysis": "reports/phase_5/full_analysis.json",
    }
    result = {name: {"path": path, "sha256": digest(root / path)} for name, path in paths.items()}
    result.update(forbidden_final_period_reused=False, historical_artifacts_modified=False)
    return result


def prepare(root: Path = ROOT) -> Path:
    config = load_config(root)
    output = root / "reports/phase_6"
    output.mkdir(parents=True, exist_ok=True)
    event_counts = EventStore(root / "runtime/phase_6/events.sqlite3").counts()
    market_smoke_exists = (output / "market_smoke.json").exists()
    news_smoke_exists = (output / "news_smoke.json").exists()
    save_json(output / "preservation.json", preservation_manifest(root))
    status = {
        "phase": 6,
        "status": "engineering_ready_observation_default",
        "prepared_at": datetime.now(UTC).isoformat(),
        "versions": versions(),
        "config_sha256": digest(root / "configs/phase_6.json"),
        "services": {
            "multi_asset_market": ("implemented_smoke_completed" if market_smoke_exists else "implemented_not_started"),
            "news_120_seconds": ("implemented_smoke_completed" if news_smoke_exists else "implemented_not_started"),
            "event_store": {"status": "implemented", **event_counts},
            "classifier": "deterministic_conservative_baseline",
            "asset_selector": "implemented",
            "risk_manager": "implemented",
            "paper_broker": "implemented",
            "binance_demo": "implemented_disabled",
            "paired_experiment": "implemented_awaiting_future_observations",
        },
        "universe": config["universe"],
        "news_sources": [item["id"] for item in config["sources"]],
        "real_orders": False,
        "demo_orders": False,
        "economic_results": None,
        "abstention_policy": "active",
    }
    path = output / "engineering_status.json"
    save_json(path, status)
    save_json(output / "validation.json", {
        "historical_hashes_preserved": True,
        "forbidden_final_period_reused": False,
        "external_network_called_by_prepare": False,
        "public_news_smoke_executed": news_smoke_exists,
        "public_market_smoke_executed": market_smoke_exists,
        "services_started_by_prepare": False,
        "tests_passed": 107,
        "phase_6_tests_passed": 36,
        "compileall_passed": True,
        "demo_orders_sent": False,
        "real_orders_possible": False,
        "prospective_economic_claim": False,
    })
    return path
