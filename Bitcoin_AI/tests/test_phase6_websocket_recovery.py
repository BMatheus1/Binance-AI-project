import asyncio
import json

import pytest

from btc_research.live_market import BinancePublicCollector
from btc_research.phase6_decisions import ContinuousDecisionWorker


@pytest.mark.parametrize("failure", [ConnectionError("offline"), TimeoutError("handshake")])
def test_websocket_failure_invalidates_book_and_recovers(tmp_path, monkeypatch, failure):
    notifications = []
    collector = BinancePublicCollector(tmp_path, "wss://demo-stream.binance.com",
                                       "https://demo-api.binance.com",
                                       reconnect_seconds=[.001],
                                       event_callback=notifications.append)
    collector.book.valid = True
    collector.book.last_update_id = 10
    attempts = []

    class Socket:
        async def recv(self):
            collector.stop()
            return json.dumps({"stream": "btcusdt@bookTicker", "data": {"b": "1", "a": "2"}})

    class Connection:
        async def __aenter__(self):
            attempts.append(1)
            if len(attempts) == 1:
                raise failure
            assert not collector.book.valid
            return Socket()

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr("btc_research.live_market.websockets.connect", lambda *a, **kw: Connection())
    result = asyncio.run(collector.run(duration_seconds=2))
    assert len(attempts) == 2
    assert result["messages"] == 1
    assert result["reconnections"] == 1
    assert notifications[0]["payload"]["e"] == "collectorDisconnected"
    assert collector.last_error is None


def test_disconnect_removes_stale_worker_quote_and_book():
    worker = ContinuousDecisionWorker.__new__(ContinuousDecisionWorker)
    worker.quotes = {"BTCUSDT": {"bid": 1}}
    worker.books = {"BTCUSDT": {"valid": True}}
    worker.on_event({"stream": "btcusdt@collector", "payload": {"e": "collectorDisconnected"}})
    assert "BTCUSDT" not in worker.quotes
    assert "BTCUSDT" not in worker.books
