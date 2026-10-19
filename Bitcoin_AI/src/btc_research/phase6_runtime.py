"""Supervised local runtime primitives for Phase 6.1."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .common import save_json


UTC = timezone.utc


class SingleInstanceLock:
    """OS-backed lock preventing two supervisors from writing the same runtime."""
    def __init__(self, path: Path):
        self.path = path
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+", encoding="utf-8")
        self.stream.seek(0)
        if self.path.stat().st_size == 0:
            self.stream.write(" ")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise RuntimeError("phase6.1 service is already running") from exc
        self.stream.seek(0)
        self.stream.write(str(os.getpid()))
        self.stream.truncate()
        self.stream.flush()
        return self

    def __exit__(self, *_):
        if self.stream is None:
            return
        self.stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"time": datetime.now(UTC).isoformat(), "level": record.levelname,
                           "logger": record.name, "message": record.getMessage()},
                          ensure_ascii=False, separators=(",", ":"))


def structured_logger(path: Path, *, max_bytes: int = 5_000_000, backups: int = 3) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"btc_research.phase6_1.{path}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


class Phase61Supervisor:
    def __init__(self, *, news_service, market_service, heartbeat_path: Path,
                 log_path: Path, heartbeat_seconds: float = 30, neural_worker=None,
                 decision_worker=None):
        if heartbeat_seconds <= 0:
            raise ValueError("heartbeat interval must be positive")
        self.news = news_service
        self.market = market_service
        self.heartbeat_path = heartbeat_path
        self.heartbeat_seconds = heartbeat_seconds
        self.logger = structured_logger(log_path)
        self.neural_worker = neural_worker
        self.decision_worker = decision_worker
        self.started_at: datetime | None = None
        self.stopped_at: datetime | None = None
        self._stop = asyncio.Event()

    def status(self) -> dict:
        return {"pid": os.getpid(), "started_at": self.started_at.isoformat() if self.started_at else None,
                "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
                "state": "stopped" if self.stopped_at else "running" if self.started_at else "created",
                "updated_at": datetime.now(UTC).isoformat(), "real_orders": False,
                "news_cycle_seconds": getattr(self.news, "cycle_seconds", None),
                "news_cycles_completed": getattr(self.news, "cycles_completed", None),
                "last_news_cycle_completed_at": getattr(self.news, "last_cycle_completed_at", None),
                "decision_worker": (self.decision_worker.status()
                                    if self.decision_worker is not None else
                                    {"state": "not_configured", "orders_sent": False})}

    async def _heartbeat(self) -> None:
        while not self._stop.is_set():
            save_json(self.heartbeat_path, self.status())
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.heartbeat_seconds)
            except asyncio.TimeoutError:
                pass

    async def run(self, duration_seconds: float | None = None) -> dict:
        self.started_at = datetime.now(UTC)
        self.logger.info("supervisor_started")
        tasks = [asyncio.create_task(self.news.serve()),
                 asyncio.create_task(self.market.run(duration_seconds=duration_seconds)),
                 asyncio.create_task(self._heartbeat())]
        if self.neural_worker is not None:
            tasks.append(asyncio.create_task(self.neural_worker.run()))
        if self.decision_worker is not None:
            tasks.append(asyncio.create_task(self.decision_worker.run()))
        try:
            if duration_seconds is None:
                await self._stop.wait()
            else:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=duration_seconds)
                except asyncio.TimeoutError:
                    pass
        finally:
            self.stop()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            failures = [type(result).__name__ for result in results if isinstance(result, Exception)]
            self.stopped_at = datetime.now(UTC)
            save_json(self.heartbeat_path, self.status() | {"task_failures": failures})
            self.logger.info("supervisor_stopped")
        return self.status() | {"task_failures": failures}

    def stop(self) -> None:
        self._stop.set()
        self.news.stop()
        self.market.stop()
        if self.neural_worker is not None:
            self.neural_worker.stop()
        if self.decision_worker is not None:
            self.decision_worker.stop()
