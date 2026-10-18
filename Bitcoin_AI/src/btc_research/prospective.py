"""Registro prospectivo imutável e paper trading; não contém envio de ordens."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .decision import decisions
from .common import digest, save_json
from .validation import metrics


def _canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class ImmutableLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self) -> dict:
        previous = "GENESIS"
        predictions, resolved = set(), set()
        rows = self.records()
        for index, row in enumerate(rows):
            stored = row.get("record_hash")
            body = {k: v for k, v in row.items() if k != "record_hash"}
            expected = hashlib.sha256(_canonical(body)).hexdigest()
            if stored != expected or row.get("previous_hash") != previous:
                raise ValueError(f"Ledger adulterado no registro {index}")
            if row["record_type"] == "prediction":
                if row["prediction_id"] in predictions:
                    raise ValueError("prediction_id duplicado")
                predictions.add(row["prediction_id"])
            elif row["record_type"] == "outcome":
                if row["prediction_id"] not in predictions or row["prediction_id"] in resolved:
                    raise ValueError("Resultado órfão ou duplicado")
                resolved.add(row["prediction_id"])
            previous = stored
        return {"records": len(rows), "predictions": len(predictions), "resolved": len(resolved), "head_hash": previous}

    def _append(self, body: dict) -> dict:
        state = self.verify()
        body = dict(body)
        body["previous_hash"] = state["head_hash"]
        body["record_hash"] = hashlib.sha256(_canonical(body)).hexdigest()
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(body, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return body

    def record_prediction(self, *, decision_time: datetime, horizon_minutes: int, model_version: str,
                          feature_snapshot_hash: str, probabilities: list[float] | None, data_quality: dict,
                          decision: str, threshold: float, prediction_id: str | None = None) -> dict:
        if decision_time.tzinfo is None or decision_time > datetime.now(timezone.utc):
            raise ValueError("Horário de decisão inválido")
        if probabilities is None:
            if decision != "abstain_technical":
                raise ValueError("Probabilidades ausentes exigem abstenção técnica")
        elif len(probabilities) != 3 or any(p < 0 for p in probabilities) or abs(sum(probabilities) - 1) > 1e-8:
            raise ValueError("Probabilidades baixa/empate/alta inválidas")
        if not data_quality.get("complete", False) and decision != "abstain_technical":
            raise ValueError("Dados incompletos exigem abstenção técnica")
        identifier = prediction_id or str(uuid.uuid4())
        if any(r.get("prediction_id") == identifier for r in self.records()):
            raise ValueError("prediction_id já registrado")
        return self._append({"record_type": "prediction", "prediction_id": identifier,
                             "recorded_at": datetime.now(timezone.utc).isoformat(),
                             "decision_time": decision_time.isoformat(), "horizon_minutes": horizon_minutes,
                             "model_version": model_version, "feature_snapshot_hash": feature_snapshot_hash,
                             "probabilities": probabilities, "data_quality": data_quality,
                             "decision": decision, "threshold": threshold})

    def resolve(self, prediction_id: str, *, event_end: datetime, outcome: int,
                entry: dict, exit: dict) -> dict:
        if event_end.tzinfo is None or outcome not in {0, 1, 2}:
            raise ValueError("Resultado inválido")
        rows = self.records()
        prediction = next((r for r in rows if r.get("record_type") == "prediction" and r["prediction_id"] == prediction_id), None)
        if prediction is None:
            raise ValueError("Previsão inexistente")
        if any(r.get("record_type") == "outcome" and r["prediction_id"] == prediction_id for r in rows):
            raise ValueError("Previsão já resolvida")
        if event_end <= datetime.fromisoformat(prediction["decision_time"]):
            raise ValueError("Resultado deve ser posterior à decisão")
        return self._append({"record_type": "outcome", "prediction_id": prediction_id,
                             "recorded_at": datetime.now(timezone.utc).isoformat(),
                             "event_end": event_end.isoformat(), "outcome": outcome,
                             "entry": entry, "exit": exit})


@dataclass(frozen=True)
class PaperSpotConfig:
    fee_bps_per_side: float = 5.0
    latency_ms: int = 250
    max_drawdown_fraction: float = .10
    max_daily_loss_fraction: float = .03


def paper_spot_long(*, entry_ask: float, exit_bid: float, quantity: float = 1.0,
                    config: PaperSpotConfig = PaperSpotConfig()) -> dict:
    if min(entry_ask, exit_bid, quantity) <= 0 or config.fee_bps_per_side < 0:
        raise ValueError("Cotação/configuração inválida")
    fee = config.fee_bps_per_side / 10_000
    gross_cost = entry_ask * quantity
    gross_proceeds = exit_bid * quantity
    net = gross_proceeds * (1 - fee) - gross_cost * (1 + fee)
    return {"market": "spot", "paper": True, "entry_side": "ask", "exit_side": "bid",
            "entry_ask": entry_ask, "exit_bid": exit_bid, "quantity": quantity,
            "fee_bps_per_side": config.fee_bps_per_side, "latency_ms": config.latency_ms,
            "net_quote": net, "net_return": net / (gross_cost * (1 + fee)),
            "real_order_sent": False}


def paper_fixed_payout(*, correct: bool, tie: bool, payout: float) -> dict:
    if not 0 < payout <= 1:
        raise ValueError("Payout inválido")
    pnl = 0.0 if tie else payout if correct else -1.0
    return {"market": "fixed_payout", "paper": True, "payout": payout, "pnl_units": pnl,
            "tie_rule": "reembolso", "real_order_sent": False}


def feature_snapshot_hash(features: dict) -> str:
    return hashlib.sha256(_canonical(features)).hexdigest()


class ProspectiveObserver:
    """Uma decisão por candle fechado; previsão é persistida antes do retorno."""
    def __init__(self, model_path: Path, ledger: ImmutableLedger, *, model_version: str,
                 horizon_minutes: int, threshold: float = .6, payout: float = .8,
                 expected_sha256: str | None = None):
        self.model_path = model_path
        self.ledger = ledger
        self.model_version = model_version
        self.horizon_minutes = horizon_minutes
        self.threshold = threshold
        self.payout = payout
        if expected_sha256 is not None and digest(model_path) != expected_sha256:
            raise ValueError("Hash do modelo prospectivo não confere")
        self.model = joblib.load(model_path)
        if not getattr(self.model, "columns", None) or not hasattr(self.model, "predict_proba"):
            raise ValueError("Modelo prospectivo incompatível")

    def observe(self, frame: pd.DataFrame, quality: dict, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or frame.empty:
            raise ValueError("Observação vazia ou sem timezone")
        row = frame.iloc[[-1]].copy()
        decision_time = pd.Timestamp(row.decision_time.iloc[0]).to_pydatetime()
        available_at = pd.Timestamp(row.available_at.iloc[0]).to_pydatetime()
        snapshot = {column: float(row[column].iloc[0]) for column in self.model.columns
                    if column in row and pd.notna(row[column].iloc[0])}
        complete = (quality.get("complete", False) and len(snapshot) == len(self.model.columns)
                    and available_at <= decision_time <= now
                    and np.isfinite(list(snapshot.values())).all())
        if not complete:
            return self.ledger.record_prediction(
                decision_time=min(decision_time, now), horizon_minutes=self.horizon_minutes,
                model_version=self.model_version, feature_snapshot_hash=feature_snapshot_hash(snapshot),
                probabilities=None, data_quality=quality | {"complete": False},
                decision="abstain_technical", threshold=self.threshold)
        probability = self.model.predict_proba(row)[0]
        signal = int(decisions(probability[None, :], self.threshold, self.payout)[0])
        label = {-1: "abstain_policy", 0: "down", 2: "up"}[signal]
        return self.ledger.record_prediction(
            decision_time=decision_time, horizon_minutes=self.horizon_minutes,
            model_version=self.model_version, feature_snapshot_hash=feature_snapshot_hash(snapshot),
            probabilities=probability.astype(float).tolist(), data_quality=quality,
            decision=label, threshold=self.threshold)


class PaperSession:
    """Contabilidade paper independente, com trava e parada imediata."""
    def __init__(self, config: PaperSpotConfig = PaperSpotConfig()):
        self.config = config
        self.active = True
        self.trades: list[dict] = []
        self.predictions = 0
        self.abstentions = 0

    def stop(self) -> None:
        self.active = False

    def observe_decision(self, decision: str) -> bool:
        self.predictions += 1
        if decision.startswith("abstain") or not self.active:
            self.abstentions += 1
            return False
        return True

    def add_spot_result(self, *, entry_ask: float, exit_bid: float, quantity: float = 1.0,
                        time: datetime | None = None) -> dict:
        if not self.active:
            raise RuntimeError("Simulação interrompida")
        result = paper_spot_long(entry_ask=entry_ask, exit_bid=exit_bid, quantity=quantity, config=self.config)
        result["time"] = (time or datetime.now(timezone.utc)).isoformat()
        self.trades.append(result)
        state = self.status()
        if (state["drawdown_fraction"] >= self.config.max_drawdown_fraction or
                state["daily_loss_fraction"] >= self.config.max_daily_loss_fraction):
            self.stop()
        return result

    def status(self) -> dict:
        pnl = np.asarray([trade["net_quote"] for trade in self.trades], dtype=float)
        curve = np.r_[0.0, np.cumsum(pnl)]
        drawdown = float(np.max(np.maximum.accumulate(curve) - curve)) if len(curve) else 0.0
        invested = sum(trade["entry_ask"] * trade["quantity"] for trade in self.trades)
        today = datetime.now(timezone.utc).date()
        daily = [trade for trade in self.trades if datetime.fromisoformat(trade["time"]).date() == today]
        daily_pnl = sum(trade["net_quote"] for trade in daily)
        daily_invested = sum(trade["entry_ask"] * trade["quantity"] for trade in daily)
        return {"active": self.active, "predictions": self.predictions, "trades": len(self.trades),
                "abstentions": self.abstentions,
                "abstention_rate": self.abstentions / self.predictions if self.predictions else 0.0,
                "net_quote": float(pnl.sum()) if len(pnl) else 0.0, "drawdown_quote": drawdown,
                "drawdown_fraction": drawdown / invested if invested else 0.0,
                "daily_loss_fraction": max(0.0, -daily_pnl / daily_invested) if daily_invested else 0.0,
                "real_orders": False}


def prospective_evaluation(ledger: ImmutableLedger) -> dict:
    """Métricas somente de previsões já resolvidas, sem reescrever o ledger."""
    rows = ledger.records()
    predictions = {row["prediction_id"]: row for row in rows if row["record_type"] == "prediction"}
    outcomes = {row["prediction_id"]: row for row in rows if row["record_type"] == "outcome"}
    resolved = [(predictions[key], outcome) for key, outcome in outcomes.items()
                if key in predictions and predictions[key]["probabilities"] is not None]
    result = {"predictions": len(predictions), "resolved": len(outcomes),
              "technical_abstentions": sum(p["decision"] == "abstain_technical" for p in predictions.values()),
              "policy_abstentions": sum(p["decision"] == "abstain_policy" for p in predictions.values()),
              "selected_opportunities": sum(p["decision"] in {"up", "down"} for p in predictions.values()),
              "ledger": ledger.verify(), "metrics": None}
    if resolved:
        y = np.asarray([outcome["outcome"] for _, outcome in resolved], dtype=int)
        probability = np.asarray([prediction["probabilities"] for prediction, _ in resolved], dtype=float)
        result["metrics"] = metrics(y, probability)
    return result


def write_prospective_report(ledger: ImmutableLedger, path: Path) -> dict:
    report = prospective_evaluation(ledger)
    save_json(path, report)
    return report
