"""Contratos futuros; nenhuma rede, credencial ou monitor iniciado."""
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
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
    relevance_estimate: float | None = None

    def __post_init__(self):
        if self.published_at.tzinfo is None or self.received_at.tzinfo is None or self.received_at < self.published_at:
            raise ValueError("Evento requer horários com timezone e recebimento >= publicação")
        if self.relevance_estimate is not None and not 0 <= self.relevance_estimate <= 1:
            raise ValueError("Relevância estimada deve estar em [0,1]")

    def available_at(self, time: datetime) -> bool:
        return self.published_at <= time and self.received_at <= time


class ClosedCandleSource(Protocol):
    def closed_candles(self) -> Iterable[dict]: ...


class EventSource(Protocol):
    def events(self) -> Iterable[ExternalEvent]: ...


@dataclass(frozen=True)
class MacroRiskState:
    """Filtro causal de risco; nunca produz direção de mercado."""
    evaluated_at: datetime
    level: str
    reasons: tuple[str, ...]
    force_abstention: bool

    def __post_init__(self):
        if self.evaluated_at.tzinfo is None or self.level not in {"normal", "elevated", "critical"}:
            raise ValueError("Estado macro inválido")
        if self.level == "critical" and not self.force_abstention:
            raise ValueError("Risco crítico exige abstenção")


def macro_risk_filter(events: Iterable[ExternalEvent], evaluated_at: datetime) -> MacroRiskState:
    """Classifica somente eventos já publicados e recebidos."""
    if evaluated_at.tzinfo is None:
        raise ValueError("Horário com timezone obrigatório")
    available = [event for event in events if event.available_at(evaluated_at)]
    critical = [e for e in available if e.category in {"exchange_outage", "regulatory_emergency"} and e.reliability == "official"]
    elevated = [e for e in available if e.category in {"macro", "regulation", "exchange"}]
    if critical:
        return MacroRiskState(evaluated_at, "critical", tuple(e.identifier for e in critical), True)
    if elevated:
        return MacroRiskState(evaluated_at, "elevated", tuple(e.identifier for e in elevated), False)
    return MacroRiskState(evaluated_at, "normal", (), False)


class EventCalendar:
    """Calendário append-only; registra eventos, não produz sinais direcionais."""
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, event: ExternalEvent) -> None:
        if any(item.identifier == event.identifier and item.source == event.source for item in self.events()):
            raise ValueError("Evento já registrado")
        row = {"source": event.source, "identifier": event.identifier, "title": event.title,
               "permitted_content": event.permitted_content, "published_at": event.published_at.isoformat(),
               "received_at": event.received_at.isoformat(), "category": event.category,
               "reliability": event.reliability, "relevance_hypothesis": event.relevance_hypothesis,
               "relevance_estimate": event.relevance_estimate}
        with self.path.open("a", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            output.flush()
            os.fsync(output.fileno())

    def events(self) -> list[ExternalEvent]:
        if not self.path.exists():
            return []
        result = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            result.append(ExternalEvent(source=row["source"], identifier=row["identifier"], title=row["title"],
                                        permitted_content=row["permitted_content"],
                                        published_at=datetime.fromisoformat(row["published_at"]),
                                        received_at=datetime.fromisoformat(row["received_at"]), category=row["category"],
                                        reliability=row["reliability"], relevance_hypothesis=row["relevance_hypothesis"],
                                        relevance_estimate=row.get("relevance_estimate")))
        return result

    def risk_at(self, evaluated_at: datetime) -> MacroRiskState:
        return macro_risk_filter(self.events(), evaluated_at)
