"""Causal news collection for Phase 6.

External text is always data.  It cannot alter configuration or call a broker.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Awaitable, Callable, Iterable, Protocol
from urllib.parse import urlparse


UTC = timezone.utc
ALLOWED_SENTIMENTS = {"positive", "negative", "neutral", "ambiguous", "unreliable"}
ASSET_TERMS = {
    "BTCUSDT": ("bitcoin", "btc"),
    "ETHUSDT": ("ethereum", "ether", "eth"),
    "SOLUSDT": ("solana", "sol"),
}
POSITIVE_TERMS = ("approval", "approved", "adoption", "launch", "upgrade", "surge", "record inflow")
NEGATIVE_TERMS = ("hack", "exploit", "outage", "lawsuit", "charged", "ban", "fraud", "breach", "liquidation")
PROMPT_INJECTION = re.compile(
    r"(?:ignore|disregard|override).{0,40}(?:instruction|rule|system)|"
    r"(?:execute|place|send).{0,25}(?:order|trade)|system\s*prompt|developer\s*message",
    re.IGNORECASE,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class SourcePolicy:
    source_id: str
    url: str
    reliability: str
    minimum_interval_seconds: int = 120
    content_policy: str = "feed metadata only"

    def __post_init__(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("news source must use HTTPS")
        if self.minimum_interval_seconds < 120:
            raise ValueError("source interval cannot be shorter than the Phase 6 cycle")
        if self.reliability not in {"official", "licensed_media", "project_official", "social"}:
            raise ValueError("unknown source reliability")


@dataclass(frozen=True)
class NewsEvent:
    event_id: str
    source: str
    title: str
    url: str
    published_at: datetime
    first_received_at: datetime
    analyzed_at: datetime
    affected_assets: tuple[str, ...]
    event_category: str
    summary: str
    sentiment_by_asset: dict[str, str]
    potential_intensity: float
    interpretation_confidence: float
    source_reliability: str
    confirmation_status: str
    novelty: float
    related_event_ids: tuple[str, ...] = ()
    possibly_priced_in: bool = False
    market_reaction_evidence: dict = field(default_factory=dict)
    untrusted_instructions_detected: bool = False
    content_fingerprint: str = ""

    def __post_init__(self) -> None:
        published = _utc(self.published_at)
        received = _utc(self.first_received_at)
        analyzed = _utc(self.analyzed_at)
        if received < published or analyzed < received:
            raise ValueError("event timestamp order is invalid")
        if not self.event_id or not self.source or not self.title:
            raise ValueError("event identity is incomplete")
        if urlparse(self.url).scheme not in {"http", "https"}:
            raise ValueError("event URL is invalid")
        if any(a not in ASSET_TERMS for a in self.affected_assets):
            raise ValueError("event contains asset outside the frozen universe")
        if not all(v in ALLOWED_SENTIMENTS for v in self.sentiment_by_asset.values()):
            raise ValueError("invalid sentiment")
        for value in (self.potential_intensity, self.interpretation_confidence, self.novelty):
            if not 0 <= value <= 1:
                raise ValueError("event scores must be in [0, 1]")

    def available_at(self, instant: datetime) -> bool:
        return self.published_at <= instant and self.first_received_at <= instant and self.analyzed_at <= instant

    def as_record(self) -> dict:
        row = asdict(self)
        for key in ("published_at", "first_received_at", "analyzed_at"):
            row[key] = row[key].isoformat()
        row["affected_assets"] = list(row["affected_assets"])
        row["related_event_ids"] = list(row["related_event_ids"])
        return row


@dataclass(frozen=True)
class RawFeedItem:
    source: SourcePolicy
    identifier: str
    title: str
    url: str
    summary: str
    published_at: datetime
    received_at: datetime


def _clean(value: str | None, limit: int = 4000) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _story_key(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _parse_feed_time(value: str | None) -> datetime:
    if not value:
        raise ValueError("feed item has no publication time")
    parsed = parsedate_to_datetime(value)
    return _utc(parsed)


def parse_rss(payload: bytes, source: SourcePolicy, received_at: datetime) -> list[RawFeedItem]:
    """Parse RSS/Atom without executing or rendering feed content."""
    received_at = _utc(received_at)
    root = ET.fromstring(payload)
    items = root.findall(".//item")
    if items:
        result = []
        for item in items:
            title = _clean(item.findtext("title"))
            url = _clean(item.findtext("link"), 2000)
            guid = _clean(item.findtext("guid"), 500) or url
            published = _parse_feed_time(item.findtext("pubDate") or item.findtext("date"))
            if published <= received_at:
                result.append(RawFeedItem(source, guid, title, url, _clean(item.findtext("description")), published, received_at))
        return result
    namespace = {"a": "http://www.w3.org/2005/Atom"}
    result = []
    for entry in root.findall(".//a:entry", namespace):
        link = entry.find("a:link", namespace)
        url = link.get("href", "") if link is not None else ""
        published = datetime.fromisoformat((entry.findtext("a:published", namespaces=namespace) or
                                             entry.findtext("a:updated", namespaces=namespace)).replace("Z", "+00:00"))
        if _utc(published) <= received_at:
            result.append(RawFeedItem(source, entry.findtext("a:id", default=url, namespaces=namespace),
                                      _clean(entry.findtext("a:title", namespaces=namespace)), url,
                                      _clean(entry.findtext("a:summary", namespaces=namespace)),
                                      _utc(published), received_at))
    return result


def classify_item(item: RawFeedItem, analyzed_at: datetime | None = None) -> NewsEvent:
    """Conservative deterministic baseline; it cannot authorize orders."""
    analyzed_at = _utc(analyzed_at or item.received_at)
    body = f"{item.title} {item.summary}".lower()
    malicious = bool(PROMPT_INJECTION.search(body))
    affected = tuple(asset for asset, terms in ASSET_TERMS.items()
                     if any(re.search(rf"\b{re.escape(term)}\b", body) for term in terms))
    if not affected and any(term in body for term in ("crypto", "digital asset", "interest rate", "inflation", "sec")):
        affected = tuple(ASSET_TERMS)
    pos = sum(term in body for term in POSITIVE_TERMS)
    neg = sum(term in body for term in NEGATIVE_TERMS)
    sentiment = "unreliable" if malicious else "positive" if pos > neg else "negative" if neg > pos else "ambiguous" if pos and neg else "neutral"
    category = "untrusted_content" if malicious else "security_incident" if any(x in body for x in ("hack", "exploit", "breach")) else "regulation" if any(x in body for x in ("sec", "regulation", "lawsuit", "charged")) else "macro" if any(x in body for x in ("federal reserve", "interest rate", "inflation", "employment")) else "market_news"
    intensity = min(1.0, 0.25 + 0.15 * (pos + neg) + (0.25 if category in {"security_incident", "regulation", "macro"} else 0))
    confidence = 0.0 if malicious else 0.75 if affected else 0.35
    fingerprint = hashlib.sha256(f"{item.title}\n{item.summary}\n{item.url}".encode()).hexdigest()
    identifier = item.identifier or fingerprint
    event_id = hashlib.sha256(f"{item.source.source_id}:{identifier}".encode()).hexdigest()
    return NewsEvent(
        event_id=event_id, source=item.source.source_id, title=item.title, url=item.url,
        published_at=item.published_at, first_received_at=item.received_at, analyzed_at=analyzed_at,
        affected_assets=affected, event_category=category, summary=item.summary,
        sentiment_by_asset={asset: sentiment for asset in affected}, potential_intensity=intensity,
        interpretation_confidence=confidence, source_reliability=item.source.reliability,
        confirmation_status="single_official_source" if item.source.reliability == "official" else "unconfirmed",
        novelty=1.0, possibly_priced_in=False, untrusted_instructions_detected=malicious,
        content_fingerprint=fingerprint,
    )


def assess_market_reaction(event: NewsEvent, *, measured_at: datetime,
                           pre_receive_return_bps: float, post_receive_return_bps: float,
                           volume_ratio: float, spread_bps: float,
                           priced_in_threshold_bps: float = 10) -> NewsEvent:
    """Attach observable reaction without changing direction or authorizing a trade."""
    measured_at = _utc(measured_at)
    if measured_at < event.first_received_at:
        raise ValueError("market reaction cannot be measured before receipt")
    evidence = {"measured_at": measured_at.isoformat(),
                "pre_receive_return_bps": float(pre_receive_return_bps),
                "post_receive_return_bps": float(post_receive_return_bps),
                "volume_ratio": float(volume_ratio), "spread_bps": float(spread_bps)}
    return replace(event, analyzed_at=max(event.analyzed_at, measured_at),
                   possibly_priced_in=abs(pre_receive_return_bps) >= priced_in_threshold_bps,
                   market_reaction_evidence=evidence)


def context_for_decision(events: Iterable[NewsEvent], *, symbol: str, as_of: datetime) -> dict:
    """Build a causal risk context. Directional adjustment stays zero until validated."""
    if symbol not in ASSET_TERMS:
        raise ValueError("symbol outside frozen universe")
    available = [event for event in events if symbol in event.affected_assets and event.available_at(as_of)]
    trusted = [event for event in available if not event.untrusted_instructions_detected]
    veto = any(event.source_reliability == "official" and
               event.event_category == "security_incident" and event.potential_intensity >= .5
               for event in trusted)
    return {"event_ids": tuple(event.event_id for event in trusted), "force_abstention": veto,
            "directional_adjustment_bps": 0.0,
            "ignored_untrusted_events": sum(event.untrusted_instructions_detected for event in available)}


class EventStore:
    """SQLite store with immutable first receipt and an append-only revision table."""
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, source TEXT NOT NULL, published_at TEXT NOT NULL,
                    first_received_at TEXT NOT NULL, analyzed_at TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
                    UNIQUE(event_id, fingerprint)
                );
                CREATE TABLE IF NOT EXISTS story_index (
                    story_key TEXT NOT NULL, event_id TEXT NOT NULL UNIQUE, source TEXT NOT NULL,
                    PRIMARY KEY(story_key, event_id)
                );
            """)

    def _connect(self):
        return sqlite3.connect(self.path)

    def add(self, event: NewsEvent) -> str:
        with self._connect() as db:
            existing = db.execute("SELECT fingerprint FROM events WHERE event_id=?", (event.event_id,)).fetchone()
            if existing is None:
                story_key = _story_key(event.title)
                related = tuple(row[0] for row in db.execute(
                    "SELECT event_id FROM story_index WHERE story_key=? ORDER BY event_id", (story_key,)).fetchall())
                if related:
                    event = replace(event, related_event_ids=tuple(sorted(set(event.related_event_ids + related))))
                payload = json.dumps(event.as_record(), ensure_ascii=False, sort_keys=True)
                db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?)", (
                    event.event_id, event.source, event.published_at.isoformat(),
                    event.first_received_at.isoformat(), event.analyzed_at.isoformat(),
                    event.content_fingerprint, payload))
                db.execute("INSERT INTO story_index VALUES(?,?,?)", (story_key, event.event_id, event.source))
                return "inserted"
            if existing[0] == event.content_fingerprint:
                return "duplicate"
            payload = json.dumps(event.as_record(), ensure_ascii=False, sort_keys=True)
            db.execute("INSERT OR IGNORE INTO revisions(event_id,recorded_at,fingerprint,payload) VALUES(?,?,?,?)",
                       (event.event_id, datetime.now(UTC).isoformat(), event.content_fingerprint, payload))
            return "updated"

    def available(self, as_of: datetime, asset: str | None = None) -> list[NewsEvent]:
        as_of = _utc(as_of)
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM events WHERE published_at<=? AND first_received_at<=? AND analyzed_at<=? ORDER BY first_received_at",
                              (as_of.isoformat(), as_of.isoformat(), as_of.isoformat())).fetchall()
        events = [event_from_record(json.loads(row[0])) for row in rows]
        return [event for event in events if asset is None or asset in event.affected_assets]

    def counts(self) -> dict:
        with self._connect() as db:
            events = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            revisions = db.execute("SELECT COUNT(*) FROM revisions").fetchone()[0]
        return {"events": events, "revisions": revisions}


def event_from_record(row: dict) -> NewsEvent:
    for key in ("published_at", "first_received_at", "analyzed_at"):
        row[key] = datetime.fromisoformat(row[key])
    row["affected_assets"] = tuple(row["affected_assets"])
    row["related_event_ids"] = tuple(row.get("related_event_ids", ()))
    return NewsEvent(**row)


class FeedFetcher(Protocol):
    async def __call__(self, source: SourcePolicy) -> bytes: ...


class NewsService:
    def __init__(self, sources: Iterable[SourcePolicy], store: EventStore, fetcher: FeedFetcher,
                 cycle_seconds: int = 120, clock: Callable[[], datetime] | None = None,
                 retry_delays: tuple[float, ...] = (0.1, 0.5)):
        if cycle_seconds < 120:
            raise ValueError("news cycle must be at least 120 seconds")
        self.sources = tuple(sources)
        self.store = store
        self.fetcher = fetcher
        self.cycle_seconds = cycle_seconds
        self.clock = clock or (lambda: datetime.now(UTC))
        self.retry_delays = retry_delays
        self._last_fetch: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self.cycles_completed = 0
        self.last_cycle_completed_at: str | None = None

    async def cycle(self, source_ids: set[str] | None = None) -> dict:
        if self._lock.locked():
            return {"status": "overlap_skipped", "inserted": 0, "duplicates": 0, "updated": 0, "errors": []}
        async with self._lock:
            counts = {"inserted": 0, "duplicates": 0, "updated": 0}
            errors = []
            for source in self.sources:
                if source_ids is not None and source.source_id not in source_ids:
                    continue
                now_monotonic = time.monotonic()
                last = self._last_fetch.get(source.source_id)
                if last is not None and now_monotonic - last < source.minimum_interval_seconds:
                    continue
                self._last_fetch[source.source_id] = now_monotonic
                try:
                    payload = None
                    last_error = None
                    for attempt in range(len(self.retry_delays) + 1):
                        try:
                            payload = await self.fetcher(source)
                            break
                        except Exception as exc:
                            last_error = exc
                            if attempt < len(self.retry_delays):
                                await asyncio.sleep(self.retry_delays[attempt])
                    if payload is None:
                        raise last_error or RuntimeError("feed fetch failed")
                    received = self.clock()
                    for item in parse_rss(payload, source, received):
                        outcome = self.store.add(classify_item(item, received))
                        counter = {"inserted": "inserted", "duplicate": "duplicates", "updated": "updated"}[outcome]
                        counts[counter] += 1
                except Exception as exc:
                    error = {"source": source.source_id, "error": type(exc).__name__}
                    status = getattr(exc, "status", None)
                    if status is not None:
                        error["http_status"] = int(status)
                    errors.append(error)
            completed_at = self.clock().isoformat()
            self.cycles_completed += 1
            self.last_cycle_completed_at = completed_at
            return {"status": "completed", **counts, "errors": errors,
                    "completed_at": completed_at, "cycle_number": self.cycles_completed}

    async def priority_cycle(self, source_ids: set[str] | None = None) -> dict:
        """Run immediately after an event, while retaining every source's minimum interval."""
        return await self.cycle(source_ids=source_ids)

    async def serve(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            await self.cycle()
            remaining = max(0.0, self.cycle_seconds - (time.monotonic() - started))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()
