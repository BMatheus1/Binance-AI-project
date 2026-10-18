"""Fase 4: novos horizontes e congelamento para observação prospectiva."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .backtesting import simulate
from .common import ROOT, digest, save_json, versions, write_text
from .features import SPECS
from .labeling import make_targets
from .models import Baseline, ModelBundle, create_model, select_columns
from .regimes import fit_regimes, regimes
from .validation import assert_disjoint, by_period, daily_block_ci, metrics, split_period


def _config(root: Path) -> dict:
    return json.loads((root / "configs/phase_4.json").read_text(encoding="utf-8"))


def _ece(y: np.ndarray, p: np.ndarray) -> float:
    confidence, prediction = p.max(axis=1), p.argmax(axis=1)
    score = 0.0
    for left in np.arange(0, 1, .1):
        mask = (confidence >= left) & (confidence < left + .1 + (1e-12 if left > .89 else 0))
        if mask.any():
            score += mask.mean() * abs((prediction[mask] == y[mask]).mean() - confidence[mask].mean())
    return float(score)


def _probability_distribution(p: np.ndarray) -> dict:
    maximum = p.max(axis=1)
    entropy = -(p * np.log(np.clip(p, 1e-12, 1))).sum(axis=1)
    return {"mean": p.mean(axis=0).tolist(), "max_probability_quantiles": np.quantile(maximum, [0, .25, .5, .75, .9, .99, 1]).tolist(),
            "entropy_quantiles": np.quantile(entropy, [0, .25, .5, .75, 1]).tolist()}


def _period(frame: pd.DataFrame) -> dict:
    return {"rows": len(frame), "start": frame.decision_time.min(), "end": frame.decision_time.max()}


def _binary_half(y: np.ndarray) -> dict:
    n = int((y != 1).sum())
    return {"observations": n, "accuracy": .5 if n else None, "log_loss": float(np.log(2)) if n else None,
            "scope": "somente baixa/alta; empates excluídos"}


def audit_previous(root: Path = ROOT) -> dict:
    phase3 = json.loads((root / "reports/phase_3/results.json").read_text(encoding="utf-8"))
    registry = json.loads((root / "reports/test_registry.json").read_text(encoding="utf-8"))
    return {
        "target_definition": "decisão após candle t; entrada open[t+1]; saída close[t+h]; 0=baixa, 1=empate, 2=alta",
        "problem": "multiclasse com três probabilidades; baseline 50% somente no subconjunto sem empates",
        "log_loss": "sklearn log_loss com labels [0,1,2], probabilidade da classe observada e soma por linha igual a 1",
        "baselines": "frequência estimada somente no treino e uniforme multiclasse, sempre nas mesmas linhas da validação",
        "calibration": "regressão logística sobre log-probabilidades em bloco posterior ao treino",
        "temporal_checks": ["features disponíveis até decision_time", "alvos em arquivos separados", "purga pelo event_end", "indicadores reiniciam após lacunas"],
        "consumed_test_registry": registry,
        "phase3_selection_warning": phase3["experiments"]["1"]["selection_warning"],
        "critical_inconsistencies": [],
        "noncritical_findings": [
            "accuracy não reflete qualidade probabilística nem custos",
            "resultados positivos de payout da Fase 3 não tinham intervalo diário estimável",
            "seleções da Fase 3 exigem teste prospectivo posterior e não são modelos de produção",
        ],
    }


def freeze_existing_models(root: Path = ROOT) -> dict:
    artifacts = []
    for path in sorted((root / "models").rglob("*.joblib")):
        if "phase_4" in path.relative_to(root / "models").parts:
            continue
        artifacts.append({"path": str(path.relative_to(root)), "sha256": digest(path), "bytes": path.stat().st_size})
    latest1 = json.loads((root / "reports/latest_development.json").read_text(encoding="utf-8"))
    development = json.loads((root / latest1["run"] / "development.json").read_text(encoding="utf-8"))
    final = json.loads((root / "reports/final_evaluation.json").read_text(encoding="utf-8"))
    latest3 = json.loads((root / "reports/phase_3/latest.json").read_text(encoding="utf-8"))
    phase3 = json.loads((root / latest3["results"]).read_text(encoding="utf-8"))
    selected = []
    for horizon, item in development["horizons"].items():
        name = item["selected"]
        candidate = item["candidates"][name]
        selected.append({"phase": 1, "horizon": int(horizon), "version": development["run_id"] + ":" + name,
                         "artifact": str(Path(latest1["run"]) / f"{horizon}m-{name}.joblib"),
                         "sha256": candidate["artifact_sha256"], "features": candidate["features"],
                         "periods": item["periods"], "validation_metrics": candidate["validation"],
                         "observed_final_metrics": final["horizons"][horizon]["comparison"][name],
                         "decision_rule": item["policy"], "economic_parameters": development["config"]})
    for horizon, item in phase3["experiments"].items():
        chosen = item["selected_for_prospective"]
        selected.append({"phase": 3, "horizon": int(horizon), "version": phase3["run_id"] + ":" + chosen,
                         "artifact": item["model_artifact"]["path"], "sha256": item["model_artifact"]["sha256"],
                         "features": item["candidates"][chosen]["columns"], "periods": item["periods"],
                         "validation_metrics": item["candidates"][chosen]["metrics"],
                         "decision_rule": {"enabled": False, "reason": "observação prospectiva somente"},
                         "economic_parameters": phase3["config"]})
    inventory = {"frozen_at": datetime.now(timezone.utc).isoformat(), "artifact_count": len(artifacts),
                 "all_joblib_artifacts": artifacts, "selected_models": selected,
                 "phase2": "não persistiu modelos; resultados exploratórios permanecem em reports/phase_2",
                 "immutability": "qualquer hash divergente invalida uso prospectivo"}
    save_json(root / "reports/phase_4/model_inventory.json", inventory)
    return inventory


def build_extended_targets(root: Path = ROOT) -> dict:
    cfg = _config(root)
    manifest = json.loads((root / "reports/D_features.json").read_text(encoding="utf-8"))
    months = [part["month"] for part in manifest["partitions"] if pd.Timestamp(part["month"], tz="UTC") < pd.Timestamp(cfg["validation_end"], tz="UTC")]
    entries, mismatches = [], 0
    for index, month in enumerate(months):
        current = pd.read_parquet(root / "data/processed" / f"{month}.parquet")
        future = current.iloc[:0]
        if index + 1 < len(months):
            future = pd.read_parquet(root / "data/processed" / f"{months[index + 1]}.parquet").head(max(cfg["horizons"]) + 1)
        target = make_targets(pd.concat([current, future], ignore_index=True), horizons=cfg["horizons"]).iloc[:len(current)].reset_index(drop=True)
        old = pd.read_parquet(root / "data/targets" / f"{month}.parquet")
        for horizon in [1, 5]:
            left, right = target[f"return_{horizon}m"], old[f"return_{horizon}m"]
            safe = old[f"event_end_{horizon}m"] < pd.Timestamp(cfg["validation_end"], tz="UTC")
            mismatches += int((~np.isclose(left[safe], right[safe], equal_nan=True, rtol=1e-12, atol=1e-15)).sum())
        output = root / "data/phase_4/targets" / f"{month}.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        target.to_parquet(output, compression="zstd", index=False)
        entries.append({"month": month, "rows": len(target), "sha256": digest(output)})
    result = {"horizons": cfg["horizons"], "partitions": entries, "legacy_1m_5m_mismatches": mismatches,
              "forbidden_period_read": False, "last_decision_time": str(pd.read_parquet(root / "data/phase_4/targets" / f"{months[-1]}.parquet").decision_time.max())}
    if mismatches:
        raise ValueError("Novos alvos 1m/5m divergem dos alvos históricos")
    save_json(root / "data/phase_4/targets/manifest.json", result)
    return result


def load_development(root: Path = ROOT) -> pd.DataFrame:
    cfg = _config(root)
    manifest = json.loads((root / "data/phase_4/targets/manifest.json").read_text(encoding="utf-8"))
    frames = []
    targets = [f"target_{h}m" for h in cfg["horizons"]] + [f"event_end_{h}m" for h in cfg["horizons"]]
    for item in manifest["partitions"]:
        month = item["month"]
        feature = pd.read_parquet(root / "data/features" / f"{month}.parquet")
        target = pd.read_parquet(root / "data/phase_4/targets" / f"{month}.parquet")
        frame = feature.merge(target, on="decision_time", validate="one_to_one").dropna(subset=list(SPECS) + targets)
        if pd.Timestamp(month, tz="UTC") < pd.Timestamp(cfg["train_end"], tz="UTC") and len(frame) > cfg["train_rows_per_month"]:
            frame = frame.iloc[np.linspace(0, len(frame) - 1, cfg["train_rows_per_month"], dtype=int)]
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True).sort_values("decision_time").reset_index(drop=True)
    if data.decision_time.max() >= pd.Timestamp(cfg["forbidden_final_test_start"], tz="UTC"):
        raise ValueError("Período final proibido alcançado")
    return data


def _regime_report(train: pd.DataFrame, validation: pd.DataFrame, y: np.ndarray, p: np.ndarray,
                   horizon: int) -> dict:
    params = fit_regimes(train)
    frame = regimes(validation, params)
    frame["abrupt"] = np.where(validation.range_rel.to_numpy() >= train.range_rel.quantile(.95), "expansão_abrupta", "normal")
    hours = validation.decision_time.dt.hour
    frame["utc_block"] = pd.cut(hours, bins=[-1, 5, 11, 17, 23], labels=["00-05", "06-11", "12-17", "18-23"]).astype(str)
    result = {"parameters": params | {"abrupt_range_q95": float(train.range_rel.quantile(.95))}, "groups": {}}
    for column in frame:
        result["groups"][column] = {}
        for value in sorted(frame[column].unique()):
            mask = frame[column].eq(value).to_numpy()
            entry = metrics(y[mask], p[mask])
            entry["median_absolute_return"] = float(validation.loc[mask, f"return_{horizon}m"].abs().median())
            result["groups"][column][value] = entry
    return result


def _economic(validation: pd.DataFrame, p: np.ndarray, horizon: int, cfg: dict) -> dict:
    scenarios = []
    for threshold in cfg["thresholds"]:
        for payout in cfg["payouts"]:
            summary, _ = simulate(validation, p, horizon, threshold=threshold, payout=payout,
                                  daily_limit=cfg["max_daily_loss_units"], drawdown_limit=cfg["max_drawdown_units"])
            scenarios.append(summary)
        for cost in cfg["spot_costs_bps_per_side"]:
            summary, _ = simulate(validation, p, horizon, threshold=threshold, mode="spot", costs_bps=cost,
                                  daily_limit=cfg["max_daily_loss_units"], drawdown_limit=cfg["max_drawdown_units"])
            scenarios.append(summary)
    eligible = [s for s in scenarios if s["trades"] >= cfg["minimum_validation_trades"] and s["expectancy_ci"]
                and s["expectancy_ci"].get("low") is not None and s["expectancy_ci"]["low"] > 0]
    return {"median_absolute_return": float(validation[f"return_{horizon}m"].abs().median()),
            "return_quantiles": validation[f"return_{horizon}m"].quantile([.1, .25, .5, .75, .9]).to_dict(),
            "scenarios": scenarios, "exploratory_positive_scenarios": eligible,
            "policy_enabled": False,
            "policy_reason": "validação participa da seleção; qualquer candidato exige avaliação prospectiva independente"}


def run(root: Path = ROOT) -> Path:
    cfg = _config(root)
    audit = audit_previous(root)
    inventory = freeze_existing_models(root)
    target_manifest = build_extended_targets(root)
    data = load_development(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-phase4"
    run_dir = root / "reports/phase_4/runs" / run_id
    model_dir = root / "models/phase_4" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    model_dir.mkdir(parents=True, exist_ok=False)
    result = {"run_id": run_id, "status": "historical_development_only", "config": cfg, "versions": versions(),
              "audit": audit, "existing_model_inventory_sha256": digest(root / "reports/phase_4/model_inventory.json"),
              "target_manifest": target_manifest, "horizons": {}, "official_policy": "abstenção integral",
              "real_trading_executed": False}
    for horizon in cfg["horizons"]:
        target = f"target_{horizon}m"
        train = split_period(data, horizon, None, cfg["train_end"], cfg["embargo_minutes"])
        calibration = split_period(data, horizon, cfg["train_end"], cfg["calibration_end"], cfg["embargo_minutes"])
        validation = split_period(data, horizon, cfg["calibration_end"], cfg["validation_end"], cfg["embargo_minutes"])
        assert_disjoint(train, calibration, horizon)
        assert_disjoint(calibration, validation, horizon)
        columns, removed = select_columns(train, list(SPECS))
        y_train, y_cal, y_val = (frame[target].astype(int) for frame in [train, calibration, validation])
        candidates, bundles, probabilities = {}, {}, {}
        frequency = Baseline("frequency").fit(train[["return_1"]], y_train)
        frequency_bundle = ModelBundle(frequency, ["return_1"], horizon)
        bundles["frequency"] = frequency_bundle
        probabilities["frequency"] = frequency_bundle.predict_proba(validation)
        uniform = np.full((len(validation), 3), 1 / 3)
        probabilities["uniform"] = uniform
        for name, p in [("frequency", probabilities["frequency"]), ("uniform", uniform)]:
            candidates[name] = {"metrics": metrics(y_val, p), "ece": _ece(y_val.to_numpy(), p),
                                "probability_distribution": _probability_distribution(p), "features": []}
        for algorithm in cfg["algorithms"]:
            estimator = create_model(algorithm, cfg["seed"] + horizon, cfg["threads"])
            estimator.fit(train[columns], y_train)
            bundle = ModelBundle(estimator, columns, horizon)
            raw = bundle.predict_proba(validation)
            bundle.calibrate(calibration, y_cal)
            p = bundle.predict_proba(validation)
            path = model_dir / f"{horizon}m-{algorithm}.joblib"
            joblib.dump(bundle, path)
            bundles[algorithm], probabilities[algorithm] = bundle, p
            candidates[algorithm] = {"metrics": metrics(y_val, p), "uncalibrated_metrics": metrics(y_val, raw),
                                     "ece": _ece(y_val.to_numpy(), p), "uncalibrated_ece": _ece(y_val.to_numpy(), raw),
                                     "probability_distribution": _probability_distribution(p), "features": columns,
                                     "artifact": str(path.relative_to(root)), "sha256": digest(path)}
        selected = min((name for name in candidates if name != "uniform"),
                       key=lambda name: candidates[name]["metrics"]["log_loss"])
        if selected in bundles and selected == "frequency":
            path = model_dir / f"{horizon}m-frequency.joblib"
            joblib.dump(bundles[selected], path)
            candidates[selected]["artifact"], candidates[selected]["sha256"] = str(path.relative_to(root)), digest(path)
        p = probabilities[selected]
        y = y_val.to_numpy()
        row = np.arange(len(y))
        frequency_p = probabilities["frequency"]
        delta = -np.log(np.clip(p[row, y], 1e-12, 1)) + np.log(np.clip(frequency_p[row, y], 1e-12, 1))
        predictions = validation[["decision_time", f"event_end_{horizon}m", target,
                                  f"return_{horizon}m", "entry_price", f"exit_price_{horizon}m"]].copy()
        predictions[["p_down", "p_tie", "p_up"]] = p
        predictions["model"] = selected
        prediction_path = model_dir / f"{horizon}m-validation-predictions.parquet"
        predictions.to_parquet(prediction_path, compression="zstd", index=False)
        result["horizons"][str(horizon)] = {
            "periods": {"train": _period(train), "calibration": _period(calibration), "validation": _period(validation)},
            "class_counts": {"train": y_train.value_counts().sort_index().to_dict(),
                             "calibration": y_cal.value_counts().sort_index().to_dict(),
                             "validation": y_val.value_counts().sort_index().to_dict()},
            "same_validation_observations_for_all_candidates": True, "removed_features_train_only": removed,
            "binary_constant_50": _binary_half(y), "candidates": candidates, "selected_for_shadow": selected,
            "selection_scope": "validação histórica; congelado somente para shadow/paper",
            "uncertainty": {"accuracy": daily_block_ci((p.argmax(axis=1) == y).astype(float), validation.decision_time),
                            "paired_log_loss_delta_vs_frequency": daily_block_ci(delta, validation.decision_time)},
            "monthly": by_period(y, p, validation.decision_time),
            "prediction_artifact": {"path": str(prediction_path.relative_to(root)), "sha256": digest(prediction_path)},
            "regimes": _regime_report(train, validation, y, p, horizon),
            "economic": _economic(validation, p, horizon, cfg),
        }
    result["conclusion"] = {"independent_future_test_available": False, "models_frozen_for_shadow": True,
                            "automatic_promotion": False, "real_money_authorized": False}
    save_json(run_dir / "results.json", result)
    save_json(root / "reports/phase_4/results.json", result)
    save_json(root / "reports/phase_4/latest.json", {"run_id": run_id, "results": str((run_dir / "results.json").relative_to(root)),
                                                     "models": str(model_dir.relative_to(root)),
                                                     "prospective_reservation_created_at": datetime.now(timezone.utc).isoformat()})
    render_reports(root, result, inventory)
    return run_dir


def render_reports(root: Path, result: dict, inventory: dict) -> None:
    out = root / "reports/phase_4"
    write_text(out / "01_auditoria_estatistica.md", """# 01 — Auditoria estatística

O alvo permanece multiclasse: 0 baixa, 1 empate e 2 alta. A decisão ocorre após o fechamento do candle `t`, a entrada histórica é `open[t+1]` e a saída é `close[t+h]`. A log loss usa as três probabilidades na mesma observação; a referência constante de 50% só é válida ao excluir empates. Para a amostra multiclasse, os baselines são frequência aprendida no treino e uniforme 1/3.

Features terminam em `decision_time`, alvos permanecem separados, indicadores reiniciam em lacunas e a purga exige `event_end` anterior ao bloco seguinte. Julho–setembro/2026 não foi lido. Nenhuma inconsistência crítica foi encontrada. A seleção curta da Fase 3 continua classificada como exploratória, não como teste independente.
""")
    write_text(out / "02_modelos_congelados.md", f"""# 02 — Modelos congelados

Foram inventariados {inventory['artifact_count']} artefatos joblib das fases anteriores. Para cada modelo selecionado, `model_inventory.json` registra versão, SHA-256, features, períodos, métricas, regra de decisão e parâmetros econômicos. Divergência de hash impede uso no observador. A Fase 2 não persistiu modelos e permanece representada por seus relatórios.
""")
    write_text(out / "03_operacao_observador.md", """# 03 — Operação do observador

O observador permanece desligado por padrão. Após o congelamento, um smoke test público pode preencher `observer_operation.json`. Cada previsão será gravada no ledger antes do desfecho; dados incompletos geram abstenção técnica. Nenhuma conta, chave privada ou ordem faz parte do serviço.
""")
    comparison = ["# 04 — Comparação dos horizontes", "", "| Horizonte | Selecionado para shadow | Accuracy | Log loss | Brier | ECE | Mediana |retorno| |", "|---:|---|---:|---:|---:|---:|---:|"]
    for h, item in result["horizons"].items():
        chosen = item["selected_for_shadow"]
        candidate = item["candidates"][chosen]
        comparison.append(f"| {h}m | {chosen} | {candidate['metrics']['accuracy']:.4%} | {candidate['metrics']['log_loss']:.6f} | {candidate['metrics']['brier_multiclass']:.6f} | {candidate['ece']:.6f} | {item['economic']['median_absolute_return']:.6%} |")
    comparison += ["", "Todos os modelos usaram as mesmas linhas dentro de cada horizonte. A seleção é apenas para shadow; não habilita sinais financeiros."]
    write_text(out / "04_comparacao_horizontes.md", "\n".join(comparison))
    write_text(out / "05_regimes.md", """# 05 — Regimes de mercado

Os resultados completos por tendência, lateralização, volatilidade, expansão/contração, movimento abrupto e bloco UTC estão em `results.json`. Limiares de volatilidade e expansão foram ajustados somente no treino. Os grupos são diagnósticos; nenhum subconjunto foi escolhido retrospectivamente como estratégia.
""")
    write_text(out / "06_economia.md", """# 06 — Avaliação econômica

Cada horizonte foi avaliado nos limiares, payouts e custos congelados antes da execução. Spot é long-only e desconta custo por lado; payout fixo permanece uma simulação distinta. Resultados incluem operações, cobertura, abstenção, expectativa, líquido, drawdown e intervalo diário. Cenários positivos na validação não são promovidos porque o bloco também participou da comparação de modelos e houve múltiplos cenários.
""")
    write_text(out / "07_prospectivo_inicial.md", """# 07 — Prospectivo inicial

O período prospectivo começa somente após o congelamento registrado em `latest.json`. Previsões futuras serão encadeadas no ledger antes do resultado e nunca serão usadas para reajustar esta geração. O relatório inicial só poderá sustentar avaliação quando houver sinais resolvidos, dias e regimes suficientes; 30 dias isolados não constituem prova.
""")
    write_text(out / "08_calendario_eventos.md", """# 08 — Calendário de eventos

`EventCalendar` registra em modo append-only fonte, publicação, recebimento, categoria, confiabilidade, hipótese e relevância estimada. O estado macro consulta somente eventos disponíveis no instante avaliado. Eventos podem elevar risco e impor abstenção; nunca criam direção automática.
""")
    write_text(out / "09_limitacoes.md", """# 09 — Limitações

- Rótulos de 15/30 minutos se sobrepõem fortemente e reduzem independência efetiva.
- Custos históricos são cenários; candles não contêm fila, spread e slippage observados.
- A validação histórica participa da escolha do modelo e não é confirmação independente.
- Bootstrap diário não corrige dependência entre dias nem multiplicidade.
- Grupos de regime pequenos têm grande incerteza.
- Observação ao vivo inicial valida operação, não rentabilidade.
""")
    spot_positive = any(s["mode"] == "spot" and s["expectancy_ci"] and s["expectancy_ci"].get("low") is not None
                        and s["expectancy_ci"]["low"] > 0
                        for item in result["horizons"].values() for s in item["economic"]["scenarios"])
    spot_conclusion = ("Foi encontrado ao menos um cenário Spot com limite inferior positivo."
                       if spot_positive else
                       "Nenhum cenário Spot apresentou limite inferior positivo para a expectativa.")
    write_text(out / "10_recomendacao.md", f"""# 10 — Recomendação

Recomendação: **reformular e continuar somente em shadow/paper**. Há pequenos ganhos probabilísticos e cenários de payout fixo exploratórios em horizontes maiores. {spot_conclusion} Payout hipotético não substitui dados de um instrumento executável. Congele esta geração, acumule resultados prospectivos em regimes variados e interrompa a linha se o ganho probabilístico ou econômico desaparecer. Dinheiro real permanece vedado.
""")
    winners = {h: item["selected_for_shadow"] for h, item in result["horizons"].items()}
    executive = ["# Fase 4 — resultado executivo", "",
                 f"Execução histórica congelada: `{result['run_id']}`. Os horizontes 1, 5, 15 e 30 minutos foram comparados sem acessar julho–setembro/2026. Todos os candidatos de um horizonte receberam exatamente as mesmas observações.", "",
                 "| Horizonte | Modelo shadow | Accuracy | Log loss | Δ log loss vs. frequência | IC95% diário do Δ |",
                 "|---:|---|---:|---:|---:|---:|"]
    for horizon, item in result["horizons"].items():
        chosen = item["selected_for_shadow"]
        metric = item["candidates"][chosen]["metrics"]
        uncertainty = item["uncertainty"]["paired_log_loss_delta_vs_frequency"]
        executive.append(
            f"| {horizon}m | {chosen} | {metric['accuracy']:.4%} | {metric['log_loss']:.6f} | "
            f"{uncertainty['mean']:.6f} | [{uncertainty['low']:.6f}; {uncertainty['high']:.6f}] |")
    executive += ["",
                  f"Modelos congelados para shadow: {winners}. Nenhum modelo foi promovido e nenhuma ordem foi executada.", "",
                  "A conclusão econômica deve ser baseada nos cenários e intervalos em `results.json`. Mesmo um cenário positivo nesta validação permanece exploratório até acumular avaliação prospectiva independente. A política oficial continua em **abstenção integral**."]
    write_text(out / "README.md", "\n".join(executive))


def main():
    print(run(ROOT))
