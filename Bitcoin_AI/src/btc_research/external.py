"""Contratos futuros; nenhuma rede, credencial ou monitor iniciado."""
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol


@dataclass(frozen=True)
class ExternalEvent:
    source: str
    identifier: str
    title: str
    permitted_content: str
    published_at: datetime
    received_at: datetime
    category: str
    reliability: str
    relevance_hypothesis: str

    def __post_init__(self):
        if self.published_at.tzinfo is None or self.received_at.tzinfo is None or self.received_at < self.published_at:
            raise ValueError("Evento requer horários com timezone e recebimento >= publicação")

    def available_at(self, time: datetime) -> bool:
        return self.published_at <= time and self.received_at <= time


class ClosedCandleSource(Protocol):
    def closed_candles(self) -> Iterable[dict]: ...


class EventSource(Protocol):
    def events(self) -> Iterable[ExternalEvent]: ...
