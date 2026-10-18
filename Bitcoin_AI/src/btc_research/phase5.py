"""Fase 5: exportação causal para Colab e importação auditável de resultados Kronos."""
from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtesting import simulate
from .common import ROOT, digest, save_json, write_text
from .phase4 import _ece, _probability_distribution
from .validation import daily_block_ci, metrics


REQUIRED_CANDLE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]


def config(root: Path = ROOT) -> dict:
    return json.loads((root / "configs/phase_5.json").read_text(encoding="utf-8"))


def _load_candles(root: Path, stop: str) -> pd.DataFrame:
    parts = []
    stop_time = pd.Timestamp(stop, tz="UTC")
    for path in sorted((root / "data/processed").glob("*.parquet")):
        if pd.Timestamp(path.stem, tz="UTC") >= stop_time:
            continue
        part = pd.read_parquet(path, columns=REQUIRED_CANDLE_COLUMNS)
        parts.append(part[part.open_time < stop_time])
    frame = pd.concat(parts, ignore_index=True).sort_values("open_time").reset_index(drop=True)
    if frame.empty or frame.open_time.duplicated().any():
        raise ValueError("Candles ausentes ou duplicados")
    if frame.open_time.diff().dropna().ne(pd.Timedelta(minutes=1)).any():
        raise ValueError("Exportação Kronos exige série contínua de um minuto")
    if frame.open_time.max() >= stop_time:
        raise ValueError("Período proibido alcançado")
    return frame


def _kronos_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame[REQUIRED_CANDLE_COLUMNS].rename(
        columns={"open_time": "timestamps", "quote_volume": "amount"}).copy()
    if not np.isfinite(out[["open", "high", "low", "close", "volume", "amount"]].to_numpy()).all():
        raise ValueError("Campos Kronos não finitos")
    return out


def _select_even(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    ordered = frame.sort_values("decision_time").drop_duplicates("decision_time").reset_index(drop=True)
    if count <= 0 or len(ordered) < count:
        raise ValueError("Quantidade inválida para seleção congelada")
    indices = np.linspace(0, len(ordered) - 1, count, dtype=int)
    return ordered.iloc[indices].reset_index(drop=True)


def _calibration_rows(root: Path, cfg: dict) -> pd.DataFrame:
    columns = ["decision_time", "entry_price"]
    for h in cfg["horizons"]:
        columns += [f"event_end_{h}m", f"target_{h}m", f"return_{h}m", f"exit_price_{h}m"]
    parts = []
    for path in sorted((root / "data/phase_4/targets").glob("2026-0[1-3].parquet")):
        parts.append(pd.read_parquet(path, columns=columns))
    frame = pd.concat(parts, ignore_index=True).dropna().sort_values("decision_time")
    start = pd.Timestamp(cfg["train_end"], tz="UTC") + pd.Timedelta(minutes=30)
    stop = pd.Timestamp(cfg["calibration_end"], tz="UTC") - pd.Timedelta(minutes=30)
    frame = frame[(frame.decision_time >= start) & (frame.decision_time < stop)]
    return _select_even(frame, cfg["comparison_rows_calibration"])


def _validation_rows(root: Path, cfg: dict) -> pd.DataFrame:
    latest = json.loads((root / "reports/phase_4/latest.json").read_text(encoding="utf-8"))
    model_root = root / latest["models"]
    merged = None
    for h in cfg["horizons"]:
        frame = pd.read_parquet(model_root / f"{h}m-validation-predictions.parquet")
        rename = {column: f"baseline_{column}_{h}m" for column in ["p_down", "p_tie", "p_up", "model"]}
        keep = ["decision_time", "entry_price", f"event_end_{h}m", f"target_{h}m",
                f"return_{h}m", f"exit_price_{h}m", "p_down", "p_tie", "p_up", "model"]
        frame = frame[keep].rename(columns=rename)
        if merged is not None:
            frame = frame.drop(columns="entry_price")
        merged = frame if merged is None else merged.merge(frame, on="decision_time", validate="one_to_one")
    if merged is None:
        raise ValueError("Previsões congeladas da Fase 4 não encontradas")
    stop = pd.Timestamp(cfg["forbidden_final_test_start"], tz="UTC")
    if merged.decision_time.max() >= stop:
        raise ValueError("Comparação alcançou período final proibido")
    return _select_even(merged, cfg["comparison_rows_validation"])


def export_colab(root: Path = ROOT) -> Path:
    cfg = config(root)
    out = root / "data/phase_5/colab"
    out.mkdir(parents=True, exist_ok=True)
    candles = _load_candles(root, cfg["validation_end"])
    periods = {
        "train": (cfg["local_train_start"], cfg["train_end"]),
        "calibration": (cfg["train_end"], cfg["calibration_end"]),
        "validation": (cfg["calibration_end"], cfg["validation_end"]),
    }
    artifacts = []
    for name, (start, stop) in periods.items():
        subset = candles[(candles.open_time >= pd.Timestamp(start, tz="UTC")) &
                         (candles.open_time < pd.Timestamp(stop, tz="UTC"))]
        target = out / f"candles_{name}.parquet"
        _kronos_frame(subset).to_parquet(target, compression="zstd", index=False)
        artifacts.append({"path": target.name, "rows": len(subset), "start": str(subset.open_time.min()),
                          "end": str(subset.open_time.max()), "sha256": digest(target)})
    for name, frame in [("comparison_calibration", _calibration_rows(root, cfg)),
                        ("comparison_validation", _validation_rows(root, cfg))]:
        target = out / f"{name}.parquet"
        frame.to_parquet(target, compression="zstd", index=False)
        artifacts.append({"path": target.name, "rows": len(frame),
                          "start": str(frame.decision_time.min()), "end": str(frame.decision_time.max()),
                          "sha256": digest(target)})
    phase4_preservation = json.loads((root / "reports/phase_4/preservation.json").read_text(encoding="utf-8"))
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(), "phase": 5,
        "schema": {"timestamps": "UTC open_time", "fields": ["open", "high", "low", "close", "volume", "amount"],
                   "amount": "quote_volume USDT"},
        "target_convention": "decision after candle t; entry open[t+1]; exit close[t+h]; classes 0/1/2",
        "config": cfg, "artifacts": artifacts, "phase4_preservation": phase4_preservation,
        "pretraining_overlap": {
            "known": True,
            "local_overlap": "2023-10-01 through 2024-06-30 may overlap Binance pre-training",
            "mitigation": "fine-tuning export begins 2024-07-01; evaluation is 2026-04-01 through 2026-06-30",
            "independence_limit": "instrument-level membership and exact source rows were not disclosed",
        },
        "forbidden_final_period_exported": False,
    }
    save_json(out / "manifest.json", manifest)
    archive = root / "data/phase_5/bitcoin_ai_phase5_colab.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(out.glob("*")):
            bundle.write(path, arcname=path.name)
    save_json(root / "reports/phase_5/export_manifest.json",
              manifest | {"archive": str(archive.relative_to(root)), "archive_sha256": digest(archive)})
    return archive


def _economic(frame: pd.DataFrame, p: np.ndarray, horizon: int, cfg: dict) -> list[dict]:
    scenarios = []
    for threshold in cfg["thresholds"]:
        for payout in cfg["payouts"]:
            scenarios.append(simulate(frame, p, horizon, threshold=threshold, payout=payout)[0])
        for cost in cfg["spot_costs_bps_per_side"]:
            scenarios.append(simulate(frame, p, horizon, threshold=threshold, mode="spot", costs_bps=cost)[0])
    return scenarios


def _same_instants(left, right) -> bool:
    """Compara instantes UTC sem exigir a mesma unidade física do Parquet (us/ns)."""
    a = pd.DatetimeIndex(pd.to_datetime(left, utc=True))
    b = pd.DatetimeIndex(pd.to_datetime(right, utc=True))
    return len(a) == len(b) and bool((a == b).all())


def import_colab_results(source: Path, root: Path = ROOT) -> Path:
    cfg = config(root)
    source = Path(source)
    manifest = json.loads((source / "run_manifest.json").read_text(encoding="utf-8"))
    predictions_path = source / "kronos_predictions.parquet"
    if manifest.get("prediction_sha256") != digest(predictions_path):
        raise ValueError("Hash das previsões diverge do manifesto do Colab")
    if manifest.get("forbidden_final_period_used") is not False or manifest.get("real_orders") is not False:
        raise ValueError("Manifesto não confirma isolamento temporal e ausência de ordens reais")
    predictions = pd.read_parquet(predictions_path)
    required = {"decision_time", "horizon", "variant", "target", "actual_return", "entry_price",
                "exit_price", "event_end", "p_down", "p_tie", "p_up", "predicted_return"}
    if required - set(predictions):
        raise ValueError(f"Colunas ausentes: {sorted(required - set(predictions))}")
    expected_identity = {key: cfg[key] for key in ["official_repository_revision", "model_id", "model_revision",
                                                    "tokenizer_id", "tokenizer_revision"]}
    if any(manifest.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("Identidade Kronos diverge da configuração congelada")
    predictions["decision_time"] = pd.to_datetime(predictions.decision_time, utc=True)
    predictions["event_end"] = pd.to_datetime(predictions.event_end, utc=True)
    if predictions.decision_time.max() >= pd.Timestamp(cfg["forbidden_final_test_start"], tz="UTC"):
        raise ValueError("Resultado inclui período final proibido")
    if predictions.duplicated(["variant", "horizon", "decision_time"]).any():
        raise ValueError("Previsões Kronos duplicadas")
    probabilities = predictions[["p_down", "p_tie", "p_up"]].to_numpy(float)
    if not np.isfinite(probabilities).all() or (probabilities < 0).any() or not np.allclose(probabilities.sum(1), 1):
        raise ValueError("Probabilidades Kronos inválidas")
    reference = pd.read_parquet(root / "data/phase_5/colab/comparison_validation.parquet")
    reference["decision_time"] = pd.to_datetime(reference.decision_time, utc=True)
    mode = manifest.get("mode")
    expected_variants = ({"pretrained_raw", "pretrained_calibrated", "finetuned_raw", "finetuned_calibrated"}
                         if mode == "full" else {"pretrained_raw_smoke"} if mode == "smoke" else set())
    if set(predictions.variant.unique()) != expected_variants:
        raise ValueError("Variantes ausentes ou inesperadas para o modo declarado")
    output = {"status": manifest.get("mode", "unknown"), "source_manifest": manifest,
              "predictions_sha256": digest(predictions_path), "variants": {},
              "policy": cfg["policy"], "automatic_promotion": False, "real_orders": False}
    for variant, variant_frame in predictions.groupby("variant"):
        output["variants"][variant] = {}
        for horizon in cfg["horizons"]:
            frame = variant_frame[variant_frame.horizon == horizon].sort_values("decision_time").copy()
            expected = reference[["decision_time", "entry_price", f"event_end_{horizon}m", f"target_{horizon}m",
                                  f"return_{horizon}m", f"exit_price_{horizon}m",
                                  f"baseline_p_down_{horizon}m", f"baseline_p_tie_{horizon}m",
                                  f"baseline_p_up_{horizon}m", f"baseline_model_{horizon}m"]]
            joined = expected.merge(frame, on="decision_time", how="inner", validate="one_to_one")
            if len(joined) != len(frame) or not np.array_equal(joined[f"target_{horizon}m"].astype(int), joined.target.astype(int)):
                raise ValueError("Resultados não correspondem às observações congeladas")
            expected_count = len(reference) if mode == "full" else 2
            if len(joined) != expected_count:
                raise ValueError("Quantidade de observações diverge do protocolo congelado")
            expected_end = pd.to_datetime(joined[f"event_end_{horizon}m"], utc=True)
            observed_end = pd.to_datetime(joined.event_end, utc=True)
            numeric_pairs = [
                (f"return_{horizon}m", "actual_return"),
                ("entry_price_x", "entry_price_y"),
                (f"exit_price_{horizon}m", "exit_price"),
            ]
            aligned = _same_instants(expected_end, observed_end)
            aligned = aligned and all(np.allclose(joined[a], joined[b], rtol=1e-12, atol=1e-12)
                                      for a, b in numeric_pairs)
            if not aligned:
                raise ValueError("Instantes ou valores econômicos não correspondem à amostra congelada")
            p = joined[["p_down", "p_tie", "p_up"]].to_numpy(float)
            base_p = joined[[f"baseline_p_down_{horizon}m", f"baseline_p_tie_{horizon}m",
                             f"baseline_p_up_{horizon}m"]].to_numpy(float)
            y = joined.target.astype(int).to_numpy()
            eval_frame = pd.DataFrame({"decision_time": joined.decision_time,
                                       f"event_end_{horizon}m": joined.event_end,
                                       f"target_{horizon}m": y,
                                       f"return_{horizon}m": joined.actual_return})
            loss_delta = -np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1)) + np.log(
                np.clip(base_p[np.arange(len(y)), y], 1e-12, 1))
            output["variants"][variant][str(horizon)] = {
                "observations": len(joined),
                "phase4_baseline_model": sorted(joined[f"baseline_model_{horizon}m"].astype(str).unique()),
                "kronos": metrics(y, p), "phase4_baseline": metrics(y, base_p),
                "kronos_ece": _ece(y, p), "probability_distribution": _probability_distribution(p),
                "paired_log_loss_delta_vs_phase4": daily_block_ci(loss_delta, joined.decision_time),
                "economics": _economic(eval_frame, p, horizon, cfg),
            }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-phase5-import"
    run_dir = root / "reports/phase_5/runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    save_json(run_dir / "results.json", output)
    save_json(root / "reports/phase_5/latest_import.json",
              {"run_id": run_id, "results": str((run_dir / "results.json").relative_to(root))})
    return run_dir
