import hashlib
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from btc_research.kronos_adapter import KronosCandidateSpec, paths_to_probabilities, record_shadow_paths
from btc_research.phase5 import _select_even, import_colab_results
from btc_research.prospective import ImmutableLedger


def test_kronos_paths_follow_next_open_convention_and_are_smoothed():
    paths = np.ones((3, 30, 6), dtype=float) * 100
    paths[0, 4, 3] = 99
    paths[1, 4, 3] = 100
    paths[2, 4, 3] = 101
    result = paths_to_probabilities(paths, horizons=[5], smoothing_alpha=.5)[5]
    assert result["probabilities"] == pytest.approx([1 / 3, 1 / 3, 1 / 3])
    assert result["predicted_return_mean"] == pytest.approx(0)


def test_kronos_paths_reject_invalid_shape_or_horizon():
    with pytest.raises(ValueError, match="shape"):
        paths_to_probabilities(np.ones((2, 30, 5)))
    with pytest.raises(ValueError, match="Horizonte"):
        paths_to_probabilities(np.ones((2, 5, 6)), horizons=[30])


def test_phase5_even_selection_is_deterministic_and_ordered():
    frame = pd.DataFrame({"decision_time": pd.date_range("2026-04-01", periods=100, freq="min", tz="UTC")})
    selected = _select_even(frame.sample(frac=1, random_state=5), 8)
    assert len(selected) == 8
    assert selected.decision_time.is_monotonic_increasing
    assert selected.decision_time.iloc[0] == frame.decision_time.iloc[0]
    assert selected.decision_time.iloc[-1] == frame.decision_time.iloc[-1]


def test_phase5_export_manifest_excludes_consumed_final_period():
    path = "reports/phase_5/export_manifest.json"
    manifest = json.load(open(path, encoding="utf-8"))
    assert manifest["forbidden_final_period_exported"] is False
    assert manifest["config"]["validation_end"] == "2026-07-01"
    assert manifest["config"]["local_train_start"] == "2024-07-01"
    for artifact in manifest["artifacts"]:
        data = open("data/phase_5/colab/" + artifact["path"], "rb").read()
        assert hashlib.sha256(data).hexdigest() == artifact["sha256"]


def test_kronos_shadow_integration_records_probabilities_but_always_abstains(tmp_path):
    ledger = ImmutableLedger(tmp_path / "kronos.jsonl")
    spec = KronosCandidateSpec("repo", "model", "model-revision", "tokenizer", "tokenizer-revision")
    paths = np.ones((4, 30, 6), dtype=float) * 100
    records = record_shadow_paths(
        ledger, paths, spec, decision_time=datetime(2026, 10, 1, tzinfo=timezone.utc),
        feature_snapshot_hash="abc", data_quality={"complete": True}, horizons=[1, 30])
    assert len(records) == 2
    assert all(row["decision"] == "abstain_policy" for row in records)
    assert all(row["threshold"] == 1.0 for row in records)
    assert ledger.verify()["predictions"] == 2


def test_phase5_import_accepts_aligned_smoke_and_rejects_economic_mismatch(tmp_path):
    cfg = json.load(open("configs/phase_5.json", encoding="utf-8"))
    root = tmp_path / "root"
    (root / "configs").mkdir(parents=True)
    (root / "configs/phase_5.json").write_text(json.dumps(cfg), encoding="utf-8")
    comparison_dir = root / "data/phase_5/colab"
    comparison_dir.mkdir(parents=True)
    reference = pd.read_parquet("data/phase_5/colab/comparison_validation.parquet").iloc[:2]
    reference.to_parquet(comparison_dir / "comparison_validation.parquet", index=False)
    rows = []
    for _, source in reference.iterrows():
        for horizon in cfg["horizons"]:
            rows.append({
                "decision_time": source.decision_time, "horizon": horizon,
                "variant": "pretrained_raw_smoke", "target": int(source[f"target_{horizon}m"]),
                "actual_return": source[f"return_{horizon}m"], "entry_price": source.entry_price,
                "exit_price": source[f"exit_price_{horizon}m"], "event_end": source[f"event_end_{horizon}m"],
                "p_down": .3, "p_tie": .1, "p_up": .6, "predicted_return": .001,
            })
    source_dir = tmp_path / "colab"
    source_dir.mkdir()
    predictions_path = source_dir / "kronos_predictions.parquet"
    pd.DataFrame(rows).to_parquet(predictions_path, index=False)

    def write_manifest():
        payload = {key: cfg[key] for key in ["official_repository_revision", "model_id", "model_revision",
                                                       "tokenizer_id", "tokenizer_revision"]}
        payload.update({"mode": "smoke", "forbidden_final_period_used": False, "real_orders": False,
                        "prediction_sha256": hashlib.sha256(predictions_path.read_bytes()).hexdigest()})
        (source_dir / "run_manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    write_manifest()
    run = import_colab_results(source_dir, root=root)
    assert (run / "results.json").exists()
    corrupted = pd.read_parquet(predictions_path)
    corrupted.loc[0, "entry_price"] += 1
    corrupted.to_parquet(predictions_path, index=False)
    write_manifest()
    with pytest.raises(ValueError, match="econômicos"):
        import_colab_results(source_dir, root=root)


def test_phase5_colab_bootstrap_is_isolated_and_upload_is_cwd_independent():
    notebook = json.load(open("notebooks/phase5_kronos_colab_v2.ipynb", encoding="utf-8"))
    sources = ["".join(cell.get("source", [])) for cell in notebook["cells"]]
    bootstrap, upload = sources[1], sources[2]
    assert "2026-10-18.3" in bootstrap
    assert "--target" in bootstrap and "phase5_deps" in bootstrap and "--no-deps" in bootstrap
    assert "requirements.txt" not in bootstrap
    assert "os.chdir(CONTENT)" in bootstrap
    assert "archive.write_bytes" in upload
    assert "EXPECTED_ARCHIVE_SHA256" in upload
