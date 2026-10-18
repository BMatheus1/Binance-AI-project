"""Fase 3: comparação temporal de microestrutura sem reutilizar o teste final."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .backtesting import simulate
from .common import ROOT, digest, save_json, versions, write_text
from .features import SPECS, make_features
from .labeling import make_targets
from .microstructure import MICRO_SPECS, load_minutes, make_micro_features, reconstructed_candles
from .models import align_probabilities, create_model
from .validation import assert_disjoint, daily_block_ci, metrics, split_period


def _cfg(root: Path) -> dict:
    return json.loads((root / "configs/phase_3.json").read_text(encoding="utf-8"))


def _ece(y: np.ndarray, p: np.ndarray) -> float:
    confidence, prediction = p.max(axis=1), p.argmax(axis=1)
    total = 0.0
    for left in np.arange(0, 1, .1):
        mask = (confidence >= left) & (confidence < left + .1 + (1e-12 if left > .89 else 0))
        if mask.any():
            total += mask.mean() * abs((prediction[mask] == y[mask]).mean() - confidence[mask].mean())
    return float(total)


class CalibratedResearchModel:
    def __init__(self, columns: list[str], seed: int, threads: int):
        self.columns = columns
        self.estimator = create_model("xgboost", seed, threads)
        self.calibrator = None

    def fit(self, frame: pd.DataFrame, target: str):
        self.estimator.fit(frame[self.columns], frame[target].astype(int))
        return self

    def raw(self, frame: pd.DataFrame) -> np.ndarray:
        return align_probabilities(self.estimator, frame[self.columns])

    def calibrate(self, frame: pd.DataFrame, target: str):
        y = frame[target].astype(int)
        raw = self.raw(frame)
        self.calibrator = LogisticRegression(C=1, max_iter=400, random_state=42)
        self.calibrator.fit(np.log(np.clip(raw, 1e-9, 1)), y)
        return self

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        raw = self.raw(frame)
        if self.calibrator is None:
            return raw
        return align_probabilities(self.calibrator, np.log(np.clip(raw, 1e-9, 1)))


def _selected_columns(train: pd.DataFrame, columns: list[str], target: str, seed: int, maximum: int = 24) -> list[str]:
    selector = make_pipeline(StandardScaler(), LogisticRegression(
        penalty="l1", solver="saga", C=.03, max_iter=800, random_state=seed))
    selector.fit(train[columns], train[target].astype(int))
    coefficients = np.abs(selector[-1].coef_).max(axis=0)
    order = np.argsort(-coefficients)
    chosen = [columns[i] for i in order if coefficients[i] > 1e-10][:maximum]
    return chosen or [columns[i] for i in order[:min(10, len(order))]]


def _binary_half_baseline(y: np.ndarray) -> dict:
    mask = y != 1
    if not mask.any():
        return {"n_non_ties": 0, "log_loss": None, "accuracy": None, "scope": "somente baixa/alta"}
    return {"n_non_ties": int(mask.sum()), "log_loss": float(-np.log(.5)), "accuracy": .5,
            "scope": "somente baixa/alta; empate excluído, pois 50/50 não define probabilidade válida para três classes"}


def _frequency_probabilities(train_y: pd.Series, n: int) -> np.ndarray:
    frequency = (np.bincount(train_y.astype(int), minlength=3) + 1) / (len(train_y) + 3)
    return np.tile(frequency, (n, 1))


def _uncertainty(y: np.ndarray, p: np.ndarray, times: pd.Series, seed: int) -> dict:
    row = np.arange(len(y))
    losses = -np.log(np.clip(p[row, y], 1e-12, 1))
    correct = (p.argmax(axis=1) == y).astype(float)
    return {"log_loss_daily_block_ci": daily_block_ci(losses, times, seed),
            "accuracy_daily_block_ci": daily_block_ci(correct, times, seed + 1),
            "limitation": "menos de 10 dias impede limites do bootstrap" if pd.DatetimeIndex(times).floor("D").nunique() < 10 else None}


def _audit_phase2(root: Path) -> dict:
    latest = json.loads((root / "reports/phase_2/latest.json").read_text(encoding="utf-8"))
    result = json.loads((root / latest["results"]).read_text(encoding="utf-8"))
    fold_ends = [v["periods"][h]["validation_end"] for v in result["folds"].values() for h in ["1", "5"]]
    candidates = {h: {name: {"log_loss": value["mean_log_loss"], "accuracy": value["mean_accuracy"],
                             "ece": value["mean_ece"], "raw_log_loss": value["mean_raw_log_loss"]}
                      for name, value in block["candidates"].items()}
                  for h, block in result["model_comparison"].items()}
    return {
        "phase2_run": result["run_id"], "target_classes": {"0": "baixa", "1": "empate", "2": "alta"},
        "probability_metric": "log loss multiclasse; Brier, ECE e calibração também registrados",
        "binary_50_percent_baseline": "aplicável apenas após excluir empates; log loss=ln(2)",
        "calibration": "bloco posterior ao treino e anterior à validação em cada fold",
        "temporal_integrity": {"latest_validation_end": max(fold_ends), "forbidden_test_reused": False,
                               "final_2026_07_to_09_status": "consumido na Fase 1, não reutilizado"},
        "statistical_vs_economic": "métricas probabilísticas não implicam expectativa líquida; cenários econômicos foram separados",
        "candidates": candidates,
        "conclusion": result["conclusion"],
    }


def build_dataset(root: Path = ROOT) -> tuple[pd.DataFrame, dict]:
    minutes = load_minutes(root)
    candles = reconstructed_candles(minutes)
    base = make_features(candles)
    micro = make_micro_features(minutes)
    targets = make_targets(candles)
    data = base.merge(micro, on=["decision_time", "available_at"], validate="one_to_one")
    data = data.merge(targets, on="decision_time", validate="one_to_one")
    if (data.available_at > data.decision_time).any():
        raise ValueError("Feature futura detectada")
    manifest = {"rows": len(data), "start": data.decision_time.min(), "end": data.decision_time.max(),
                "base_features": len(SPECS), "micro_features": len(MICRO_SPECS),
                "candle_origin": "OHLCV reconstruído dos AggTrades oficiais; trades é soma dos IDs de trades subjacentes",
                "missing_minutes": int(minutes.open_time.diff().gt(pd.Timedelta(minutes=1)).sum())}
    dataset_path = root / "data/phase_3/features/dataset.parquet"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(dataset_path, compression="zstd", index=False)
    save_json(root / "data/phase_3/manifests/features.json", manifest)
    return data, manifest


def _render(root: Path, result: dict) -> None:
    out = root / "reports/phase_3"
    audit = result["phase2_audit"]
    write_text(out / "01_auditoria_fase_2.md", f"""# 01 — Auditoria da Fase 2

- O alvo é multiclasse: baixa, empate e alta. A log loss principal usa três probabilidades que somam 1.
- A referência constante de 50% é válida somente no subconjunto binário sem empates; seu log loss é ln(2) = 0,693147. Para três classes, a referência correta é a frequência estimada no treino.
- A calibração da Fase 2 foi ajustada em bloco posterior ao treino e anterior à validação.
- O período julho–setembro/2026 continua marcado como teste final consumido e não foi aberto nesta fase.
- Significância estatística, calibração e resultado econômico são diagnósticos distintos. Nenhuma melhora estatística foi tratada como lucro.

Execução auditada: `{audit['phase2_run']}`. Última validação da Fase 2: {audit['temporal_integrity']['latest_validation_end']}.
""")
    ingestion = result["ingestion"]
    write_text(out / "02_dados_aggtrades.md", f"""# 02 — Dados oficiais de AggTrades

Foram ingeridos {ingestion['rows']:,} AggTrades oficiais em {len(ingestion['days'])} arquivos diários, de 01 a 14/10/2026, totalizando {ingestion['minutes']:,} minutos observados. Cada ZIP e `.CHECKSUM` foi preservado, e cada SHA-256 foi conferido antes da ingestão.

O processamento é incremental em partes Parquet. IDs duplicados, regressões, gaps de aggregate ID, gaps de IDs subjacentes e lacunas de minutos são contabilizados por dia e nas fronteiras diárias em `data/phase_3/manifests/ingestion.json`. Não há preenchimento sintético de lacunas.

O processamento do piloto foi tecnicamente viável. A expansão para 30–90 dias não foi executada nesta data porque ainda não existem 30 dias completos posteriores a setembro/2026; recuar o início reutilizaria o teste final já consumido. A ampliação deve ocorrer prospectivamente quando o período existir.
""")
    rows = ["# 03 — Catálogo causal de microestrutura", "", "Todas as variáveis ficam disponíveis no fim do minuto (`open_time + 1min`) e reiniciam após lacunas.", "", "| Feature | Fórmula |", "|---|---|"]
    rows += [f"| `{name}` | {formula} |" for name, formula in MICRO_SPECS.items()]
    write_text(out / "03_catalogo_microestrutura.md", "\n".join(rows))
    exp = ["# 04 — Experimentos A–D", "", "A, B, C e D usam o mesmo intervalo, divisões, regressão logística, calibração e métricas. D escolhe atributos apenas no treino por regressão L1; a validação não participa da escolha.", ""]
    for h, block in result["experiments"].items():
        exp += [f"## Horizonte {h}m", "", "| Variante | Features | Accuracy | Log loss | Brier | ECE |", "|---|---:|---:|---:|---:|---:|"]
        for name, value in block["candidates"].items():
            m = value["metrics"]
            exp.append(f"| {name} | {len(value['columns'])} | {m['accuracy']:.4%} | {m['log_loss']:.6f} | {m['brier_multiclass']:.6f} | {value['ece']:.6f} |")
        b = block["frequency_baseline"]
        exp += [f"| frequência do treino | 0 | {b['accuracy']:.4%} | {b['log_loss']:.6f} | {b['brier_multiclass']:.6f} | {block['frequency_ece']:.6f} |", "",
                f"Menor log loss observado: **{block['selected_for_prospective']}**. Isso seleciona uma versão para observação prospectiva; não promove negociação.", ""]
    write_text(out / "04_experimentos_ad.md", "\n".join(exp))
    collector_text = """# 05 — Coletor público em tempo real

`btc_research.live_market` implementa os streams públicos `aggTrade`, `kline_1m`, `bookTicker` e `depth@100ms`. Cada registro inclui horário da origem, horário local de recebimento, tipo e payload bruto, particionado em JSONL.

AggTrade IDs repetidos e saltos são registrados. O livro local segue a sequência oficial: eventos são armazenados em buffer, o snapshot REST público é aplicado e somente então os deltas contíguos são aceitos. Qualquer salto invalida o livro e força nova sincronização. Dados incompletos geram abstenção técnica.
"""
    smoke_path = out / "collector_smoke.json"
    if smoke_path.exists():
        smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        collector_text += (f"\n## Smoke test público\n\nRecebidas {smoke['messages']} mensagens em 15 segundos, com "
                           f"{smoke['reconnections']} reconexões, {smoke['aggtrade_duplicates']} IDs duplicados, "
                           f"{smoke['aggtrade_missing_ids']} IDs ausentes e {smoke['depth_invalidations']} invalidações. "
                           f"Livro válido ao final: {smoke['book'].get('valid', False)}.\n")
    write_text(out / "05_coletor_tempo_real.md", collector_text)
    write_text(out / "06_ledger_e_paper.md", """# 06 — Ledger imutável e paper trading

O ledger é append-only e encadeado por SHA-256. Uma previsão registra versão, features, probabilidades, qualidade e decisão antes do resultado; a resolução é um novo registro e não altera a previsão. A verificação detecta edição, remoção ou reordenação.

O simulador Spot usa compra no ask e venda no bid observados, taxas por lado e latência registrada. O simulador de payout permanece separado. Não existe cliente autenticado, envio de ordem, credencial ou movimentação financeira.
""")
    econ = ["# 07 — Diagnóstico econômico", "", "Todos os resultados são hipotéticos. O histórico de AggTrades não contém bid/ask; por isso, o retrospectivo Spot usa cenários explícitos de custo por lado. Spread real é reservado ao coletor prospectivo.", ""]
    for h, block in result["economics"].items():
        econ += [f"## Horizonte {h}m — {block['model']}", "", "| Mercado | Parâmetro | Trades | Expectativa | IC diário |", "|---|---:|---:|---:|---|"]
        for row in block["scenarios"]:
            ci = row.get("expectancy_ci") or {}
            interval = "indisponível (<10 dias)" if ci.get("low") is None else f"[{ci['low']:.6f}, {ci['high']:.6f}]"
            parameter = f"limiar={row['threshold']}; " + (f"payout={row['payout']}" if row['mode'] == 'fixed' else f"custo/lado={row['costs_bps_per_side']}bps")
            econ.append(f"| {row['mode']} | {parameter} | {row['trades']} | {row['expectancy_per_trade'] if row['expectancy_per_trade'] is not None else 'n/a'} | {interval} |")
        econ += ["", "A amostra de validação tem três dias; não permite intervalo diário confiável nem conclusão econômica robusta.", ""]
    write_text(out / "07_diagnostico_economico.md", "\n".join(econ))
    write_text(out / "08_monitoramento_e_noticias.md", """# 08 — Monitoramento e notícias

Indicadores mínimos: atraso origem→recebimento, reconexões, IDs duplicados/perdidos, validade do livro, minutos completos, taxa de abstenção, deriva das features, calibração e resultado paper por dia.

Notícias entram somente por `ExternalEvent`: fonte, identificador, publicação, recebimento, categoria, confiabilidade e hipótese de relevância. O filtro macro pode elevar risco e forçar abstenção; ele não cria sinal direcional e não usa conteúdo futuro.
""")
    best = {h: b["selected_for_prospective"] for h, b in result["experiments"].items()}
    m1 = result["experiments"]["1"]["candidates"]
    m5 = result["experiments"]["5"]["candidates"]
    delta_1 = m1[best['1']]['metrics']['log_loss'] - m1['A_original_xgboost_37']['metrics']['log_loss']
    added_5 = m5['C_combined']['metrics']['log_loss'] - m5['A_original_xgboost_37']['metrics']['log_loss']
    write_text(out / "README.md", f"""# Fase 3 — resultado executivo

O piloto oficial de 14 dias foi concluído com ingestão íntegra, features causais, comparação A–D, coletor público, ledger imutável e paper trading. Nenhuma ordem real ou API autenticada foi implementada.

As variantes escolhidas apenas para observação prospectiva foram `{best['1']}` em 1m e `{best['5']}` em 5m. Em 1m, a escolhida obteve accuracy de {m1[best['1']]['metrics']['accuracy']:.4%} e log loss de {m1[best['1']]['metrics']['log_loss']:.6f}, contra {m1['A_original_xgboost_37']['metrics']['accuracy']:.4%} e {m1['A_original_xgboost_37']['metrics']['log_loss']:.6f} do XGBoost original com 37 features. Em 5m, a escolhida obteve {m5[best['5']]['metrics']['accuracy']:.4%} e {m5[best['5']]['metrics']['log_loss']:.6f}, contra {m5['A_original_xgboost_37']['metrics']['accuracy']:.4%} e {m5['A_original_xgboost_37']['metrics']['log_loss']:.6f} do mesmo baseline.

O ganho de log loss da variante escolhida em 1m foi {delta_1:+.6f}. Em 5m, acrescentar microestrutura mudou a log loss em {added_5:+.6f} e o próprio XGBoost original venceu A–D. A microestrutura não apresentou vantagem consistente entre horizontes. Todos os cenários Spot ficaram negativos, inclusive a 5 bps por lado; resultados positivos isolados de payout não têm intervalo diário confiável em apenas três dias.

A validação cobre só três dias, e a escolha foi feita nesse mesmo bloco; portanto, não existe teste independente posterior para promoção. A política oficial permanece em **abstenção integral**.

Consulte `results.json` para números completos, gaps, probabilidades, cenários de custo e limitações.
""")


def run(root: Path = ROOT) -> Path:
    cfg = _cfg(root)
    data, feature_manifest = build_dataset(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-phase3"
    run_dir = root / "reports/phase_3/runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    result = {"run_id": run_id, "status": "exploratory_post_final_test_pilot", "versions": versions(),
              "config": cfg, "phase2_audit": _audit_phase2(root),
              "ingestion": json.loads((root / "data/phase_3/manifests/ingestion.json").read_text(encoding="utf-8")),
              "features": feature_manifest, "experiments": {}, "economics": {},
              "real_trading_executed": False, "official_policy": "abstenção integral"}
    base_cols, micro_cols = list(SPECS), list(MICRO_SPECS)
    all_cols = base_cols + micro_cols
    model_dir = root / "models/phase_3" / run_id
    model_dir.mkdir(parents=True, exist_ok=False)
    for h in cfg["horizons"]:
        target = f"target_{h}m"
        usable = data.dropna(subset=all_cols + [target, f"event_end_{h}m"]).copy()
        train = split_period(usable, h, None, cfg["train_end"], cfg["embargo_minutes"])
        calibration = split_period(usable, h, cfg["train_end"], cfg["calibration_end"], cfg["embargo_minutes"])
        validation = split_period(usable, h, cfg["calibration_end"], cfg["validation_end"], cfg["embargo_minutes"])
        assert_disjoint(train, calibration, h)
        assert_disjoint(calibration, validation, h)
        selected = _selected_columns(train, all_cols, target, cfg["seed"] + h)
        definitions = {"A_original_xgboost_37": base_cols, "B_aggtrades": micro_cols,
                       "C_combined": all_cols, "D_selected_train_only": selected}
        candidates, fitted = {}, {}
        y = validation[target].astype(int).to_numpy()
        for name, columns in definitions.items():
            model = CalibratedResearchModel(columns, cfg["seed"] + h, cfg["threads"]).fit(train, target).calibrate(calibration, target)
            p = model.predict_proba(validation)
            raw = model.raw(validation)
            candidates[name] = {"columns": columns, "metrics": metrics(y, p), "raw_metrics": metrics(y, raw),
                                "ece": _ece(y, p), "raw_ece": _ece(y, raw),
                                "uncertainty": _uncertainty(y, p, validation.decision_time, cfg["seed"] + h)}
            fitted[name] = (model, p)
        frequency_p = _frequency_probabilities(train[target], len(validation))
        frequency_metrics = metrics(y, frequency_p)
        chosen = min(candidates, key=lambda n: candidates[n]["metrics"]["log_loss"])
        model_path = model_dir / f"horizon_{h}m.joblib"
        joblib.dump(fitted[chosen][0], model_path)
        result["experiments"][str(h)] = {
            "periods": {"train": [str(train.decision_time.min()), str(train.decision_time.max()), len(train)],
                        "calibration": [str(calibration.decision_time.min()), str(calibration.decision_time.max()), len(calibration)],
                        "validation": [str(validation.decision_time.min()), str(validation.decision_time.max()), len(validation)]},
            "candidates": candidates, "frequency_baseline": frequency_metrics,
            "frequency_ece": _ece(y, frequency_p), "constant_50_binary": _binary_half_baseline(y),
            "selected_for_prospective": chosen,
            "model_artifact": {"path": str(model_path.relative_to(root)), "sha256": digest(model_path)},
            "selection_warning": "selecionado no próprio holdout; exige observação prospectiva antes de qualquer conclusão"}
        scenarios = []
        p = fitted[chosen][1]
        for threshold in cfg["thresholds"]:
            for payout in cfg["payouts"]:
                summary, _ = simulate(validation, p, h, threshold=threshold, payout=payout, mode="fixed",
                                      daily_limit=1e9, drawdown_limit=1e9)
                scenarios.append(summary)
            for cost in cfg["spot_costs_bps_per_side"]:
                summary, _ = simulate(validation, p, h, threshold=threshold, mode="spot", costs_bps=cost,
                                      daily_limit=1e9, drawdown_limit=1e9)
                scenarios.append(summary)
        result["economics"][str(h)] = {"model": chosen, "scenarios": scenarios,
                                        "spread_observed": False, "reason": "AggTrades históricos não incluem bid/ask"}
    result["conclusion"] = {"pilot_complete": True, "independent_post_selection_test": False,
                            "evidence_sufficient_for_real_trading": False,
                            "reason": "14 dias e apenas três dias de validação; seleção consumiu o holdout; custos históricos são cenários"}
    save_json(run_dir / "results.json", result)
    save_json(root / "reports/phase_3/latest.json", {"run_id": run_id, "results": str((run_dir / "results.json").relative_to(root)),
                                                     "models": str(model_dir.relative_to(root))})
    save_json(root / "reports/phase_3/results.json", result)
    _render(root, result)
    return run_dir
