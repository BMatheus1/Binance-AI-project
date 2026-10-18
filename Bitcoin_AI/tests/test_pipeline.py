import json
import zipfile

import joblib
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from btc_research.audit import classify
from btc_research.backtesting import break_even, simulate
from btc_research.decision import decisions
from btc_research.external import ExternalEvent
from btc_research.features import SPECS, catalog, make_features
from btc_research.ingestion import COLUMNS, DataQualityError, deduplicate, ingest, read_zip, validate_values
from btc_research.labeling import make_targets
from btc_research.models import ModelBundle, create_model, select_columns
from btc_research.phase2 import EXTENDED_SPECS, _create_estimator, _holm, make_context_features
from btc_research.validation import assert_disjoint, assert_inputs, daily_block_ci, metrics, split_period


def zip_candles(path, df, unit="ms"):
    d = df[COLUMNS].copy()
    # pandas 3 pode usar datetime64[us]; converter explicitamente, sem assumir nanos.
    for col in ["open_time", "close_time"]:
        d[col] = d[col].astype(f"datetime64[{unit}, UTC]").astype("int64")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(path.stem + ".csv", d.to_csv(index=False, header=False))


def test_zip_milliseconds(tmp_path, candles):
    p = tmp_path / "BTCUSDT-1m-2024-01.zip"
    zip_candles(p, candles)
    d, info = read_zip(p)
    assert len(d) == len(candles) and info["unit"] == "ms"
    assert d.open_time.iloc[0] == candles.open_time.iloc[0]
    assert "ignore" not in d


def test_zip_microseconds(tmp_path, candles):
    d = candles.copy()
    d.open_time += pd.DateOffset(years=1)
    d.close_time = d.open_time + pd.Timedelta(minutes=1) - pd.Timedelta(microseconds=1)
    p = tmp_path / "BTCUSDT-1m-2025-01.zip"
    zip_candles(p, d, "us")
    got, info = read_zip(p)
    assert info["unit"] == "us" and got.close_time.iloc[0] == d.close_time.iloc[0]


def test_wrong_timestamp_precision(tmp_path, candles):
    p = tmp_path / "BTCUSDT-1m-2024-01.zip"
    zip_candles(p, candles, "us")
    with pytest.raises(DataQualityError, match="Unidade temporal"):
        read_zip(p)


def test_wrong_month(tmp_path, candles):
    p = tmp_path / "BTCUSDT-1m-2024-02.zip"
    zip_candles(p, candles)
    with pytest.raises(DataQualityError, match="fora do mês"):
        read_zip(p)


def test_invalid_zip(tmp_path):
    p = tmp_path / "BTCUSDT-1m-2024-01.zip"
    p.write_text("not a zip")
    with pytest.raises(DataQualityError, match="ZIP/CSV inválido"):
        read_zip(p)


def test_unknown_file(tmp_path):
    with pytest.raises(DataQualityError, match="incompatível"):
        read_zip(tmp_path / "ETHUSDT-1m-2024-01.zip")
    assert classify(tmp_path / "unknown.bin") == "revisão_manual"


def test_wrong_schema(tmp_path):
    p = tmp_path / "BTCUSDT-1m-2024-01.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(p.stem + ".csv", "1,2,3\n")
    with pytest.raises(DataQualityError, match="12 colunas"):
        read_zip(p)


def test_bad_checksum(tmp_path, candles):
    p = tmp_path / "BTCUSDT-1m-2024-01.zip"
    zip_candles(p, candles)
    p.with_name(p.name + ".CHECKSUM").write_text("0" * 64)
    with pytest.raises(DataQualityError, match="Checksum"):
        read_zip(p)


@pytest.mark.parametrize("column,value", [("open", -1), ("high", 1), ("volume", -2), ("taker_base", 99), ("trades", .5), ("quote_volume", 1)])
def test_impossible_values(candles, column, value):
    candles[column] = candles[column].astype(float)
    candles.loc[5, column] = value
    with pytest.raises(DataQualityError):
        validate_values(candles)


def test_duplicate_and_conflict(candles):
    dup = pd.concat([candles, candles.iloc[:1]])
    cleaned, count = deduplicate(dup)
    assert count == 1 and len(cleaned) == len(candles)
    dup.iloc[-1, dup.columns.get_loc("close")] += 1
    with pytest.raises(DataQualityError, match="conflitantes"):
        deduplicate(dup)


def test_incremental_ingest_and_gap_report(tmp_path, candles):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/research.json").write_text(json.dumps({"raw": "data/raw", "books": "books", "entry_convention": "next_open", "tie_tolerance": 0}))
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    zip_candles(raw / "BTCUSDT-1m-2024-01.zip", candles.drop(index=100))
    first = ingest(tmp_path)
    second = ingest(tmp_path)
    assert first["months"][0]["internal_gap_events"] == 1
    assert first["candles"] == 799 and second["months"][0]["cache_hit"]


def test_catalog_matches_features(candles):
    f = make_features(candles)
    assert set(f.columns) - {"decision_time", "available_at"} == set(SPECS)
    assert set(r["id"] for r in catalog()) == set(SPECS)
    assert all(r["formula"] and r["dependencies"] and r["available_at"] for r in catalog())
    assert not any("target" in c for c in f)


def test_causality_append_and_modify_future(candles):
    prefix = make_features(candles.iloc[:400])
    altered = candles.copy()
    for c in ["open", "high", "low", "close"]:
        altered.loc[400:, c] *= 2
    full = make_features(altered)
    assert_frame_equal(prefix, full.iloc[:400])


def test_no_features_across_gap(candles):
    d = candles.drop(index=400).reset_index(drop=True)
    f = make_features(d)
    assert pd.isna(f.loc[400, "return_1"])
    assert f.loc[400:458, "ema_distance_20"].isna().all()


def test_missing_input_rejected(candles):
    candles.loc[50, "close"] = np.nan
    with pytest.raises(ValueError, match="incompleto"):
        make_features(candles)


def test_closed_multiscale_only(candles):
    f = make_features(candles)
    assert f.loc[:58, "closed_60m_return"].isna().all()
    expected = candles.close.iloc[59] / candles.open.iloc[0] - 1
    assert np.allclose(f.loc[59:118, "closed_60m_return"], expected)
    assert f.loc[119, "closed_60m_return"] == pytest.approx(candles.close.iloc[119] / candles.open.iloc[60] - 1)


def test_partition_context_equivalence(candles):
    full = make_features(candles).iloc[500:]
    chunk = make_features(candles.iloc[320:]).iloc[180:]
    assert_frame_equal(full, chunk, atol=1e-10, rtol=1e-8)


def test_flat_candle_and_indicators(candles):
    d = candles.copy()
    d[["open", "high", "low", "close"]] = 100.
    d.volume = 0.
    d.taker_base = 0.
    f = make_features(d)
    last = f.iloc[-1]
    assert last.rsi_14 == .5 and last.body_fraction == 0 and last.close_position == .5
    assert np.isfinite(last[list(SPECS)].to_numpy(dtype=float)).all()


def test_targets_exact(candles):
    t = make_targets(candles)
    for h in [1, 5]:
        assert t[f"return_{h}m"].iloc[20] == pytest.approx(candles.close.iloc[20 + h] / candles.open.iloc[21] - 1)
        assert t[f"event_end_{h}m"].iloc[20] == candles.open_time.iloc[20] + pd.Timedelta(minutes=h + 1)
        assert t[f"target_{h}m"].tail(h).isna().all()
    assert t.target_1m.iloc[16] == 1


def test_targets_invalidate_cross_gap(candles):
    t = make_targets(candles.drop(index=400).reset_index(drop=True))
    assert t.target_5m.iloc[395:400].isna().all()
    assert pd.isna(t.target_1m.iloc[399])


def test_purged_time_split(candles):
    d = make_features(candles).merge(make_targets(candles), on="decision_time")
    a = split_period(d, 5, None, "2024-01-01 06:00")
    b = split_period(d, 5, "2024-01-01 06:00", "2024-01-01 12:00")
    assert_disjoint(a, b, 5)
    assert a.event_end_5m.max() < b.decision_time.min() - pd.Timedelta(minutes=5)
    with pytest.raises(ValueError, match="sobrepostos"):
        assert_disjoint(b, a, 5)


def test_future_feature_detection(candles):
    f = make_features(candles).dropna()
    with pytest.raises(ValueError, match="catálogo"):
        assert_inputs(f, ["target_1m"])
    f.loc[f.index[-1], "available_at"] += pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match="Vazamento"):
        assert_inputs(f, ["return_1"])


@pytest.mark.parametrize("algorithm", ["logistic", "random_forest", "xgboost", "catboost"])
def test_models_and_persistence(candles, tmp_path, algorithm):
    d = make_features(candles).merge(make_targets(candles), on="decision_time").dropna()
    tr, ca, va = d.iloc[:400], d.iloc[410:520], d.iloc[530:]
    cols, _ = select_columns(tr, list(SPECS))
    model = create_model(algorithm, 42, 2)
    model.fit(tr[cols], tr.target_1m.astype(int))
    bundle = ModelBundle(model, cols, 1)
    bundle.calibrate(ca, ca.target_1m.astype(int))
    p = bundle.predict_proba(va)
    assert p.shape == (len(va), 3) and np.allclose(p.sum(axis=1), 1)
    path = tmp_path / "model.joblib"
    joblib.dump(bundle, path)
    assert np.allclose(joblib.load(path).predict_proba(va), p)


def test_reproducible_training(candles):
    d = make_features(candles).merge(make_targets(candles), on="decision_time").dropna()
    predictions = []
    for _ in range(2):
        model = create_model("logistic", 42, 2)
        model.fit(d.iloc[:400][["return_1"]], d.target_1m.iloc[:400].astype(int))
        predictions.append(model.predict_proba(d.iloc[410:][["return_1"]]))
    assert np.array_equal(*predictions)


def test_metrics_and_bootstrap():
    y = np.array([0, 1, 2] * 100)
    p = np.eye(3)[y] * .9 + .1 / 3
    m = metrics(y, p)
    assert m["accuracy"] == 1 and m["brier_multiclass"] < .01
    times = pd.date_range("2024-01-01", periods=300, freq="h", tz="UTC")
    ci = daily_block_ci(np.ones(300), times)
    assert ci["low"] == ci["high"] == 1


@pytest.mark.parametrize("payout,rate", [(.7, 1 / 1.7), (.8, 1 / 1.8), (.9, 1 / 1.9)])
def test_payout_equilibrium(payout, rate):
    assert break_even(payout) == pytest.approx(rate)


def test_abstention():
    p = np.array([[.45, .1, .45], [.1, .0, .9]])
    assert list(decisions(p, .6)) == [-1, 2]
    assert list(decisions(p, .6, enabled=False)) == [-1, -1]


def test_backtest_no_overlap_and_ties(candles):
    d = make_targets(candles).dropna()
    p = np.tile([.05, .05, .9], (len(d), 1))
    result, trades = simulate(d, p, 5, daily_limit=1e6, drawdown_limit=1e6)
    assert (trades.decision_time.iloc[1:].to_numpy() >= trades.event_end.iloc[:-1].to_numpy()).all()
    assert (trades.loc[trades.tie, "pnl"] == 0).all()
    assert result["net_units"] == pytest.approx(trades.pnl.sum())


def test_spot_long_only_and_costs(candles):
    d = make_targets(candles).dropna()
    down = np.tile([.9, .05, .05], (len(d), 1))
    assert simulate(d, down, 1, mode="spot")[0]["trades"] == 0
    up = np.tile([.05, .05, .9], (len(d), 1))
    cheap = simulate(d, up, 1, mode="spot", costs_bps=5)[0]
    costly = simulate(d, up, 1, mode="spot", costs_bps=20)[0]
    assert costly["net_units"] < cheap["net_units"]


def test_risk_stops(candles):
    d = make_targets(candles).dropna()
    d.target_1m = 0
    p = np.tile([.01, .01, .98], (len(d), 1))
    result, _ = simulate(d, p, 1, daily_limit=3)
    assert result["trades"] == 3 and result["max_drawdown_units"] == 3


def test_external_availability():
    published = pd.Timestamp("2024-01-01", tz="UTC").to_pydatetime()
    received = published + pd.Timedelta(minutes=2)
    event = ExternalEvent("test", "1", "title", "", published, received, "macro", "unknown", "untested")
    assert not event.available_at(published) and event.available_at(received)


def test_final_test_cannot_be_reused(tmp_path):
    from btc_research.training import evaluate
    run = tmp_path / "models/run"
    run.mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    (run / "development.json").write_text(json.dumps({"pilot": False, "config": {"validation_end": "2026-07-01", "test_end": "2026-10-01"}}))
    (tmp_path / "reports/test_registry.json").write_text(json.dumps([{"start": "2026-07-01", "end": "2026-10-01"}]))
    with pytest.raises(ValueError, match="já aberto"):
        evaluate(tmp_path, run)


def test_incomplete_multiscale_candle_is_not_reused_across_gap(candles):
    gapped = candles.drop(index=90).reset_index(drop=True)
    f = make_features(gapped)
    # Segmento novo começa 01:31; primeira hora completa disponível somente às03:00.
    check = f[(f.decision_time > pd.Timestamp('2024-01-01 01:31', tz='UTC')) &
              (f.decision_time < pd.Timestamp('2024-01-01 03:00', tz='UTC'))]
    assert check.closed_60m_return.isna().all()


def test_phase2_context_features_are_causal(candles):
    base = make_features(candles)
    first = make_context_features(base)
    changed = candles.copy()
    changed.loc[150:, "close"] *= 1.01
    changed.loc[150:, "high"] = np.maximum(changed.loc[150:, "high"], changed.loc[150:, "close"])
    second = make_context_features(make_features(changed))
    assert_frame_equal(first.loc[:149, list(EXTENDED_SPECS)], second.loc[:149, list(EXTENDED_SPECS)])


def test_phase2_sequences_restart_after_gap(candles):
    gapped = candles.drop(index=90).reset_index(drop=True)
    result = make_context_features(make_features(gapped))
    restart = result.index[result.decision_time == pd.Timestamp("2024-01-01 01:32", tz="UTC")][0]
    assert result.loc[restart:restart + 3, "doji_frequency_5"].isna().all()


def test_holm_adjustment_is_monotone_and_bounded():
    adjusted = _holm({"a": .01, "b": .03, "c": .2})
    assert 0 <= adjusted["a"] <= adjusted["b"] <= adjusted["c"] <= 1


def test_phase2_logistic_supports_three_classes():
    x = pd.DataFrame({"x": [-2., -1., 0., 1., 2., 3.]})
    y = np.array([0, 0, 1, 1, 2, 2])
    model = _create_estimator("logistic", 42, 1).fit(x, y)
    assert model.predict_proba(x).shape == (6, 3)
