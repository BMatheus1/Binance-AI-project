"""Coletor público Binance Spot para observação em sombra, sem autenticação."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import websockets


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PartitionedJsonl:
    def __init__(self, root: Path, partition_minutes: int = 5, flush_records: int = 100,
                 flush_seconds: float = 1.0):
        self.root = root
        self.partition_minutes = partition_minutes
        self.flush_records = flush_records
        self.flush_seconds = flush_seconds
        self.buffers: dict[Path, list[str]] = {}
        self.buffered_records = 0
        self.last_flush = time.monotonic()

    def append(self, stream: str, record: dict) -> Path:
        now = datetime.fromisoformat(record["received_at"])
        minute = now.minute - now.minute % self.partition_minutes
        path = self.root / stream / now.strftime("%Y-%m-%d") / f"{now:%H}-{minute:02d}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.buffers.setdefault(path, []).append(json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
        self.buffered_records += 1
        if self.buffered_records >= self.flush_records or time.monotonic() - self.last_flush >= self.flush_seconds:
            self.flush()
        return path

    def flush(self) -> None:
        for path, lines in list(self.buffers.items()):
            if not lines:
                continue
            with path.open("a", encoding="utf-8", newline="\n") as output:
                output.writelines(lines)
                output.flush()
                os.fsync(output.fileno())
        self.buffers.clear()
        self.buffered_records = 0
        self.last_flush = time.monotonic()


@dataclass
class SequenceMonitor:
    last_agg_id: int | None = None
    duplicates: int = 0
    gap_events: int = 0
    missing_ids: int = 0

    def observe_aggtrade(self, value: int) -> dict:
        status = "first"
        if self.last_agg_id is not None:
            if value == self.last_agg_id:
                self.duplicates += 1
                status = "duplicate"
            elif value > self.last_agg_id + 1:
                self.gap_events += 1
                self.missing_ids += value - self.last_agg_id - 1
                status = "gap"
            elif value < self.last_agg_id:
                status = "out_of_order"
        self.last_agg_id = max(value, self.last_agg_id if self.last_agg_id is not None else value)
        return {"status": status, "duplicates": self.duplicates, "gap_events": self.gap_events,
                "missing_ids": self.missing_ids}


@dataclass
class LocalOrderBook:
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    last_update_id: int | None = None
    valid: bool = False
    buffer: list[dict] = field(default_factory=list)
    invalidations: int = 0

    def buffer_event(self, event: dict) -> None:
        self.buffer.append(event)

    @staticmethod
    def _side(levels: dict[float, float], updates: list[list[str]]) -> None:
        for price_text, quantity_text in updates:
            price, quantity = float(price_text), float(quantity_text)
            if quantity == 0:
                levels.pop(price, None)
            else:
                levels[price] = quantity

    def install_snapshot(self, snapshot: dict) -> None:
        last = int(snapshot["lastUpdateId"])
        self.bids = {float(p): float(q) for p, q in snapshot["bids"] if float(q) != 0}
        self.asks = {float(p): float(q) for p, q in snapshot["asks"] if float(q) != 0}
        self.last_update_id, self.valid = last, False
        pending = [e for e in self.buffer if int(e["u"]) > last]
        self.buffer = []
        if not pending:
            return
        first = pending.pop(0)
        if not (int(first["U"]) <= last + 1 <= int(first["u"])):
            self.invalidate()
            return
        self._apply_unchecked(first)
        self.valid = True
        for event in pending:
            if not self.apply(event):
                return

    def _apply_unchecked(self, event: dict) -> None:
        self._side(self.bids, event.get("b", []))
        self._side(self.asks, event.get("a", []))
        self.last_update_id = int(event["u"])

    def apply(self, event: dict) -> bool:
        if self.last_update_id is None:
            self.buffer_event(event)
            return False
        if not self.valid:
            if int(event["u"]) <= self.last_update_id:
                return False
            if not (int(event["U"]) <= self.last_update_id + 1 <= int(event["u"])):
                self.invalidate()
                return False
            self._apply_unchecked(event)
            self.valid = True
            return True
        if int(event["u"]) <= self.last_update_id:
            return True
        if int(event["U"]) > self.last_update_id + 1:
            self.invalidate()
            return False
        self._apply_unchecked(event)
        return True

    def invalidate(self) -> None:
        self.valid = False
        self.last_update_id = None
        self.bids.clear()
        self.asks.clear()
        self.buffer.clear()
        self.invalidations += 1

    def top(self) -> dict:
        if not self.valid or not self.bids or not self.asks:
            return {"valid": False, "reason": "depth_not_synchronized"}
        bid, ask = max(self.bids), min(self.asks)
        bid_levels = sorted(self.bids.items(), reverse=True)[:20]
        ask_levels = sorted(self.asks.items())[:20]
        return {"valid": True, "bid": bid, "ask": ask, "spread": ask - bid,
                "spread_bps": (ask - bid) / ((ask + bid) / 2) * 10_000,
                "bid_depth_quote": sum(price * quantity for price, quantity in bid_levels),
                "ask_depth_quote": sum(price * quantity for price, quantity in ask_levels),
                "depth_levels": 20,
                "last_update_id": self.last_update_id}


class BinancePublicCollector:
    def __init__(self, output: Path, websocket_base: str, rest_base: str, symbol: str = "BTCUSDT",
                 partition_minutes: int = 5, reconnect_seconds: list[int] | None = None,
                 event_callback=None):
        self.symbol = symbol.lower()
        self.websocket_base = websocket_base.rstrip("/")
        self.rest_base = rest_base.rstrip("/")
        self.storage = PartitionedJsonl(output, partition_minutes)
        self.monitor = SequenceMonitor()
        self.book = LocalOrderBook()
        self.reconnect_seconds = reconnect_seconds or [1, 2, 5, 10, 30]
        self.event_callback = event_callback
        self.stop_event = asyncio.Event()
        self.reconnections = 0
        self.messages = 0
        self.last_message_at: str | None = None
        self.last_book_at: str | None = None
        self.last_reconnect_at: str | None = None
        self.last_error: str | None = None
        self.connection_state = "disconnected"
        self.last_error_details: dict | None = None

    @property
    def url(self) -> str:
        streams = "/".join([f"{self.symbol}@aggTrade", f"{self.symbol}@kline_1m",
                            f"{self.symbol}@bookTicker", f"{self.symbol}@depth@100ms"])
        return f"{self.websocket_base}/stream?streams={streams}"

    async def _snapshot(self) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.rest_base}/api/v3/depth",
                                   params={"symbol": self.symbol.upper(), "limit": 5000}, timeout=20) as response:
                response.raise_for_status()
                return await response.json()

    async def _handle(self, envelope: dict) -> None:
        received = utc_now()
        stream, payload = envelope.get("stream", "unknown"), envelope.get("data", envelope)
        event_ms = payload.get("E", payload.get("T"))
        record = {"stream": stream, "received_at": received.isoformat(),
                  "source_event_time": (datetime.fromtimestamp(event_ms / 1000, timezone.utc).isoformat()
                                        if isinstance(event_ms, (int, float)) else None),
                  "payload": payload}
        if payload.get("e") == "aggTrade":
            record["sequence"] = self.monitor.observe_aggtrade(int(payload["a"]))
        if payload.get("e") == "depthUpdate":
            if self.book.last_update_id is None:
                self.book.buffer_event(payload)
                try:
                    self.book.install_snapshot(await self._snapshot())
                except Exception as exc:
                    self.book.invalidate()
                    record["depth_error"] = type(exc).__name__
            elif not self.book.apply(payload):
                record["depth_error"] = "sequence_gap_invalidated"
            record["local_book"] = self.book.top()
            self.last_book_at = received.isoformat() if self.book.valid else None
        self.storage.append(stream.replace("@", "_"), record)
        if self.event_callback is not None:
            callback_result = self.event_callback(record)
            if inspect.isawaitable(callback_result):
                await callback_result

    async def run(self, duration_seconds: float | None = None) -> dict:
        started = asyncio.get_running_loop().time()
        attempt = 0
        messages = 0
        while not self.stop_event.is_set():
            if duration_seconds is not None and asyncio.get_running_loop().time() - started >= duration_seconds:
                break
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20, close_timeout=5) as socket:
                    self.connection_state = "connected"
                    while not self.stop_event.is_set():
                        remaining = None if duration_seconds is None else max(.01, duration_seconds - (asyncio.get_running_loop().time() - started))
                        if remaining is not None and remaining <= .01:
                            break
                        timeout = min(30.0, remaining) if remaining is not None else 30.0
                        raw = await asyncio.wait_for(socket.recv(), timeout=timeout)
                        await self._handle(json.loads(raw))
                        messages += 1
                        self.messages += 1
                        self.last_message_at = utc_now().isoformat()
                        self.last_error = None
                        self.last_error_details = None
                        attempt = 0
            except Exception as exc:
                if (isinstance(exc, asyncio.TimeoutError) and duration_seconds is not None and
                        asyncio.get_running_loop().time() - started >= duration_seconds):
                    break
                self.connection_state = "disconnected"
                self.book.invalidate()
                self.reconnections += 1
                self.last_reconnect_at = utc_now().isoformat()
                self.last_error = type(exc).__name__
                received_close = getattr(exc, "rcvd", None)
                self.last_error_details = {
                    "error_type": type(exc).__name__,
                    "errno": getattr(exc, "errno", None),
                    "winerror": getattr(exc, "winerror", None),
                    "received_close_code": getattr(received_close, "code", None),
                }
                self.storage.append("collector", {"received_at": utc_now().isoformat(), "event": "reconnect",
                                                    "error": type(exc).__name__, "attempt": attempt,
                                                    "details": self.last_error_details})
                if self.event_callback is not None:
                    notification = {"stream": f"{self.symbol}@collector",
                                    "received_at": self.last_reconnect_at,
                                    "payload": {"e": "collectorDisconnected"}}
                    callback_result = self.event_callback(notification)
                    if inspect.isawaitable(callback_result):
                        await callback_result
                delay = self.reconnect_seconds[min(attempt, len(self.reconnect_seconds) - 1)]
                attempt += 1
                if duration_seconds is not None and asyncio.get_running_loop().time() - started + delay >= duration_seconds:
                    break
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
        self.connection_state = "stopped"
        self.storage.flush()
        return {"messages": messages, "reconnections": self.reconnections,
                "aggtrade_duplicates": self.monitor.duplicates, "aggtrade_gap_events": self.monitor.gap_events,
                "aggtrade_missing_ids": self.monitor.missing_ids, "depth_invalidations": self.book.invalidations,
                "book": self.book.top(), "real_orders": False}

    def status(self) -> dict:
        """Live counters used by the long-running prospective audit."""
        return {"symbol": self.symbol.upper(), "messages": self.messages,
                "connection_state": self.connection_state,
                "reconnections": self.reconnections,
                "last_message_at": self.last_message_at,
                "last_reconnect_at": self.last_reconnect_at,
                "last_error": self.last_error,
                "last_error_details": self.last_error_details,
                "aggtrade_duplicates": self.monitor.duplicates,
                "aggtrade_gap_events": self.monitor.gap_events,
                "aggtrade_missing_ids": self.monitor.missing_ids,
                "depth_invalidations": self.book.invalidations,
                "book_valid": self.book.valid, "book": self.book.top(),
                "last_book_at": self.last_book_at}

    def stop(self) -> None:
        self.stop_event.set()
