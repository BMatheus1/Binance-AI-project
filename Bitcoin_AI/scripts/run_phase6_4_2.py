"""Read-only research/audit commands. No order/authentication API is imported."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from btc_research.common import digest, save_json
from btc_research.unified_intelligence import UnifiedDecisionStore

REPORTS = ROOT / "reports/phase_6_4_2"


def audit() -> dict:
    """Parse every first-party Python file and enumerate each product source."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    python_paths = [*sorted((ROOT / "src").rglob("*.py")),
                    *sorted((ROOT / "scripts").glob("*.py")),
                    *sorted((ROOT / "tests").rglob("*.py"))]
    product_paths = [path for path in (ROOT / "dashboard/frontend").rglob("*")
                     if path.is_file() and path.suffix in {".tsx", ".ts", ".css", ".json"}
                     and not {"node_modules", ".next"}.intersection(path.parts)]
    sources, edges = [], []
    for path in python_paths:
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.append(("." * node.level) + (node.module or ""))
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
        relative = path.relative_to(ROOT).as_posix()
        definitions = [{"name": node.name, "line": node.lineno,
                        "kind": type(node).__name__} for node in tree.body
                       if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
        sources.append({"path": relative, "sha256": digest(path), "lines": len(text.splitlines()),
                        "definitions": definitions, "imports": sorted(set(imports))})
        edges.extend({"consumer": relative, "dependency": value} for value in sorted(set(imports)))
    source_inventory = {"audited_at": datetime.now(timezone.utc).isoformat(),
                        "python_sources": sources, "dependency_edges": edges,
                        "product_sources": [{"path": path.relative_to(ROOT).as_posix(),
                                             "sha256": digest(path)} for path in product_paths]}
    save_json(REPORTS / "source_inventory.json", source_inventory)
    protected = [*sorted((ROOT / "configs").glob("*.json")),
                 ROOT / "reports/test_registry.json"]
    for phase in ("phase_2", "phase_3", "phase_4", "phase_5", "phase_6", "phase_6_1", "phase_6_2"):
        protected.extend(path for path in (ROOT / "reports" / phase).rglob("*")
                         if path.is_file() and path.suffix in {".json", ".md", ".csv"})
    # Hash frozen predictor weights; giant raw archives/books are untouched.
    weights = list((ROOT / "models").rglob("*.joblib"))
    manifest = {path.relative_to(ROOT).as_posix(): digest(path) for path in [*protected, *weights]}
    baseline = REPORTS / "preservation_before.json"
    if not baseline.exists():
        save_json(baseline, manifest)
    save_json(REPORTS / "preservation_current.json", manifest)
    original = json.loads(baseline.read_text(encoding="utf-8"))
    differences = [path for path, expected in original.items() if manifest.get(path) != expected]
    save_json(REPORTS / "preservation_verification.json", {
        "checked_at": datetime.now(timezone.utc).isoformat(), "files": len(original),
        "differences": differences, "datasets_and_books_touched": False,
        "reserved_holdout_used_for_fitting": False})
    inventories = {}
    for name in ("phase_4/model_inventory.json", "phase_4/results.json",
                 "phase_5/full_analysis.json", "phase_5/validation.json",
                 "phase_6_1/model_inventory.json", "phase_3/results.json"):
        path = ROOT / "reports" / name
        if path.exists():
            inventories[name] = {"source": str(path), "sha256": digest(path),
                                 "content": json.loads(path.read_text(encoding="utf-8"))}
    save_json(REPORTS / "model_evidence_inventory.json", inventories)
    return {"python_files_parsed": len(sources), "product_files": len(product_paths),
            "frozen_joblib_files": len(weights), "protected_files": len(original),
            "preservation_differences": differences, "orders_sent": False}


def evidence() -> dict:
    database = ROOT / "runtime/phase_6_1/evaluations.sqlite3"
    decisions = UnifiedDecisionStore.recent(database, 30)
    engine = json.loads((ROOT / "runtime/phase_6_4/engine.json").read_text(encoding="utf-8"))
    kill = json.loads((ROOT / "runtime/phase_6_2/kill_switch.json").read_text(encoding="utf-8"))
    heartbeat = json.loads((ROOT / "runtime/phase_6_1/heartbeat.json").read_text(encoding="utf-8"))
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as db:
        counts = dict(db.execute("SELECT decision,COUNT(*) FROM unified_decisions GROUP BY decision"))
    result = {"collected_at": datetime.now(timezone.utc).isoformat(), "engine": engine,
              "kill_switch": kill, "unified_decision_counts": counts,
              "recent_decisions": decisions,
              "quantitative_worker": heartbeat.get("decision_worker"),
              "news_context_worker": heartbeat.get("news_decision_worker"),
              "orders_sent_by_audit": False, "production_supported": False}
    save_json(REPORTS / "runtime_evidence.json", result)
    return {"collected_at": result["collected_at"], "engine_state": engine["state"],
            "orders_enabled": engine["orders_enabled"], "kill_switch": kill["engaged"],
            "unified_decision_counts": counts, "latest_at": decisions[0]["evaluated_at"] if decisions else None}


def benchmarks() -> dict:
    """Recompute descriptive comparisons on existing aligned development exports.

    No fit, threshold search, holdout read, or automatic promotion takes place.
    April--June was previously consumed for selection: this is NOT a final test.
    """
    import numpy as np
    import pandas as pd
    from sklearn.metrics import log_loss, accuracy_score

    kronos_path = ROOT / "models/phase_5/20261018T152415Z-kronos/kronos_predictions.parquet"
    pointer = json.loads((ROOT / "reports/phase_4/latest.json").read_text(encoding="utf-8"))
    frame = pd.read_parquet(kronos_path)
    times = pd.to_datetime(frame.decision_time, utc=True)
    if ((times >= "2026-07-01") & (times < "2026-10-01")).any():
        raise ValueError("forbidden holdout in comparison export")
    result = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "interpretation": "exploratory previously consumed development validation; no fitting",
              "threshold_frozen": .60, "source_sha256": digest(kronos_path), "horizons": {},
              "no_ensemble_promoted": True, "holdout_reused": False}

    def metrics(probabilities, target, gross):
        probabilities = np.asarray(probabilities, float)
        selected = (probabilities.argmax(axis=1) == 2) & (probabilities[:, 2] >= .60)
        confidence = probabilities.max(axis=1)
        correctness = probabilities.argmax(axis=1) == target
        ece = 0.0
        for lower in np.arange(0, 1, .1):
            mask = (confidence >= lower) & (confidence < lower + .1 + (1e-10 if lower > .8 else 0))
            if mask.any():
                ece += mask.mean() * abs(confidence[mask].mean() - correctness[mask].mean())
        return {"observations": len(target), "accuracy": float(accuracy_score(target, probabilities.argmax(axis=1))),
                "log_loss": float(log_loss(target, probabilities, labels=[0, 1, 2])),
                "brier_multiclass": float(np.mean(np.sum((probabilities - np.eye(3)[target]) ** 2, axis=1))),
                "ece_10_bins": float(ece), "long_signals": int(selected.sum()),
                "abstention_fraction": float(1 - selected.mean()),
                "spot_cost_sensitivity": {str(cost): {
                    "assumed_round_trip_bps": cost,
                    "mean_net_bps_per_selected_opportunity": float((gross[selected] * 10000 - cost).mean()) if selected.any() else None,
                    "source": "historical_candle_return_minus_cost_scenario_not_exchange_fills",
                    "overlapping_opportunities_are_not_a_portfolio_backtest": True}
                    for cost in (10, 14, 20)}, "always_abstain_net_quote": 0}

    for horizon in (1, 5, 15, 30):
        frozen = pd.read_parquet(ROOT / pointer["models"] / f"{horizon}m-validation-predictions.parquet")
        frozen_times = pd.to_datetime(frozen.decision_time, utc=True)
        if ((frozen_times >= "2026-07-01") & (frozen_times < "2026-10-01")).any():
            raise ValueError("forbidden holdout in frozen model export")
        blocks = {}
        for variant, candidate in frame[frame.horizon == horizon].groupby("variant"):
            joined = candidate.merge(frozen, on="decision_time", suffixes=("_kronos", "_frozen"), validate="one_to_one")
            if joined.empty or not np.array_equal(joined.target, joined[f"target_{horizon}m"]):
                raise ValueError("unaligned labels in expert comparison")
            target = joined.target.to_numpy(int)
            gross = joined.actual_return.to_numpy(float)
            blocks[str(variant)] = {
                "same_observation_ids": hashlib.sha256("|".join(map(str, joined.decision_time)).encode()).hexdigest(),
                "first_decision": str(joined.decision_time.min()), "last_decision": str(joined.decision_time.max()),
                "kronos": metrics(joined[[f"p_{key}_kronos" for key in ("down", "tie", "up")]], target, gross),
                "frozen_specialist": metrics(joined[[f"p_{key}_frozen" for key in ("down", "tie", "up")]], target, gross),
                "frozen_model": sorted(joined.model.unique().tolist())}
        result["horizons"][str(horizon)] = blocks
    result["unavailable_comparisons"] = {
        "stacking_and_calibrated_fusion": "no aligned OOF development predictions for all experts; arbitrary weights forbidden",
        "news_microstructure_regime_timing_ablations": "no paired timestamped OOS forecasts with identical inputs and costs",
        "adaptive_exit_ablation": "requires recorded executable bid/ask paths for identical prospective entries",
        "momentum_mean_reversion": "not preregistered for historical comparisons; collect new forward observations"}
    save_json(REPORTS / "expert_comparison.json", result)
    return {"horizons": list(result["horizons"]), "variants": 4, "fitting_performed": False,
            "economic_advantage_claimed": False, "orders_sent": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auditoria Fase 6.4.2; sem ordens")
    parser.add_argument("command", choices=("audit", "evidence", "benchmarks"))
    args = parser.parse_args()
    print(json.dumps({"audit": audit, "evidence": evidence, "benchmarks": benchmarks}[args.command](), indent=2))
