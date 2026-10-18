"""Contratos puros para transformar caminhos Kronos em probabilidades auditáveis."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np


KRONOS_COLUMNS = ("open", "high", "low", "close", "volume", "amount")


def paths_to_probabilities(paths: np.ndarray, horizons=(1, 5, 15, 30), *,
                           smoothing_alpha: float = 0.5, tie_tolerance: float = 0.0) -> dict[int, dict]:
    """Converte caminhos OHLCVA em P(baixa, empate, alta) usando a convenção next_open."""
    values = np.asarray(paths, dtype=float)
    if values.ndim != 3 or values.shape[2] != len(KRONOS_COLUMNS) or not np.isfinite(values).all():
        raise ValueError("Caminhos Kronos devem ter shape [amostras, passos, 6] e valores finitos")
    if smoothing_alpha <= 0 or tie_tolerance < 0:
        raise ValueError("Suavização deve ser positiva e tolerância não negativa")
    result = {}
    entry = values[:, 0, 0]
    if (entry <= 0).any():
        raise ValueError("Open previsto de entrada deve ser positivo")
    for horizon in horizons:
        if not 1 <= int(horizon) <= values.shape[1]:
            raise ValueError("Horizonte fora do caminho previsto")
        returns = values[:, int(horizon) - 1, 3] / entry - 1
        labels = np.where(returns < -tie_tolerance, 0, np.where(returns > tie_tolerance, 2, 1))
        counts = np.bincount(labels, minlength=3).astype(float)
        probability = (counts + smoothing_alpha) / (counts.sum() + 3 * smoothing_alpha)
        result[int(horizon)] = {
            "probabilities": probability.tolist(),
            "predicted_return_mean": float(returns.mean()),
            "predicted_return_median": float(np.median(returns)),
            "path_count": int(len(returns)),
        }
    return result


def verify_identity(path: Path, expected_sha256: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"Hash divergente para {path}: {actual}")


@dataclass(frozen=True)
class KronosCandidateSpec:
    repository_revision: str
    model_id: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    variant: str = "pretrained"

    @classmethod
    def from_manifest(cls, path: Path) -> "KronosCandidateSpec":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{name: data[name] for name in cls.__dataclass_fields__})

    def model_version(self) -> str:
        return f"kronos:{self.variant}:{self.model_revision[:12]}:{self.tokenizer_revision[:12]}"


def record_shadow_paths(ledger, paths: np.ndarray, spec: KronosCandidateSpec, *, decision_time: datetime,
                        feature_snapshot_hash: str, data_quality: dict, horizons=(1, 5, 15, 30),
                        smoothing_alpha: float = 0.5) -> list[dict]:
    """Registra o challenger no ledger sem autorizar qualquer sinal ou ordem."""
    converted = paths_to_probabilities(paths, horizons=horizons, smoothing_alpha=smoothing_alpha)
    complete = bool(data_quality.get("complete", False))
    records = []
    for horizon in horizons:
        records.append(ledger.record_prediction(
            decision_time=decision_time,
            horizon_minutes=int(horizon),
            model_version=spec.model_version(),
            feature_snapshot_hash=feature_snapshot_hash,
            probabilities=converted[int(horizon)]["probabilities"],
            data_quality=data_quality,
            decision="abstain_policy" if complete else "abstain_technical",
            threshold=1.0,
        ))
    return records
