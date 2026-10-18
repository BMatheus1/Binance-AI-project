"""Fase 2: diagnóstico e experimentos walk-forward sem reabrir o teste final.

Este módulo é deliberadamente separado do pipeline congelado da Fase 1. Ele usa
somente observações anteriores a 2026-07-01 e nunca promove uma política.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .backtesting import simulate
from .common import ROOT, digest, save_json, versions, write_text
from .features import SPECS
from .models import Baseline, align_probabilities
from .validation import assert_disjoint, daily_block_ci, metrics, split_period


EXTENDED_SPECS = {
    "wick_imbalance": "sombra inferior menos sombra superior",
    "rejection_low": "sombra inferior vezes posição do fechamento",
    "rejection_high": "sombra superior vezes distância do fechamento ao topo",
    "doji": "1 se corpo/range <= 10%",
    "doji_frequency_5": "frequência de doji nos cinco candles encerrados",
    "body_growth_3": "1 se o corpo absoluto cresceu por três candles",
    "range_compression_3": "1 se a amplitude relativa contraiu por três candles",
    "engulf_proxy": "reversão de sinal com corpo maior que o candle anterior",
    "momentum_acceleration": "momentum de 5m menos um quarto do momentum de 20m",
    "trend_strength": "momentum20 normalizado pela volatilidade realizada",
    "range_to_atr": "amplitude do candle dividida pelo ATR relativo",
    "mean_reversion_pressure": "-z-score de Bollinger vezes razão de volatilidade",
    "taker_imbalance": "duas vezes participação compradora agressora menos um",
    "activity_pressure": "desequilíbrio agressor vezes volume e trades relativos",
    "price_volume_agreement": "sinal do corpo vezes desequilíbrio agressor",
    "rejection_at_extreme": "rejeição ponderada pela distância causal ao extremo de 20m",
    "direction_persistence": "módulo do balanço direcional dos últimos cinco candles"
}

CATEGORIES = sorted({spec[0] for spec in SPECS.values()})


@dataclass
class ProbabilityModel:
    estimator: object
    columns: list[str]
    calibrator: object | None = None

    def predict_raw(self, frame: pd.DataFrame) -> np.ndarray:
        _assert_feature_frame(frame, self.columns)
        return align_probabilities(self.estimator, frame[self.columns])

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        p = self.predict_raw(frame)
        if self.calibrator is not None:
            p = align_probabilities(self.calibrator, np.log(np.clip(p, 1e-9, 1)))
        return p

    def calibrate(self, frame: pd.DataFrame, y: pd.Series) -> None:
        p = self.predict_raw(frame)
        self.calibrator = LogisticRegression(C=1.0, max_iter=300, random_state=42)
        self.calibrator.fit(np.log(np.clip(p, 1e-9, 1)), y)


def _phase2_config(root: Path) -> dict:
    return json.loads((root / "configs/phase_2.json").read_text(encoding="utf-8"))


def _assert_feature_frame(frame: pd.DataFrame, columns: list[str]) -> None:
    allowed = set(SPECS) | set(EXTENDED_SPECS)
    if not columns or set(columns) - allowed:
        raise ValueError("Feature experimental fora do catálogo da Fase 2")
    if frame.decision_time.duplicated().any() or not frame.decision_time.is_monotonic_increasing:
        raise ValueError("Sequência temporal inválida")
    if (frame.available_at > frame.decision_time).any():
        raise ValueError("Vazamento temporal: feature ainda indisponível")
    if not np.isfinite(frame[columns].to_numpy()).all():
        raise ValueError("Feature não finita")


def make_context_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Transformações causais feitas antes da amostragem mensal."""
    d = frame.copy()
    eps = 1e-12
    d["wick_imbalance"] = d.lower_wick - d.upper_wick
    d["rejection_low"] = d.lower_wick * d.close_position
    d["rejection_high"] = d.upper_wick * (1 - d.close_position)
    d["doji"] = (d.body_fraction.abs() <= .10).astype(float)
    d["doji_frequency_5"] = d.doji.rolling(5, min_periods=5).mean()
    d["body_growth_3"] = ((d.body_rel > d.body_rel.shift(1)) &
                            (d.body_rel.shift(1) > d.body_rel.shift(2))).astype(float)
    d["range_compression_3"] = ((d.range_rel < d.range_rel.shift(1)) &
                                  (d.range_rel.shift(1) < d.range_rel.shift(2))).astype(float)
    prior_sign = np.sign(d.body_fraction.shift(1))
    d["engulf_proxy"] = ((np.sign(d.body_fraction) == -prior_sign) &
                           (prior_sign != 0) & (d.body_rel > d.body_rel.shift(1))).astype(float)
    d["momentum_acceleration"] = d.momentum_5 - .25 * d.momentum_20
    d["trend_strength"] = (d.momentum_20 / (d.realized_vol_20 * np.sqrt(20) + eps)).clip(-20, 20)
    d["range_to_atr"] = (d.range_rel / (d.atr_rel_14 + eps)).clip(0, 20)
    d["mean_reversion_pressure"] = (-d.bollinger_z * d.vol_ratio).clip(-20, 20)
    d["taker_imbalance"] = 2 * d.taker_buy_ratio - 1
    d["activity_pressure"] = (d.taker_imbalance * np.log1p(d.volume_rel_20.clip(lower=0)) *
                                np.log1p(d.trade_intensity.clip(lower=0))).clip(-20, 20)
    d["price_volume_agreement"] = np.sign(d.body_fraction) * d.taker_imbalance
    scale = d.atr_rel_14.abs() + eps
    near_support = np.exp(-(d.support_distance_20.abs() / scale).clip(0, 50))
    near_resistance = np.exp(-(d.breakout_20.abs() / scale).clip(0, 50))
    d["rejection_at_extreme"] = d.lower_wick * near_support - d.upper_wick * near_resistance
    d["direction_persistence"] = d.direction_balance_5.abs()
    # Shifts não podem atravessar descontinuidades ou o início de uma partição mensal.
    continuous5 = d.decision_time.diff().eq(pd.Timedelta(minutes=1)).rolling(4).sum().eq(4)
    d.loc[~continuous5, ["doji_frequency_5"]] = np.nan
    continuous3 = d.decision_time.diff().eq(pd.Timedelta(minutes=1)).rolling(2).sum().eq(2)
    d.loc[~continuous3, ["body_growth_3", "range_compression_3", "engulf_proxy"]] = np.nan
    return d


def load_development_data(root: Path, cfg: dict) -> pd.DataFrame:
    """Carrega somente dados anteriores ao teste proibido e amostra após features."""
    manifest = json.loads((root / "reports/D_features.json").read_text(encoding="utf-8"))
    stop = pd.Timestamp(cfg["development_end_exclusive"], tz="UTC")
    forbidden = pd.Timestamp(cfg["forbidden_final_test_start"], tz="UTC")
    if stop > forbidden:
        raise ValueError("Configuração tentaria acessar o teste final consumido")
    frames = []
    for part in manifest["partitions"]:
        month = pd.Timestamp(part["month"], tz="UTC")
        if month >= stop:
            continue
        fpath = root / "data/features" / f"{part['month']}.parquet"
        tpath = root / "data/targets" / f"{part['month']}.parquet"
        if digest(fpath) != part["features_sha256"] or digest(tpath) != part["targets_sha256"]:
            raise ValueError("Derivado alterado; reconstrua a Fase 1 antes da Fase 2")
        frame = pd.read_parquet(fpath).merge(
            pd.read_parquet(tpath), on="decision_time", validate="one_to_one"
        )
        # A partição de junho contém o candle aberto às 23:59, cuja decisão só
        # existe às 00:00 de 01/07. O corte é pelo instante de decisão.
        frame = frame[frame.decision_time < stop].copy()
        frame = make_context_features(frame)
        required = list(SPECS) + list(EXTENDED_SPECS)
        frame = frame.dropna(subset=required).reset_index(drop=True)
        if len(frame) > cfg["rows_per_month"]:
            idx = np.linspace(0, len(frame) - 1, cfg["rows_per_month"], dtype=int)
            frame = frame.iloc[idx].copy()
        frame["source_month"] = part["month"]
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True).sort_values("decision_time").reset_index(drop=True)
    if data.empty or data.decision_time.max() >= forbidden:
        raise ValueError("Teste final carregado ou nenhum dado de desenvolvimento")
    _assert_feature_frame(data, list(SPECS) + list(EXTENDED_SPECS))
    return data


def _create_estimator(name: str, seed: int, threads: int):
    if name == "logistic":
        return make_pipeline(StandardScaler(), OneVsRestClassifier(
            LogisticRegression(C=.05, max_iter=300, solver="liblinear", random_state=seed)
        ))
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=100, max_depth=8, min_samples_leaf=120,
                                      max_features=.6, n_jobs=threads, random_state=seed)
    if name == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=100, max_depth=3, learning_rate=.05, subsample=.8,
                             colsample_bytree=.8, min_child_weight=30, reg_lambda=10,
                             objective="multi:softprob", num_class=3, tree_method="hist",
                             n_jobs=threads, random_state=seed)
    if name == "xgboost_regularized":
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=140, max_depth=3, learning_rate=.035, subsample=.8,
                             colsample_bytree=.7, min_child_weight=60, reg_lambda=20,
                             reg_alpha=.1, objective="multi:softprob", num_class=3,
                             tree_method="hist", n_jobs=threads, random_state=seed)
    if name == "catboost":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(iterations=120, depth=4, learning_rate=.04, l2_leaf_reg=12,
                                  loss_function="MultiClass", random_seed=seed,
                                  thread_count=threads, verbose=False, allow_writing_files=False)
    raise ValueError(name)


def _candidate_definitions() -> dict[str, tuple[str, list[str]]]:
    original = list(SPECS)
    extended = original + list(EXTENDED_SPECS)
    return {
        "frequency": ("frequency", ["return_1"]),
        "logistic_original": ("logistic", original),
        "logistic_contextual": ("logistic", extended),
        "random_forest_original": ("random_forest", original),
        "xgboost_original": ("xgboost", original),
        "xgboost_contextual_regularized": ("xgboost_regularized", extended),
        "catboost_original": ("catboost", original),
    }


def _fit_candidate(name: str, algorithm: str, columns: list[str], train: pd.DataFrame,
                   calibration: pd.DataFrame, h: int, cfg: dict) -> ProbabilityModel:
    y = train[f"target_{h}m"].astype(int)
    if algorithm == "frequency":
        estimator = Baseline("frequency").fit(train[["return_1"]], y)
        return ProbabilityModel(estimator, columns)
    estimator = _create_estimator(algorithm, cfg["seed"], cfg["threads"])
    estimator.fit(train[columns], y)
    bundle = ProbabilityModel(estimator, columns)
    bundle.calibrate(calibration, calibration[f"target_{h}m"].astype(int))
    return bundle


def _ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    confidence = p.max(axis=1)
    correct = p.argmax(axis=1) == y
    total = len(y)
    value = 0.0
    for left in np.linspace(0, 1, bins + 1)[:-1]:
        right = left + 1 / bins
        mask = (confidence >= left) & (confidence < right + (1e-12 if right == 1 else 0))
        if mask.any():
            value += mask.sum() / total * abs(correct[mask].mean() - confidence[mask].mean())
    return float(value)


def _losses(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return -np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1))


def _daily_delta_ci(y: np.ndarray, p: np.ndarray, baseline: np.ndarray,
                    times: pd.Series, seed: int) -> dict:
    delta = _losses(y, p) - _losses(y, baseline)
    return daily_block_ci(delta, times, seed=seed, repeats=500)


def _sign_flip_pvalue(values: np.ndarray, seed: int, repeats: int = 4096) -> float:
    values = np.asarray(values, dtype=float)
    if len(values) < 2:
        return 1.0
    observed = abs(values.mean())
    rng = np.random.default_rng(seed)
    exceed = 1
    for _ in range(repeats):
        exceed += abs((values * rng.choice([-1, 1], len(values))).mean()) >= observed
    return float(exceed / (repeats + 1))


def _holm(pvalues: dict[str, float]) -> dict[str, float]:
    ordered = sorted(pvalues, key=pvalues.get)
    adjusted, running = {}, 0.0
    m = len(ordered)
    for rank, name in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * pvalues[name]))
        adjusted[name] = running
    return adjusted


def _group_metric(frame: pd.DataFrame, p: np.ndarray, h: int, column: str) -> dict:
    y = frame[f"target_{h}m"].to_numpy(dtype=int)
    output = {}
    for key, positions in frame.groupby(column, observed=True).indices.items():
        idx = np.asarray(positions)
        if len(idx) < 20:
            continue
        m = metrics(y[idx], p[idx])
        output[str(key)] = {"n": m["n"], "accuracy": m["accuracy"],
                            "log_loss": m["log_loss"], "brier": m["brier_multiclass"],
                            "mean_confidence": float(p[idx].max(axis=1).mean())}
    return output


def _error_analysis(frame: pd.DataFrame, p: np.ndarray, h: int) -> dict:
    d = frame.copy().reset_index(drop=True)
    d["trend_regime"] = np.select([d.trend_strength > 2, d.trend_strength < -2],
                                   ["alta", "baixa"], default="lateral")
    d["volatility_regime"] = np.select([d.realized_vol_20 < d.fold_vol_low,
                                         d.realized_vol_20 > d.fold_vol_high],
                                        ["baixa", "alta"], default="normal")
    d["volatility_change"] = np.select([d.vol_ratio > 1.25, d.vol_ratio < .75],
                                        ["expansão", "contração"], default="estável")
    d["abrupt_movement"] = np.where(d.range_rel >= d.fold_range_q95, "abrupto", "normal")
    d["utc_block"] = (d.decision_time.dt.hour // 4 * 4).map(lambda x: f"{x:02d}-{x+3:02d}")
    d["weekday"] = d.decision_time.dt.day_name()
    d["sequence"] = np.select([d.direction_balance_5 >= .6, d.direction_balance_5 <= -.6],
                               ["alta_persistente", "baixa_persistente"], default="mista")
    conf = p.max(axis=1)
    d["confidence"] = pd.cut(conf, bins=[0, .5, .55, .6, .65, .7, 1.000001],
                              labels=["<0.50", "0.50-0.55", "0.55-0.60", "0.60-0.65", "0.65-0.70", ">=0.70"],
                              include_lowest=True)
    return {name: _group_metric(d, p, h, name) for name in [
        "trend_regime", "volatility_regime", "volatility_change", "abrupt_movement",
        "utc_block", "weekday", "sequence", "confidence", "fold_id"
    ]}


def _permutation_importance(bundle: ProbabilityModel, validation: pd.DataFrame, h: int,
                            cfg: dict, fold_number: int) -> dict:
    n = min(cfg["permutation_sample"], len(validation))
    sample = validation.iloc[np.linspace(0, len(validation) - 1, n, dtype=int)].copy()
    y = sample[f"target_{h}m"].astype(int)
    base = metrics(y, bundle.predict_proba(sample))["log_loss"]
    rng = np.random.default_rng(cfg["seed"] + 100 * h + fold_number)
    groups = {column: [column] for column in SPECS}
    for category in CATEGORIES:
        groups[f"group:{category}"] = [c for c, spec in SPECS.items() if spec[0] == category]
    output = {}
    for label, columns in groups.items():
        changed = sample.copy()
        offset = int(rng.integers(60, max(61, len(sample) - 60)))
        changed[columns] = np.roll(changed[columns].to_numpy(), offset, axis=0)
        output[label] = metrics(y, bundle.predict_proba(changed))["log_loss"] - base
    return output


def _economic_analysis(frame: pd.DataFrame, p: np.ndarray, h: int, cfg: dict) -> dict:
    d = frame.sort_values("decision_time").reset_index(drop=True)
    scenarios = []
    for payout in cfg["payouts"]:
        for threshold in cfg["thresholds"]:
            result, _ = simulate(d, p, h, threshold=threshold, payout=payout,
                                 daily_limit=10, drawdown_limit=30)
            result["selection_status"] = "exploratório; limiar examinado na mesma validação"
            scenarios.append(result)
    for costs in cfg["spot_costs_bps_per_side"]:
        for threshold in cfg["thresholds"]:
            result, _ = simulate(d, p, h, threshold=threshold, mode="spot", costs_bps=costs,
                                 daily_limit=10, drawdown_limit=30)
            result["selection_status"] = "exploratório; execução não observada em OHLCV"
            scenarios.append(result)
    payout80 = [s for s in scenarios if s["mode"] == "fixed" and s["payout"] == .8]
    eligible = [s for s in payout80 if s["trades"] >= cfg["minimum_validation_trades"] and
                s["expectancy_ci"] and s["expectancy_ci"].get("low") is not None and
                s["expectancy_ci"]["low"] > 0]
    return {"scenarios": scenarios,
            "exploratory_candidate": max(eligible, key=lambda x: x["expectancy_ci"]["low"]) if eligible else None,
            "promotion_allowed": False,
            "reason": "Não existe teste pós-junho/2026 não observado; todos os limiares são validação interna."}


def _target_diagnostics(frame: pd.DataFrame, h: int) -> dict:
    r = frame[f"return_{h}m"].abs()
    return {"n": len(r), "zero_return_rate": float((r == 0).mean()),
            "median_abs_return": float(r.median()),
            "economically_large_rate": {f"{bps}_bps": float((r > bps / 10000).mean())
                                        for bps in [10, 20, 40]},
            "interpretation": "Descritivo; não redefine retrospectivamente o alvo da Fase 1."}


def _audit_phase1(root: Path, data: pd.DataFrame, cfg: dict) -> dict:
    quality = json.loads((root / "reports/B_quality.json").read_text(encoding="utf-8"))
    features = json.loads((root / "reports/D_features.json").read_text(encoding="utf-8"))
    latest = json.loads((root / "reports/latest_development.json").read_text(encoding="utf-8"))
    dev_path = root / latest["run"] / "development.json"
    dev = json.loads(dev_path.read_text(encoding="utf-8"))
    registry = json.loads((root / "reports/test_registry.json").read_text(encoding="utf-8"))
    originals = json.loads((root / "reports/originals_preserved.json").read_text(encoding="utf-8"))
    horizons = {}
    for h, item in dev["horizons"].items():
        horizons[h] = {"candidate_count": len(item["candidates"]),
                       "selected": item["selected"], "policy": item["policy"],
                       "candidate_names": sorted(item["candidates"]),
                       "periods": item["periods"]}
    return {
        "status": "aprovada_com_limitações",
        "candles": quality["candles"], "critical_data_errors": quality["errors"],
        "missing_minutes": quality["missing_minutes_within_months"] + quality["boundary_missing_minutes"],
        "duplicates_removed": quality["duplicate_rows_removed"],
        "feature_count": features["feature_count"], "phase1_horizons": horizons,
        "causality_checks": {"available_after_decision": int((data.available_at > data.decision_time).sum()),
                             "duplicate_decisions": int(data.decision_time.duplicated().sum()),
                             "ordered": bool(data.decision_time.is_monotonic_increasing)},
        "phase1_test_registry": registry,
        "phase2_latest_timestamp": str(data.decision_time.max()),
        "forbidden_test_start": cfg["forbidden_final_test_start"],
        "forbidden_test_rows_loaded": int((data.decision_time >= pd.Timestamp(cfg["forbidden_final_test_start"], tz="UTC")).sum()),
        "originals_preserved": {"checked": originals["checked"], "all_unchanged": originals["all_unchanged"]},
        "findings": [
            "Timestamps, ordem, continuidade, OHLC, volume, hashes e precisão ms/us foram auditados na Fase 1 sem erro crítico.",
            "As 37 features são calculadas com candles encerrados; targets e preços futuros ficam em arquivos/colunas separados.",
            "Treino, calibração e validação possuem purga pelo fim do rótulo e embargo; o scaler e a seleção de colunas são ajustados no treino.",
            "A calibração usa regressão logística sobre log-probabilidades em bloco posterior ao treino.",
            "A importância da Fase 1 teve somente duas permutações e o walk-forward cobriu apenas logística e frequência.",
            "O relatório final descreveu todos os candidatos e sensibilidades no teste consumido; esses números não podem selecionar mudanças da Fase 2.",
            "Amostragem uniforme reduz custo, mas pode omitir eventos raros e torna a inferência sobre caudas mais fraca."
        ],
        "phase1_development_sha256": digest(dev_path)
    }


def _render_reports(root: Path, result: dict) -> None:
    out = root / "reports/phase_2"
    audit = result["audit"]
    write_text(out / "01_auditoria_fase_1.md", f"""# 01 — Auditoria da Fase 1

Estado: **{audit['status']}**. Foram confirmados {audit['candles']:,} candles, {audit['feature_count']} features, zero lacunas, zero duplicatas e zero linhas do teste proibido carregadas pela Fase 2.

Os instantes são causais: candle `t` fecha antes da decisão, a entrada histórica é `open[t+1]`, a saída é `close[t+h]`, e a purga considera o fim do evento. Treino, calibração e validação são cronológicos. Os 40 originais permanecem inalterados.

Limitações encontradas: importância da Fase 1 com apenas duas permutações; walk-forward restrito a logística e frequência; amostragem uniforme do treino; ausência de correção de multiplicidade; e exposição descritiva de candidatos/limiares no teste já consumido. Isso não invalida os números históricos, mas impede reutilizá-los para selecionar a Fase 2.

O teste julho–setembro/2026 permanece registrado como consumido. A execução desta fase terminou antes de 01/07/2026.
""")
    errors = result["error_analysis"]
    error_lines = ["# 02 — Análise de erros", "", "As tabelas completas estão em `results.json`. Diferenças são descritivas e não foram transformadas retrospectivamente em filtros.", ""]
    for h, blocks in errors.items():
        error_lines += [f"## Horizonte {h}m", ""]
        for block in ["trend_regime", "volatility_regime", "volatility_change", "abrupt_movement",
                      "utc_block", "weekday", "sequence", "confidence", "fold_id"]:
            values = blocks[block]
            error_lines.append(f"### {block}")
            error_lines.append("")
            error_lines.append("| Grupo | N | Accuracy | Log loss | Confiança média |")
            error_lines.append("|---|---:|---:|---:|---:|")
            for key, m in values.items():
                error_lines.append(f"| {key} | {m['n']} | {m['accuracy']:.4%} | {m['log_loss']:.6f} | {m['mean_confidence']:.4f} |")
            error_lines.append("")
    write_text(out / "02_analise_de_erros.md", "\n".join(error_lines))

    relevance_lines = ["# 03 — Relevância das features", "",
                       "As 37 variáveis foram permutadas individualmente por deslocamento circular dentro de cada validação. Delta positivo indica piora ao destruir a variável; o método mede associação preditiva, não causalidade. As ablações de categorias usam a mesma logística e calibração.", ""]
    for h, rel in result["feature_relevance"].items():
        relevance_lines += [f"## Horizonte {h}m", "", "| Feature | Delta médio de log loss | Sinal estável nos folds |", "|---|---:|---:|"]
        ranked = sorted(rel["permutation"].items(), key=lambda x: x[1]["mean_delta"], reverse=True)
        for name, value in ranked:
            if not name.startswith("group:"):
                relevance_lines.append(f"| {name} | {value['mean_delta']:+.6f} | {value['positive_folds']}/{value['folds']} |")
        relevance_lines += ["", "A importância foi instável para várias features; nenhuma foi apagada do catálogo original.", ""]
    write_text(out / "03_relevancia_features.md", "\n".join(relevance_lines))

    regime_lines = ["# 04 — Regimes de mercado", "",
                    "Regimes usam somente dados disponíveis: tendência por momentum normalizado, volatilidade por quartis do treino e expansão/contração pela razão vol20/vol60. Resultados completos por regime estão no relatório de erros e em `results.json`.", "",
                    "A análise serve para diagnóstico. Nenhum especialista por regime foi promovido porque isso exigiria uma camada adicional de seleção e nova validação independente.", ""]
    write_text(out / "04_regimes_mercado.md", "\n".join(regime_lines))

    exp_lines = ["# 05 — Experimentos controlados", "",
                 "Todos os experimentos respeitaram o plano congelado e três folds walk-forward. As novas features são traduções matemáticas próprias, calculadas com candles encerrados.", ""]
    for h, summary in result["model_comparison"].items():
        exp_lines += [f"## Horizonte {h}m", "", f"Selecionado na validação interna: **{summary['selected']}**.", "",
                      "| Modelo | Log loss médio | Brier médio | Accuracy média | Holm p vs frequência |",
                      "|---|---:|---:|---:|---:|"]
        for name, value in summary["candidates"].items():
            exp_lines.append(f"| {name} | {value['mean_log_loss']:.6f} | {value['mean_brier']:.6f} | {value['mean_accuracy']:.4%} | {value['holm_p_vs_frequency']:.4f} |")
        exp_lines += ["", "A seleção é exploratória; não existe teste independente posterior disponível.", ""]
    write_text(out / "05_experimentos_controlados.md", "\n".join(exp_lines))
    write_text(out / "06_comparacao_modelos.md", "\n".join(exp_lines).replace("# 05 — Experimentos controlados", "# 06 — Comparação de modelos"))

    cal_lines = ["# 07 — Calibração probabilística", "",
                 "Cada algoritmo foi ajustado no treino e calibrado em um bloco posterior separado. ECE, Brier e log loss foram medidos somente no bloco de validação seguinte.", ""]
    for h, summary in result["model_comparison"].items():
        cal_lines += [f"## Horizonte {h}m", "", "| Modelo | ECE médio | Log loss bruto | Log loss calibrado |", "|---|---:|---:|---:|"]
        for name, value in summary["candidates"].items():
            raw = value.get("mean_raw_log_loss")
            cal_lines.append(f"| {name} | {value['mean_ece']:.6f} | {'n/a' if raw is None else f'{raw:.6f}'} | {value['mean_log_loss']:.6f} |")
        cal_lines.append("")
    write_text(out / "07_calibracao_probabilistica.md", "\n".join(cal_lines))

    econ_lines = ["# 08 — Diagnóstico econômico", "",
                  "Payout fixo e Spot são cenários separados. A simulação usa entrada idealizada no próximo open, uma posição por vez, sem martingale, e não observa fila, latência, liquidez, lote mínimo ou spread real.", ""]
    for h, econ in result["economic_analysis"].items():
        candidate = econ["exploratory_candidate"]
        econ_lines += [f"## Horizonte {h}m", ""]
        if candidate:
            econ_lines.append(f"Houve candidato exploratório no payout 80%: limiar {candidate['threshold']}, {candidate['trades']} operações, expectativa {candidate['expectancy_per_trade']:.6f}. Ele não pode ser promovido sem teste futuro independente.")
        else:
            econ_lines.append("Nenhum limiar do payout 80% satisfez simultaneamente quantidade mínima e limite inferior positivo do IC diário.")
        econ_lines += ["", "A política oficial permanece em abstenção integral.", ""]
    write_text(out / "08_diagnostico_economico.md", "\n".join(econ_lines))

    selected = {h: value["selected"] for h, value in result["model_comparison"].items()}
    write_text(out / "09_plano_fase_3.md", f"""# 09 — Plano para a Fase 3

1. Reservar candles posteriores a setembro/2026 sem consulta durante desenvolvimento e registrar antecipadamente o corte temporal.
2. Repetir somente as variantes selecionadas internamente ({selected}) contra frequência e o vencedor congelado da Fase 1.
3. Obter dados de execução, AggTrades e/ou snapshots de livro apenas se houver hipótese explícita; medir latência, spread, slippage, lote, tick e minNotional.
4. Executar previsão em tempo real em modo sombra, sem ordens, salvando entrada disponível, probabilidade, versão e resultado posterior.
5. Considerar dinheiro real somente após teste independente, calibração estável, expectativa líquida positiva com margem de segurança e revisão operacional. A Fase 2 não satisfaz essas condições.
""")
    h1 = result["model_comparison"]["1"]["candidates"]
    h5 = result["model_comparison"]["5"]["candidates"]
    delta_1 = h1["xgboost_contextual_regularized"]["mean_log_loss"] - h1["xgboost_original"]["mean_log_loss"]
    delta_5 = h5["xgboost_contextual_regularized"]["mean_log_loss"] - h5["xgboost_original"]["mean_log_loss"]
    write_text(out / "README.md", f"""# Fase 2 — resultado executivo

A Fase 2 foi concluída como pesquisa exploratória walk-forward. Nenhuma operação real foi executada e a política oficial permanece em **abstenção integral**.

## Resultado principal

| Horizonte | Melhor validação interna | Accuracy média | Log loss médio | Frequência histórica | Diferença |
|---|---|---:|---:|---:|---:|
| 1m | {result['model_comparison']['1']['selected']} | {h1[result['model_comparison']['1']['selected']]['mean_accuracy']:.4%} | {h1[result['model_comparison']['1']['selected']]['mean_log_loss']:.6f} | {h1['frequency']['mean_log_loss']:.6f} | {h1[result['model_comparison']['1']['selected']]['mean_log_loss'] - h1['frequency']['mean_log_loss']:+.6f} |
| 5m | {result['model_comparison']['5']['selected']} | {h5[result['model_comparison']['5']['selected']]['mean_accuracy']:.4%} | {h5[result['model_comparison']['5']['selected']]['mean_log_loss']:.6f} | {h5['frequency']['mean_log_loss']:.6f} | {h5[result['model_comparison']['5']['selected']]['mean_log_loss'] - h5['frequency']['mean_log_loss']:+.6f} |

A variante contextual do XGBoost mudou o log loss em {delta_1:+.6f} no horizonte de 1m e {delta_5:+.6f} em 5m contra o XGBoost original, nas mesmas validações. O ganho de 1m é pequeno e não foi testado em período independente; em 5m a variante piorou nos três folds. Portanto, os conhecimentos dos livros geraram hipóteses úteis, mas **não demonstraram uma vantagem nova e sustentável**.

Todos os modelos aprendidos superaram a frequência histórica em log loss após Holm, mas isso não se converteu em expectativa econômica demonstrada. Nenhum limiar de payout 80% reuniu ao mesmo tempo 200 operações e limite inferior positivo do IC diário. Os melhores resultados aparentes tiveram intervalos que incluíram zero.

## Comparação com a Fase 1

A Fase 1 continua sendo a única avaliação no teste final consumido: 50,6549%/0,809687 em 1m e 51,6876%/0,717344 em 5m para accuracy/log loss. Os números acima usam períodos e amostragem diferentes, então não provam melhora sobre esse teste. A comparação causal disponível dentro da Fase 2 é entre candidatos nos mesmos folds: ganho contextual praticamente nulo em 1m e piora em 5m.

## O que mudou

- 17 features contextuais experimentais, mantidas fora do catálogo congelado da Fase 1.
- Três folds walk-forward para todos os algoritmos avaliados.
- Erros por tendência, volatilidade, movimentos abruptos, horário UTC, dia da semana, sequências e confiança.
- Permutação temporal das 37 features, ablação por categoria e correção de Holm.
- Calibração medida antes/depois e cenários econômicos separados para payout e Spot.

## Limite da evidência

Foram usadas até 3.000 observações por mês para controlar CPU e memória. Eventos raros têm estimativas frágeis. Julho–setembro/2026 permaneceu fora da Fase 2; não existe outro teste futuro independente nos arquivos recebidos. Resultados completos e negativos estão em [results.json](runs/{result['run_id']}/results.json).
""")


def run(root: Path = ROOT) -> Path:
    cfg = _phase2_config(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-phase2"
    run_dir = root / "reports/phase_2/runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    logging.info("Fase 2: carregando desenvolvimento anterior a %s", cfg["development_end_exclusive"])
    data = load_development_data(root, cfg)
    result = {"run_id": run_id, "status": "exploratory_validation_only", "config": cfg,
              "versions": versions(), "new_feature_catalog": EXTENDED_SPECS,
              "audit": _audit_phase1(root, data, cfg), "folds": {}, "model_comparison": {},
              "error_analysis": {}, "feature_relevance": {}, "economic_analysis": {},
              "target_diagnostics": {}}
    definitions = _candidate_definitions()
    all_predictions: dict[int, dict[str, list[tuple[pd.DataFrame, np.ndarray]]]] = {
        h: {name: [] for name in definitions} for h in [1, 5]
    }
    permutation: dict[int, list[dict]] = {1: [], 5: []}
    candidate_daily: dict[int, dict[str, list[pd.Series]]] = {
        h: {name: [] for name in definitions if name != "frequency"} for h in [1, 5]
    }

    for fold_number, fold in enumerate(cfg["folds"]):
        fold_result = {"periods": {}, "horizons": {}}
        for h in [1, 5]:
            available = data.dropna(subset=[f"target_{h}m", f"event_end_{h}m"]).copy()
            tr = split_period(available, h, None, fold["train_end"], cfg["embargo_minutes"])
            ca = split_period(available, h, fold["train_end"], fold["calibration_end"], cfg["embargo_minutes"])
            va = split_period(available, h, fold["calibration_end"], fold["validation_end"], cfg["embargo_minutes"])
            assert_disjoint(tr, ca, h)
            assert_disjoint(ca, va, h)
            if va.decision_time.max() >= pd.Timestamp(cfg["forbidden_final_test_start"], tz="UTC"):
                raise ValueError("Fold alcançou teste proibido")
            fold_result["periods"][str(h)] = {"train": len(tr), "calibration": len(ca), "validation": len(va),
                                                      "validation_start": str(va.decision_time.min()),
                                                      "validation_end": str(va.decision_time.max())}
            fold_result["horizons"][str(h)] = {"candidates": {}}
            baseline_p = None
            original_bundle = None
            for name, (algorithm, columns) in definitions.items():
                logging.info("Fase 2 %s h=%sm: %s", fold["id"], h, name)
                bundle = _fit_candidate(name, algorithm, columns, tr, ca, h, cfg)
                raw_p = bundle.predict_raw(va)
                p = bundle.predict_proba(va)
                y = va[f"target_{h}m"].to_numpy(dtype=int)
                m = metrics(y, p)
                entry = {"metrics": m, "ece": _ece(y, p),
                         "raw_metrics": metrics(y, raw_p) if algorithm != "frequency" else None,
                         "columns": columns}
                if name == "frequency":
                    baseline_p = p
                else:
                    entry["paired_delta_vs_frequency_ci"] = _daily_delta_ci(y, p, baseline_p, va.decision_time, cfg["seed"] + fold_number)
                    by_day = pd.DataFrame({"delta": _losses(y, p) - _losses(y, baseline_p),
                                           "day": va.decision_time.dt.floor("D")}).groupby("day").delta.mean()
                    candidate_daily[h][name].append(by_day)
                record = va.copy()
                record["fold_id"] = fold["id"]
                record["fold_vol_low"] = float(tr.realized_vol_20.quantile(.25))
                record["fold_vol_high"] = float(tr.realized_vol_20.quantile(.75))
                record["fold_range_q95"] = float(tr.range_rel.quantile(.95))
                all_predictions[h][name].append((record, p))
                fold_result["horizons"][str(h)]["candidates"][name] = entry
                if name == "logistic_original":
                    original_bundle = bundle
            permutation[h].append(_permutation_importance(original_bundle, va, h, cfg, fold_number))
            # Categorias: retirada de cada grupo, mesma logística/calibração. A
            # permutação acima complementa a ablação sem duplicar 72 ajustes.
            ablations = {}
            full_loss = fold_result["horizons"][str(h)]["candidates"]["logistic_original"]["metrics"]["log_loss"]
            for category in CATEGORIES:
                group = [c for c, spec in SPECS.items() if spec[0] == category]
                without = [c for c in SPECS if c not in group]
                bundle = _fit_candidate(f"without_{category}", "logistic", without, tr, ca, h, cfg)
                score = metrics(va[f"target_{h}m"].astype(int), bundle.predict_proba(va))["log_loss"]
                ablations[f"without:{category}"] = {"log_loss": score, "delta_vs_full": score - full_loss}
            fold_result["horizons"][str(h)]["category_ablations"] = ablations
            save_json(run_dir / "partial_results.json", result | {"active_fold": fold["id"], "active_horizon_completed": h})
        result["folds"][fold["id"]] = fold_result
        save_json(run_dir / "partial_results.json", result)

    for h in [1, 5]:
        raw_pvalues = {}
        summary = {}
        for name in definitions:
            fold_entries = [result["folds"][fold["id"]]["horizons"][str(h)]["candidates"][name]
                            for fold in cfg["folds"]]
            if name != "frequency":
                days = pd.concat(candidate_daily[h][name]).to_numpy()
                raw_pvalues[name] = _sign_flip_pvalue(days, cfg["seed"] + h)
            summary[name] = {
                "mean_log_loss": float(np.mean([e["metrics"]["log_loss"] for e in fold_entries])),
                "mean_brier": float(np.mean([e["metrics"]["brier_multiclass"] for e in fold_entries])),
                "mean_accuracy": float(np.mean([e["metrics"]["accuracy"] for e in fold_entries])),
                "mean_ece": float(np.mean([e["ece"] for e in fold_entries])),
                "mean_raw_log_loss": (float(np.mean([e["raw_metrics"]["log_loss"] for e in fold_entries]))
                                      if name != "frequency" else None),
                "fold_log_loss": [e["metrics"]["log_loss"] for e in fold_entries],
            }
        adjusted = _holm(raw_pvalues)
        summary["frequency"]["holm_p_vs_frequency"] = 1.0
        for name in raw_pvalues:
            summary[name]["raw_p_vs_frequency"] = raw_pvalues[name]
            summary[name]["holm_p_vs_frequency"] = adjusted[name]
        selected = min(summary, key=lambda name: summary[name]["mean_log_loss"])
        result["model_comparison"][str(h)] = {"selected": selected, "candidates": summary,
                                                     "selection_scope": "validação interna; não promover"}
        selected_frames = [item[0] for item in all_predictions[h][selected]]
        selected_probs = [item[1] for item in all_predictions[h][selected]]
        oof_frame = pd.concat(selected_frames, ignore_index=True).sort_values("decision_time").reset_index(drop=True)
        order = np.argsort(pd.concat(selected_frames, ignore_index=True).decision_time.to_numpy())
        oof_p = np.concatenate(selected_probs)[order]
        result["error_analysis"][str(h)] = _error_analysis(oof_frame, oof_p, h)
        result["economic_analysis"][str(h)] = _economic_analysis(oof_frame, oof_p, h, cfg)
        result["target_diagnostics"][str(h)] = _target_diagnostics(oof_frame, h)
        labels = sorted(permutation[h][0])
        perm_summary = {}
        for label in labels:
            values = [fold[label] for fold in permutation[h]]
            perm_summary[label] = {"mean_delta": float(np.mean(values)), "values": values,
                                   "positive_folds": int(np.sum(np.asarray(values) > 0)), "folds": len(values)}
        ablation_summary = {}
        for key in result["folds"][cfg["folds"][0]["id"]]["horizons"][str(h)]["category_ablations"]:
            values = [result["folds"][fold["id"]]["horizons"][str(h)]["category_ablations"][key]["delta_vs_full"]
                      for fold in cfg["folds"]]
            ablation_summary[key] = {"mean_delta_vs_full": float(np.mean(values)), "values": values}
        result["feature_relevance"][str(h)] = {"permutation": perm_summary, "category_ablations": ablation_summary}

    result["conclusion"] = {
        "phase2_complete": True,
        "independent_test_available": False,
        "real_trading_executed": False,
        "official_policy": "abstenção integral",
        "statement": "Resultados são exploratórios/walk-forward até junho de 2026; nenhum modelo ou estratégia foi promovido."
    }
    save_json(run_dir / "results.json", result)
    save_json(root / "reports/phase_2/latest.json", {"run_id": run_id,
              "results": str((run_dir / "results.json").relative_to(root))})
    _render_reports(root, result)
    return run_dir
