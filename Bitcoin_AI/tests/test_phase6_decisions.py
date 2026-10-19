from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from btc_research.phase6_1 import POLICIES
from btc_research.phase6_decisions import ContinuousDecisionWorker, DecisionStore
from btc_research.phase6_runtime import SingleInstanceLock


UTC = timezone.utc


def test_decision_store_invalidates_evaluation_before_candle_close(tmp_path):
    store = DecisionStore(tmp_path / "evaluations.sqlite3")
    result = {
        "as_of": "2026-10-19T03:49:59.500000+00:00",
        "forecasts": {"BTCUSDT": {"state": "ready"}},
        "policies": {
            policy: {"opportunities": [{
                "symbol": "BTCUSDT", "cost_bps": 14.0, "expected_net_bps": -14.0,
                "expected_gross_bps": 0.0,
                "decision": "abstain", "reasons": ["threshold"], "news_event_ids": [],
            }]}
            for policy in POLICIES
        },
    }
    market = {"BTCUSDT": {"candle_close_time": "2026-10-19T03:49:59.999000+00:00"}}
    assert store.add_cycle("cycle", result, market) == 4
    assert store.count() == 4
    assert store.invalidate_noncausal() == ["cycle"]
    assert store.count() == 0
    assert store.invalidate_noncausal() == []


def test_worker_waits_until_nominal_candle_close():
    worker = ContinuousDecisionWorker.__new__(ContinuousDecisionWorker)
    close_at = datetime.now(UTC) + timedelta(milliseconds=60)
    record = {"payload": {"e": "kline", "k": {"x": True, "T": int(close_at.timestamp() * 1000)}}}
    started = datetime.now(UTC)
    asyncio.run(worker._wait_for_nominal_close(record))
    assert datetime.now(UTC) >= close_at
    assert (datetime.now(UTC) - started).total_seconds() >= .04


def test_high_frequency_quotes_are_coalesced_outside_candle_queue():
    worker = ContinuousDecisionWorker.__new__(ContinuousDecisionWorker)
    worker.queue = asyncio.Queue(maxsize=2)
    worker.quotes, worker.books = {}, {}
    worker.dropped_events = 0
    worker.on_event({"stream": "btcusdt@bookTicker", "received_at": "2026-10-19T00:00:00+00:00",
                     "payload": {"e": "bookTicker", "b": "100", "a": "101"}})
    assert worker.queue.empty() and worker.quotes["BTCUSDT"]["bid"] == 100
    worker.on_event({"stream": "btcusdt@kline_1m", "received_at": "2026-10-19T00:01:00+00:00",
                     "payload": {"e": "kline", "k": {"x": True}}})
    assert worker.queue.qsize() == 1


def test_single_instance_lock_rejects_second_owner(tmp_path):
    path = tmp_path / "service.lock"
    with SingleInstanceLock(path):
        try:
            with SingleInstanceLock(path):
                raise AssertionError("second owner was accepted")
        except RuntimeError as exc:
            assert "already running" in str(exc)
