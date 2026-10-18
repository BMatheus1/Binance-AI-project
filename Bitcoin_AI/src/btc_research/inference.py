"""Inferência auditável, sem atuação financeira."""
from pathlib import Path

import joblib
import pandas as pd

from .common import digest
from .features import make_features


def predict_closed_candles(path: Path, expected_sha256: str, candles: pd.DataFrame, received_at: pd.Timestamp) -> dict:
    if digest(path) != expected_sha256:
        raise ValueError("Hash do modelo não confere")
    if received_at.tzinfo is None:
        raise ValueError("Horário de recebimento deve conter timezone")
    if (candles.close_time >= received_at).any():
        raise ValueError("Candles ainda não disponíveis no instante informado")
    features = make_features(candles).tail(1)
    bundle = joblib.load(path)  # nunca carregar pickle de fonte não confiável
    p = bundle.predict_proba(features)[0]
    return {"decision_time": str(features.decision_time.iloc[0]), "received_at": str(received_at), "horizon": bundle.horizon,
            "p_down": float(p[0]), "p_tie": float(p[1]), "p_up": float(p[2]), "model_sha256": expected_sha256,
            "features": features[bundle.columns].iloc[0].to_dict(), "automatic_trading": False}
