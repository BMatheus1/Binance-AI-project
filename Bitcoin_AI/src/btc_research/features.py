"""Features finitas, causais e reproduzíveis com 180 candles de contexto."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .common import ROOT, config, digest, save_json
from .ingestion import require_quality
from .labeling import make_targets

VERSION = "1.0"
SPECS = {
    "return_1": ("PREÇO", "close/close.shift(1)-1", 2, ["close"]),
    "log_return": ("PREÇO", "log(close/close.shift(1))", 2, ["close"]),
    "range_rel": ("VOLATILIDADE", "(high-low)/close", 1, ["high", "low", "close"]),
    "body_rel": ("PRICE ACTION", "abs(close-open)/open", 1, ["open", "close"]),
    "body_fraction": ("PRICE ACTION", "(close-open)/(high-low); zero se range=0", 1, ["open", "high", "low", "close"]),
    "lower_wick": ("PRICE ACTION", "(min(open,close)-low)/(high-low); zero se range=0", 1, ["open", "high", "low", "close"]),
    "upper_wick": ("PRICE ACTION", "(high-max(open,close))/(high-low); zero se range=0", 1, ["open", "high", "low", "close"]),
    "close_position": ("PRICE ACTION", "(close-low)/(high-low); 0.5 se range=0", 1, ["high", "low", "close"]),
    "direction_balance_5": ("PRICE ACTION", "mean(sign(close-open),5)", 5, ["open", "close"]),
    "higher_high": ("TENDÊNCIA", "1(high>high.shift(1))", 2, ["high"]),
    "higher_low": ("TENDÊNCIA", "1(low>low.shift(1))", 2, ["low"]),
    "momentum_5": ("TENDÊNCIA", "close/close.shift(5)-1", 6, ["close"]),
    "momentum_20": ("TENDÊNCIA", "close/close.shift(20)-1", 21, ["close"]),
    "sma_distance_20": ("TENDÊNCIA", "close/mean(close,20)-1", 20, ["close"]),
    "sma_slope_20": ("TENDÊNCIA", "mean(close,20)/mean(close,20).shift(5)-1", 25, ["close"]),
    "ema_distance_20": ("TENDÊNCIA", "close/EMA finita normalizada span20 sobre60-1", 60, ["close"]),
    "macd_rel": ("TENDÊNCIA", "(EMAfinita12-EMAfinita26)/close; ambas janela60", 60, ["close"]),
    "rsi_14": ("TENDÊNCIA", "RSI Cutler: mean(gain,14)/(mean(gain,14)+mean(loss,14)); neutro0.5", 15, ["close"]),
    "atr_rel_14": ("VOLATILIDADE", "mean(max(high-low,abs(high-prevclose),abs(low-prevclose)),14)/close", 15, ["high", "low", "close"]),
    "realized_vol_20": ("VOLATILIDADE", "std(log_return,20,ddof1)", 21, ["close"]),
    "vol_ratio": ("VOLATILIDADE", "std(log_return,20)/std(log_return,60); 1 se ambas zero", 61, ["close"]),
    "bollinger_z": ("VOLATILIDADE", "(close-mean(close,20))/std(close,20); zero se std=0", 20, ["close"]),
    "volume_rel_20": ("VOLUME", "volume/mean(volume,20); 1 se média=0", 20, ["volume"]),
    "volume_change": ("VOLUME", "log1p(volume)-log1p(volume.shift(1))", 2, ["volume"]),
    "trade_intensity": ("VOLUME", "trades/mean(trades,20); 1 se média=0", 20, ["trades"]),
    "taker_buy_ratio": ("VOLUME", "taker_base/volume; 0.5 se volume=0", 1, ["taker_base", "volume"]),
    "signed_volume": ("VOLUME", "sign(close-open)*volume/mean(volume,20)", 20, ["open", "close", "volume"]),
    "breakout_20": ("PRICE ACTION", "close/max(high.shift(1),20)-1", 21, ["high", "close"]),
    "support_distance_20": ("PRICE ACTION", "close/min(low.shift(1),20)-1", 21, ["low", "close"]),
    "hour_sin": ("TEMPO", "sin(2*pi*minute_of_day_at_decision/1440)", 1, ["open_time"]),
    "hour_cos": ("TEMPO", "cos(2*pi*minute_of_day_at_decision/1440)", 1, ["open_time"]),
    "weekday_sin": ("TEMPO", "sin(2*pi*day_of_week_at_decision/7)", 1, ["open_time"]),
    "weekday_cos": ("TEMPO", "cos(2*pi*day_of_week_at_decision/7)", 1, ["open_time"]),
}
for minutes in (5, 15, 30, 60):
    SPECS[f"closed_{minutes}m_return"] = ("TENDÊNCIA", f"close/open-1 do último candle UTC completo de {minutes}m", 2 * minutes, ["open", "close", "open_time"])


def catalog() -> list[dict]:
    return [{"id": name, "name": name, "category": s[0], "description": s[1], "formula": s[1],
             "window_minutes": s[2], "dependencies": s[3], "unit": "adimensional", "source": "Binance Spot BTCUSDT 1m; SHA e source_file em processed",
             "available_at": "open_time + 1min; somente candle encerrado", "hypothesis": "H-" + s[0],
             "missing": "sem imputação; warmup/lacuna = NaN, linha excluída do modelo; divisão por zero conforme fórmula",
             "version": VERSION, "validation_status": "implementada; evidência preditiva em relatórios E/G", "relevance": None} for name, s in SPECS.items()]


def finite_ema(s: pd.Series, span: int) -> pd.Series:
    w = (1 - 2 / (span + 1)) ** np.arange(59, -1, -1)
    w /= w.sum()
    return s.rolling(60).apply(lambda a: np.dot(a, w), raw=True)


def _segment(d: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=d.index)
    o, h, l, c, v = (d[n] for n in ["open", "high", "low", "close", "volume"])
    amplitude = (h - l).replace(0, np.nan)
    x["return_1"] = c.pct_change(fill_method=None)
    x["log_return"] = np.log(c / c.shift())
    x["range_rel"] = (h - l) / c
    x["body_rel"] = (c - o).abs() / o
    x["body_fraction"] = ((c - o) / amplitude).fillna(0)
    x["lower_wick"] = ((pd.concat([o, c], axis=1).min(axis=1) - l) / amplitude).fillna(0)
    x["upper_wick"] = ((h - pd.concat([o, c], axis=1).max(axis=1)) / amplitude).fillna(0)
    x["close_position"] = ((c - l) / amplitude).fillna(0.5)
    x["direction_balance_5"] = np.sign(c - o).rolling(5).mean()
    x["higher_high"] = (h > h.shift()).astype(float).where(h.shift().notna())
    x["higher_low"] = (l > l.shift()).astype(float).where(l.shift().notna())
    for n in (5, 20):
        x[f"momentum_{n}"] = c / c.shift(n) - 1
    sma = c.rolling(20).mean()
    x["sma_distance_20"] = c / sma - 1
    x["sma_slope_20"] = sma / sma.shift(5) - 1
    x["ema_distance_20"] = c / finite_ema(c, 20) - 1
    x["macd_rel"] = (finite_ema(c, 12) - finite_ema(c, 26)) / c
    gain = c.diff().clip(lower=0).rolling(14).mean()
    loss = -c.diff().clip(upper=0).rolling(14).mean()
    x["rsi_14"] = (gain / (gain + loss).replace(0, np.nan)).mask((gain + loss) == 0, 0.5)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    tr.iloc[0] = np.nan
    x["atr_rel_14"] = tr.rolling(14).mean() / c
    vol20, vol60 = x.log_return.rolling(20).std(), x.log_return.rolling(60).std()
    x["realized_vol_20"] = vol20
    x["vol_ratio"] = (vol20 / vol60.replace(0, np.nan)).mask(vol60 == 0, 1)
    std = c.rolling(20).std()
    x["bollinger_z"] = ((c - sma) / std.replace(0, np.nan)).mask(std == 0, 0)
    vmean = v.rolling(20).mean()
    x["volume_rel_20"] = (v / vmean.replace(0, np.nan)).mask(vmean == 0, 1)
    x["volume_change"] = np.log1p(v).diff()
    trades_mean = d.trades.rolling(20).mean()
    x["trade_intensity"] = (d.trades / trades_mean.replace(0, np.nan)).mask(trades_mean == 0, 1)
    x["taker_buy_ratio"] = (d.taker_base / v.replace(0, np.nan)).fillna(0.5)
    x["signed_volume"] = np.sign(c - o) * x.volume_rel_20
    x["breakout_20"] = c / h.shift().rolling(20).max() - 1
    x["support_distance_20"] = c / l.shift().rolling(20).min() - 1
    decision_time = d.open_time + pd.Timedelta(minutes=1)
    minute = decision_time.dt.hour * 60 + decision_time.dt.minute
    x["hour_sin"], x["hour_cos"] = np.sin(2 * np.pi * minute / 1440), np.cos(2 * np.pi * minute / 1440)
    x["weekday_sin"], x["weekday_cos"] = np.sin(2 * np.pi * decision_time.dt.dayofweek / 7), np.cos(2 * np.pi * decision_time.dt.dayofweek / 7)
    for n in (5, 15, 30, 60):
        grouped = d.set_index("open_time").resample(f"{n}min", closed="left", label="right", origin="epoch")
        agg = grouped.agg({"open": "first", "close": "last", "volume": "count"})
        agg = agg[agg.volume == n]
        s = agg.close / agg.open - 1
        x[f"closed_{n}m_return"] = s.reindex(pd.DatetimeIndex(decision_time), method="ffill").to_numpy()
    return x[list(SPECS)].replace([np.inf, -np.inf], np.nan)


def make_features(d: pd.DataFrame) -> pd.DataFrame:
    if d.empty or d.open_time.duplicated().any() or not d.open_time.is_monotonic_increasing:
        raise ValueError("Features exigem candles únicos ordenados e não vazios")
    if d[["open", "high", "low", "close", "volume", "trades", "taker_base"]].isna().any().any():
        raise ValueError("Candle incompleto não aceito; represente lacunas removendo a linha")
    segments = d.open_time.diff().ne(pd.Timedelta(minutes=1)).cumsum()
    f = pd.concat([_segment(group) for _, group in d.groupby(segments)], axis=0).sort_index()
    f.insert(0, "decision_time", d.open_time + pd.Timedelta(minutes=1))
    f.insert(1, "available_at", d.open_time + pd.Timedelta(minutes=1))
    return f


def build(root: Path = ROOT) -> dict:
    quality = require_quality(root)
    c = config(root)
    months = [m["month"] for m in quality["months"]]
    manifest_path = root / "reports/D_features.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    old_parts = {p["month"]: p for p in old.get("partitions", [])}
    parts = []
    source_version = digest(Path(__file__)) + digest(Path(__file__).with_name("labeling.py"))
    for i, month in enumerate(months):
        logging.info("Features e targets %s", month)
        neighbors = months[max(0, i - 1):i + 2]
        key = {"code": source_version, "sources": {m: quality["months"][months.index(m)]["output_sha256"] for m in neighbors}, "tie_tolerance": c["tie_tolerance"]}
        out = root / "data/features" / f"{month}.parquet"
        target = root / "data/targets" / f"{month}.parquet"
        cached = old_parts.get(month, {})
        if cached.get("key") == key and out.exists() and target.exists() and cached.get("features_sha256") == digest(out) and cached.get("targets_sha256") == digest(target):
            parts.append(cached)
            continue
        current = pd.read_parquet(root / "data/processed" / f"{month}.parquet")
        history = pd.read_parquet(root / "data/processed" / f"{months[i - 1]}.parquet").tail(180) if i else current.iloc[:0]
        future = pd.read_parquet(root / "data/processed" / f"{months[i + 1]}.parquet").head(5) if i + 1 < len(months) else current.iloc[:0]
        context = pd.concat([history, current], ignore_index=True)
        f = make_features(context).iloc[len(history):].reset_index(drop=True)
        t = make_targets(pd.concat([context, future], ignore_index=True), tolerance=c["tie_tolerance"]).iloc[len(history):len(context)].reset_index(drop=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        f.to_parquet(out, compression="zstd", index=False)
        t.to_parquet(target, compression="zstd", index=False)
        parts.append({"month": month, "rows": len(f), "warmup_or_missing_rows": int(f[list(SPECS)].isna().any(axis=1).sum()),
                      "key": key, "features_sha256": digest(out), "targets_sha256": digest(target)})
    report = {"version": VERSION, "feature_count": len(SPECS), "partitions": parts, "catalog": catalog()}
    save_json(manifest_path, report)
    save_json(root / "knowledge/feature_catalog.json", catalog())
    return report
