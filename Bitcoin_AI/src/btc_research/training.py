"""Experimentos congelados antes de abrir o teste. Sem promoção automática."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .backtesting import simulate
from .common import ROOT, config, digest, save_json, versions
from .features import SPECS
from .ingestion import require_quality
from .models import Baseline, ModelBundle, create_model, feature_groups, select_columns
from .regimes import fit_regimes, regimes
from .validation import assert_disjoint, assert_inputs, by_period, daily_block_ci, metrics, split_period


def load_data(root: Path, c: dict, start=None, stop=None, sample_train=True) -> pd.DataFrame:
    manifest = json.loads((root / "reports/D_features.json").read_text(encoding="utf-8"))
    frames = []
    for part in manifest["partitions"]:
        month = pd.Timestamp(part["month"], tz="UTC")
        if stop and month >= pd.Timestamp(stop, tz="UTC"):
            continue
        if start and month + pd.offsets.MonthBegin(1) <= pd.Timestamp(start, tz="UTC"):
            continue
        fpath = root / "data/features" / f"{part['month']}.parquet"
        tpath = root / "data/targets" / f"{part['month']}.parquet"
        if digest(fpath) != part["features_sha256"] or digest(tpath) != part["targets_sha256"]:
            raise ValueError("Features/targets alterados; reconstruir antes de treinar")
        f, t = pd.read_parquet(fpath), pd.read_parquet(tpath)
        frame = f.merge(t, on="decision_time", validate="one_to_one").dropna(subset=list(SPECS))
        if start:
            frame = frame[frame.decision_time >= pd.Timestamp(start, tz="UTC")]
        if stop:
            frame = frame[frame.decision_time < pd.Timestamp(stop, tz="UTC")]
        if sample_train and month < pd.Timestamp(c["train_end"], tz="UTC") and len(frame) > c["train_rows_per_month"]:
            frame = frame.iloc[np.linspace(0, len(frame) - 1, c["train_rows_per_month"], dtype=int)]
        frames.append(frame)
    if not frames:
        raise ValueError("Sem partições no período solicitado")
    return pd.concat(frames, ignore_index=True).sort_values("decision_time").reset_index(drop=True)


def _period(d: pd.DataFrame) -> dict:
    return {"rows": len(d), "start": str(d.decision_time.min()), "end": str(d.decision_time.max())}


def permutation_report(bundle: ModelBundle, val: pd.DataFrame, h: int, seed: int) -> dict:
    # Interpretação exploratória exclusivamente na validação; deslocamentos circulares preservam parte da estrutura local.
    sample = val.iloc[::max(1, len(val) // 12000)].copy()
    y = sample[f"target_{h}m"].astype(int)
    base = metrics(y, bundle.predict_proba(sample))["log_loss"]
    rng = np.random.default_rng(seed)
    result = {}
    groups = {col: [col] for col in bundle.columns}
    for category in sorted({SPECS[c][0] for c in bundle.columns}):
        groups["group:" + category] = [c for c in bundle.columns if SPECS[c][0] == category]
    for label, cols in groups.items():
        scores = []
        for _ in range(2):
            changed = sample.copy()
            offset = int(rng.integers(60, len(sample) - 60))
            changed[cols] = np.roll(changed[cols].to_numpy(), offset, axis=0)
            scores.append(metrics(y, bundle.predict_proba(changed))["log_loss"] - base)
        result[label] = {"delta_log_loss_mean": float(np.mean(scores)), "delta_log_loss_std": float(np.std(scores))}
    return {"method": "2 deslocamentos circulares por feature/grupo, validação; exploratório, sem causalidade", "n": len(sample), "importance": result}


def walk_forward(data: pd.DataFrame, c: dict, h: int) -> list:
    folds = [("2024-10-01", "2025-01-01", "2025-04-01"), ("2025-04-01", "2025-07-01", "2025-10-01")]
    output = []
    for train_end, cal_end, val_end in folds:
        train = split_period(data, h, None, train_end)
        cal = split_period(data, h, train_end, cal_end)
        val = split_period(data, h, cal_end, val_end)
        if min(len(train), len(cal), len(val)) < 1000:
            continue
        assert_disjoint(train, cal, h)
        assert_disjoint(cal, val, h)
        cols, _ = select_columns(train, list(SPECS))
        estimator = create_model("logistic", c["seed"], c["threads"])
        estimator.fit(train[cols], train[f"target_{h}m"].astype(int))
        bundle = ModelBundle(estimator, cols, h)
        bundle.calibrate(cal, cal[f"target_{h}m"].astype(int))
        baseline = Baseline().fit(train[["return_1"]], train[f"target_{h}m"].astype(int))
        output.append({"train": _period(train), "calibration": _period(cal), "validation": _period(val),
                       "logistic": metrics(val[f"target_{h}m"], bundle.predict_proba(val)),
                       "frequency": metrics(val[f"target_{h}m"], baseline.predict_proba(val[["return_1"]]))})
    return output


def train(root: Path = ROOT, pilot=False) -> Path:
    quality = require_quality(root)
    c = config(root)
    if pilot:
        c.update(train_end="2023-11-01", calibration_end="2023-11-11", validation_end="2023-11-21", test_end="2023-12-01", train_rows_per_month=3000)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ("-pilot" if pilot else "-research")
    run = root / "models/trained" / run_id
    run.mkdir(parents=True, exist_ok=False)
    report = {"run_id": run_id, "pilot": pilot, "config": c, "versions": versions(), "quality_manifest_sha256": digest(root / "reports/B_quality.json"),
              "features_manifest_sha256": digest(root / "reports/D_features.json"), "source_hashes": {p.name: digest(p) for p in Path(__file__).parent.glob("*.py")},
              "sampling": "Até N posições igualmente espaçadas por mês só no treino; demais períodos completos.",
              "test_status": "unopened", "horizons": {}}
    data = load_data(root, c, stop=c["validation_end"])
    for h in c["horizons"]:
        logging.info("Treino horizonte %sm", h)
        d = data.dropna(subset=[f"target_{h}m", f"event_end_{h}m"])
        tr = split_period(d, h, None, c["train_end"], c["embargo_minutes"])
        ca = split_period(d, h, c["train_end"], c["calibration_end"], c["embargo_minutes"])
        va = split_period(d, h, c["calibration_end"], c["validation_end"], c["embargo_minutes"])
        assert_disjoint(tr, ca, h)
        assert_disjoint(ca, va, h)
        assert_inputs(tr, list(SPECS))
        ytr, yca, yva = (z[f"target_{h}m"].astype(int) for z in [tr, ca, va])
        candidates, bundles = {}, {}
        for name in ["frequency", "constant", "momentum", "reversion"]:
            baseline = Baseline(name).fit(tr[["return_1"]], ytr)
            bundle = ModelBundle(baseline, ["return_1"], h)
            candidates[name] = {"validation": metrics(yva, bundle.predict_proba(va)), "features": bundle.columns, "calibrated": False, "parameters": {"name": name}}
            bundles[name] = bundle
        combinations = [("logistic_" + group, "logistic", columns) for group, columns in feature_groups().items()]
        combinations += [(name, name, list(SPECS)) for name in ["random_forest", "xgboost", "catboost"]]
        for label, algorithm, cols in combinations:
            logging.info("Horizonte %sm: %s", h, label)
            cols, removed = select_columns(tr, cols)
            estimator = create_model(algorithm, c["seed"], c["threads"])
            estimator.fit(tr[cols], ytr)
            bundle = ModelBundle(estimator, cols, h)
            raw = metrics(yva, bundle.predict_proba(va))
            bundle.calibrate(ca, yca)
            candidates[label] = {"validation": metrics(yva, bundle.predict_proba(va)), "uncalibrated_validation": raw, "features": cols,
                                 "removed": removed, "calibrated": True, "parameters": {k: str(v) if isinstance(v, float) and not np.isfinite(v) else v for k, v in estimator.get_params(deep=True).items() if isinstance(v, (int, float, bool, str, type(None)))}}
            bundles[label] = bundle
        winner = min(candidates, key=lambda n: candidates[n]["validation"]["log_loss"])
        logging.info("Horizonte %sm selecionado em validação: %s", h, winner)
        for name, bundle in bundles.items():
            joblib.dump(bundle, run / f"{h}m-{name}.joblib")
            candidates[name]["artifact_sha256"] = digest(run / f"{h}m-{name}.joblib")
        chosen = bundles[winner]
        p = chosen.predict_proba(va)
        threshold_trials = []
        for threshold in c["thresholds"]:
            result, _ = simulate(va, p, h, threshold=threshold, daily_limit=c["max_daily_loss_units"], drawdown_limit=c["max_drawdown_units"])
            threshold_trials.append(result)
        eligible = [r for r in threshold_trials if r["trades"] >= c["minimum_validation_trades"] and r["expectancy_ci"] and r["expectancy_ci"]["low"] is not None and r["expectancy_ci"]["low"] > 0]
        policy = {"enabled": bool(eligible), "threshold": max(eligible, key=lambda r: r["expectancy_ci"]["low"])["threshold"] if eligible else max(c["thresholds"]),
                  "reason": "Limite inferior do IC diário positivo em validação" if eligible else "Nenhum limiar atingiu evidência mínima de expectativa positiva; abstenção integral",
                  "payout_reference": .8}
        item = {"periods": {"train": _period(tr), "calibration": _period(ca), "validation": _period(va)},
                "class_counts_train": {str(k): int(v) for k, v in ytr.value_counts().items()}, "candidates": candidates, "selected": winner,
                "policy": policy, "threshold_validation": threshold_trials, "regime_parameters": fit_regimes(tr),
                "walk_forward": walk_forward(d, c, h) if not pilot else [], "interpretability": permutation_report(chosen, va, h, c["seed"]),
                "validation_monthly": by_period(yva, p, va.decision_time)}
        report["horizons"][str(h)] = item
        save_json(run / "development.json", report)
    # Referência de drift é ajustada exclusivamente no treino.
    reference = data[data.decision_time < pd.Timestamp(c["train_end"], tz="UTC")]
    report["drift_reference"] = {}
    for col in SPECS:
        edges = np.unique(np.quantile(reference[col], np.linspace(0, 1, 11)))
        if len(edges) > 2:
            edges[0], edges[-1] = -1e100, 1e100
            counts = np.histogram(reference[col], bins=edges)[0]
            report["drift_reference"][col] = {"edges": edges.tolist(), "proportions": ((counts + .5) / (counts.sum() + .5 * len(counts))).tolist()}
    save_json(run / "development.json", report)
    save_json(root / "reports/experiments" / f"{run_id}.json", report)
    save_json(root / "reports/latest_development.json", {"run": str(run.relative_to(root)), "pilot": pilot})
    return run


def evaluate(root: Path = ROOT, run: Path | None = None) -> dict:
    if run is None:
        pointer = json.loads((root / "reports/latest_development.json").read_text(encoding="utf-8"))
        run = root / pointer["run"]
    report = json.loads((run / "development.json").read_text(encoding="utf-8"))
    c = report["config"]
    registry_path = root / "reports/test_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else []
    if not report["pilot"] and any(r["start"] < c["test_end"] and r["end"] > c["validation_end"] for r in registry):
        raise ValueError("Teste final já aberto ou reservado. Novas escolhas exigem outro período futuro independente.")
    require_quality(root)
    if digest(root / "reports/D_features.json") != report["features_manifest_sha256"]:
        raise ValueError("Dataset mudou após desenvolvimento")
    for name, sha in report["source_hashes"].items():
        if digest(Path(__file__).parent / name) != sha:
            raise ValueError("Código mudou após desenvolvimento; repetir desenvolvimento antes de abrir teste")
    # Reserva persistente ANTES de ler o teste: falhas posteriores não apagam exposição.
    if not report["pilot"]:
        registry.append({"run": report["run_id"], "start": c["validation_end"], "end": c["test_end"], "status": "reserved_before_read",
                         "development_sha256": digest(run / "development.json")})
        save_json(registry_path, registry)
    data = load_data(root, c, start=c["validation_end"], stop=c["test_end"], sample_train=False)
    result = {"run_id": report["run_id"], "pilot": report["pilot"], "horizons": {}, "drift_psi": {}}
    for col, ref in report["drift_reference"].items():
        counts = np.histogram(data[col], bins=ref["edges"])[0]
        observed = (counts + .5) / (counts.sum() + .5 * len(counts))
        expected = np.array(ref["proportions"])
        result["drift_psi"][col] = float(np.sum((observed - expected) * np.log(observed / expected)))
    for hstr, item in report["horizons"].items():
        h = int(hstr)
        d = split_period(data.dropna(subset=[f"target_{h}m", f"event_end_{h}m"]), h, c["validation_end"], c["test_end"], c["embargo_minutes"])
        y = d[f"target_{h}m"].astype(int).to_numpy()
        comparisons, probabilities = {}, {}
        for name, candidate in item["candidates"].items():
            artifact = run / f"{h}m-{name}.joblib"
            if digest(artifact) != candidate["artifact_sha256"]:
                raise ValueError("Modelo alterado desde seleção")
            model = joblib.load(artifact)  # somente artefatos locais recém-criados e conferidos
            p = model.predict_proba(d)
            probabilities[name] = p
            comparisons[name] = metrics(y, p)
        p = probabilities[item["selected"]]
        freq = probabilities["frequency"]
        loss_delta = -np.log(p[np.arange(len(y)), y].clip(1e-9)) + np.log(freq[np.arange(len(y)), y].clip(1e-9))
        policy = item["policy"]
        params = {"threshold": policy["threshold"], "enabled": policy["enabled"], "daily_limit": c["max_daily_loss_units"], "drawdown_limit": c["max_drawdown_units"]}
        backtests = []
        for payout in c["payouts"]:
            bt, trades = simulate(d, p, h, payout=payout, **params)
            trades.to_parquet(run / f"{h}m-trades-payout{payout}.parquet", index=False)
            backtests.append(bt)
        for cost in c["spot_costs_bps_per_side"]:
            bt, _ = simulate(d, p, h, mode="spot", costs_bps=cost, **params)
            backtests.append(bt)
        sensitivity = [simulate(d, p, h, threshold=threshold, daily_limit=c["max_daily_loss_units"], drawdown_limit=c["max_drawdown_units"])[0] for threshold in c["thresholds"]]
        rg = regimes(d, item["regime_parameters"])
        regime_metrics = {}
        for kind in rg:
            for name in rg[kind].unique():
                mask = (rg[kind] == name).to_numpy()
                regime_metrics[f"{kind}:{name}"] = metrics(y[mask], p[mask])
        # Mesma trajetória de risco; apenas atribuir operações aos regimes observados na entrada.
        _, ledger = simulate(d, p, h, **params)
        regime_pnl = {}
        if len(ledger):
            tagged = ledger.merge(pd.concat([d[["decision_time"]], rg], axis=1), on="decision_time", validate="one_to_one")
            for kind in rg:
                regime_pnl[kind] = tagged.groupby(kind).pnl.agg(["count", "sum", "mean"]).to_dict(orient="index")
        predictions = d[["decision_time", f"event_end_{h}m", f"target_{h}m", f"return_{h}m", "entry_price", f"exit_price_{h}m"]].copy()
        predictions[["p_down", "p_tie", "p_up"]] = p
        predictions["model_id"] = report["run_id"] + ":" + item["selected"]
        predictions["split"] = "pilot_development_holdout" if report["pilot"] else "final_test"
        predictions.to_parquet(run / f"{h}m-oos_predictions.parquet", index=False)
        result["horizons"][hstr] = {"period": _period(d), "selected_before_test": item["selected"], "policy_frozen": policy,
                                   "comparison": comparisons, "monthly": by_period(y, p, d.decision_time), "regimes": regime_metrics,
                                   "accuracy_daily_ci": daily_block_ci((p.argmax(axis=1) == y).astype(float), d.decision_time),
                                   "paired_log_loss_delta_vs_frequency_ci": daily_block_ci(loss_delta, d.decision_time),
                                   "backtests": backtests, "pnl_by_regime": regime_pnl,
                                   "threshold_sensitivity_descriptive_only": sensitivity}
    save_json(run / "evaluation.json", result)
    if not report["pilot"]:
        registry[-1]["status"] = "evaluated"
        save_json(registry_path, registry)
        save_json(root / "reports/final_evaluation.json", result)
    return result
