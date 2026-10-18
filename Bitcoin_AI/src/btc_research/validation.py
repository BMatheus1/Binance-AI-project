from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss, precision_recall_fscore_support, roc_auc_score

from .features import SPECS


def assert_inputs(x: pd.DataFrame, names: list[str]) -> None:
    if not names or set(names) - set(SPECS):
        raise ValueError("Feature fora do catálogo; possível target/preço futuro")
    if x.decision_time.duplicated().any() or not x.decision_time.is_monotonic_increasing:
        raise ValueError("Sequência temporal inválida")
    if (x.available_at > x.decision_time).any():
        raise ValueError("Vazamento: feature disponível depois da decisão")
    if not np.isfinite(x[names].to_numpy()).all():
        raise ValueError("Features não finitas; retirar warmup/lacunas")


def split_period(d: pd.DataFrame, h: int, start: str | None, stop: str, embargo: int = 5) -> pd.DataFrame:
    end = pd.Timestamp(stop, tz="UTC")
    mask = (d.decision_time < end) & (d[f"event_end_{h}m"] < end - pd.Timedelta(minutes=embargo))
    if start:
        mask &= d.decision_time >= pd.Timestamp(start, tz="UTC") + pd.Timedelta(minutes=embargo)
    return d.loc[mask].copy()


def assert_disjoint(a: pd.DataFrame, b: pd.DataFrame, h: int) -> None:
    if a.empty or b.empty or a[f"event_end_{h}m"].max() >= b.decision_time.min():
        raise ValueError("Divisão vazia ou rótulos sobrepostos entre períodos")


def metrics(y, p) -> dict:
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    if len(y) == 0:
        return {"n": 0}
    if p.shape != (len(y), 3) or not np.isfinite(p).all() or (p < 0).any() or not np.allclose(p.sum(axis=1), 1):
        raise ValueError("Probabilidades inválidas; exigidas colunas baixa/empate/alta")
    pred = p.argmax(axis=1)
    precision, recall, f1, _ = precision_recall_fscore_support(y, pred, labels=[0, 1, 2], average="macro", zero_division=0)
    calibration = []
    for cls in range(3):
        for left in np.arange(0, 1, 0.1):
            mask = (p[:, cls] >= left) & (p[:, cls] < left + 0.1 + (1e-12 if left > 0.89 else 0))
            if mask.any():
                calibration.append({"class": cls, "left": float(left), "n": int(mask.sum()), "probability": float(p[mask, cls].mean()), "frequency": float((y[mask] == cls).mean())})
    try:
        auc = float(roc_auc_score(y, p, multi_class="ovr", labels=[0, 1, 2])) if len(np.unique(y)) == 3 else None
    except ValueError:
        auc = None
    return {"n": len(y), "accuracy": float(accuracy_score(y, pred)), "precision_macro": float(precision), "recall_macro": float(recall),
            "f1_macro": float(f1), "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
            "log_loss": float(log_loss(y, p, labels=[0, 1, 2])), "brier_multiclass": float(((p - np.eye(3)[y]) ** 2).sum(axis=1).mean()),
            "roc_auc_ovr": auc, "calibration": calibration}


def daily_block_ci(values, times, seed=42, repeats=500) -> dict:
    """Reamostra dias inteiros; preserva dependência intradiária, não interdiária."""
    s = pd.DataFrame({"value": np.asarray(values), "day": pd.DatetimeIndex(times).floor("D")}).groupby("day").value.agg(["sum", "count"])
    if len(s) < 10:
        return {"mean": float(np.mean(values)) if len(values) else None, "low": None, "high": None, "days": len(s), "limitation": "menos de 10 dias"}
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(s), (repeats, len(s)))
    means = s["sum"].to_numpy()[samples].sum(axis=1) / s["count"].to_numpy()[samples].sum(axis=1)
    return {"mean": float(np.mean(values)), "low": float(np.quantile(means, .025)), "high": float(np.quantile(means, .975)), "days": len(s),
            "method": "bootstrap 500 blocos diários; sem correção por múltiplos experimentos"}


def by_period(y, p, times) -> dict:
    periods = pd.DatetimeIndex(times).strftime("%Y-%m")
    return {period: metrics(np.asarray(y)[periods == period], p[periods == period]) for period in sorted(set(periods))}
