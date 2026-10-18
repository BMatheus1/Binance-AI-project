"""Ingestão oficial de AggTrades e atributos causais de microestrutura.

Os ZIPs originais são imutáveis. A normalização escreve partes Parquet e um
agregado por minuto; nenhum dado posterior ao fechamento do minuto entra nas
features disponibilizadas para a decisão seguinte.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .common import ROOT, digest, save_json

AGG_COLUMNS = [
    "aggregate_trade_id", "price", "quantity", "first_trade_id",
    "last_trade_id", "transact_time", "is_buyer_maker", "is_best_match",
]

MICRO_SPECS = {
    "flow_imbalance": "(taker_buy_base-taker_sell_base)/base_volume",
    "buy_share": "taker_buy_base/base_volume",
    "volume_delta": "taker_buy_base-taker_sell_base",
    "mean_aggtrade_size": "base_volume/aggtrade_count",
    "avg_trades_per_aggtrade": "underlying_trade_count/aggtrade_count",
    "quote_per_aggtrade": "quote_volume/aggtrade_count",
    "aggtrades_per_second": "aggtrade_count/60",
    "cum_delta_5": "soma(volume_delta,5)/soma(base_volume,5)",
    "cum_delta_20": "soma(volume_delta,20)/soma(base_volume,20)",
    "cum_delta_60": "soma(volume_delta,60)/soma(base_volume,60)",
    "aggtrade_intensity_5": "aggtrade_count/média(aggtrade_count,5)",
    "aggtrade_intensity_20": "aggtrade_count/média(aggtrade_count,20)",
    "aggtrade_intensity_60": "aggtrade_count/média(aggtrade_count,60)",
    "underlying_trade_intensity_20": "underlying_trade_count/média(underlying_trade_count,20)",
    "size_shock_20": "mean_aggtrade_size/média(mean_aggtrade_size,20)",
    "activity_shock_20": "quote_volume/média(quote_volume,20)",
    "flow_persistence_5": "média(sinal(volume_delta),5)",
    "flow_persistence_20": "média(sinal(volume_delta),20)",
    "price_flow_divergence_5": "abs(retorno5) se sinais de retorno e delta5 divergem; senão 0",
    "price_flow_divergence_20": "abs(retorno20) se sinais de retorno e delta20 divergem; senão 0",
}


class AggTradeQualityError(ValueError):
    pass


def official_urls(base: str, symbol: str, day: date) -> tuple[str, str, str]:
    name = f"{symbol}-aggTrades-{day.isoformat()}.zip"
    url = f"{base.rstrip('/')}/{symbol}/{name}"
    return name, url, url + ".CHECKSUM"


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "bitcoin-ai-research/phase3"})
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    partial.replace(destination)


def download_pilot(root: Path = ROOT) -> dict:
    """Baixa somente o intervalo congelado e valida SHA-256 oficial."""
    cfg = json.loads((root / "configs/phase_3.json").read_text(encoding="utf-8"))
    start = date.fromisoformat(cfg["pilot_start"])
    end = date.fromisoformat(cfg["pilot_end_inclusive"])
    raw = root / "data/phase_3/raw/aggTrades/BTCUSDT"
    records = []
    current = start
    while current <= end:
        name, url, checksum_url = official_urls(cfg["official_archive_base"], cfg["symbol"], current)
        archive, checksum_path = raw / name, raw / (name + ".CHECKSUM")
        if not archive.exists():
            _download(url, archive)
        if not checksum_path.exists():
            _download(checksum_url, checksum_path)
        expected = checksum_path.read_text(encoding="utf-8").strip().split()[0].lower()
        actual = digest(archive)
        if len(expected) != 64 or actual != expected:
            raise AggTradeQualityError(f"Checksum oficial inválido: {name}")
        records.append({"date": current.isoformat(), "file": str(archive.relative_to(root)),
                        "url": url, "checksum_url": checksum_url, "sha256": actual,
                        "bytes": archive.stat().st_size})
        current += timedelta(days=1)
    manifest = {"source": "Binance Public Data Spot daily aggTrades", "symbol": cfg["symbol"],
                "period": [start.isoformat(), end.isoformat()], "files": records}
    save_json(root / "data/phase_3/manifests/download.json", manifest)
    return manifest


def _bool_series(series: pd.Series, name: str) -> pd.Series:
    values = series.astype(str).str.lower().map({"true": True, "false": False})
    if values.isna().any():
        raise AggTradeQualityError(f"Booleano inválido em {name}")
    return values.astype(bool)


def read_aggtrade_chunks(path: Path, chunksize: int = 250_000):
    """Lê o único CSV do ZIP sem expandi-lo em memória."""
    try:
        archive = zipfile.ZipFile(path)
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise AggTradeQualityError("ZIP deve conter exatamente um CSV")
        stream = archive.open(members[0])
        first = stream.readline().decode("utf-8", errors="replace")
        stream.close()
        has_header = "aggregate" in first.lower() or "trade_id" in first.lower()
        stream = archive.open(members[0])
    except (OSError, zipfile.BadZipFile) as exc:
        raise AggTradeQualityError(f"ZIP/CSV inválido: {path.name}") from exc
    try:
        reader = pd.read_csv(stream, names=AGG_COLUMNS, header=0 if has_header else None,
                             chunksize=chunksize, low_memory=False)
        for frame in reader:
            if frame.shape[1] != len(AGG_COLUMNS):
                raise AggTradeQualityError("AggTrades requer 8 colunas")
            for col in ["aggregate_trade_id", "first_trade_id", "last_trade_id", "transact_time"]:
                frame[col] = pd.to_numeric(frame[col], errors="raise").astype("int64")
            for col in ["price", "quantity"]:
                frame[col] = pd.to_numeric(frame[col], errors="raise").astype("float64")
            frame["is_buyer_maker"] = _bool_series(frame["is_buyer_maker"], "is_buyer_maker")
            frame["is_best_match"] = _bool_series(frame["is_best_match"], "is_best_match")
            frame["event_time"] = pd.to_datetime(frame.transact_time, unit="us", utc=True)
            yield frame
    finally:
        stream.close()
        archive.close()


def _partial_minutes(frame: pd.DataFrame) -> pd.DataFrame:
    d = frame.copy()
    d["minute"] = d.event_time.dt.floor("min")
    d["notional"] = d.price * d.quantity
    d["buy_base"] = d.quantity.where(~d.is_buyer_maker, 0.0)
    d["sell_base"] = d.quantity.where(d.is_buyer_maker, 0.0)
    d["buy_quote"] = d.notional.where(~d.is_buyer_maker, 0.0)
    d["underlying"] = d.last_trade_id - d.first_trade_id + 1
    return d.groupby("minute", sort=True).agg(
        open=("price", "first"), high=("price", "max"), low=("price", "min"),
        close=("price", "last"), base_volume=("quantity", "sum"),
        quote_volume=("notional", "sum"), aggtrade_count=("aggregate_trade_id", "size"),
        underlying_trade_count=("underlying", "sum"), taker_buy_base=("buy_base", "sum"),
        taker_sell_base=("sell_base", "sum"), taker_buy_quote=("buy_quote", "sum"),
        first_agg_id=("aggregate_trade_id", "first"), last_agg_id=("aggregate_trade_id", "last"),
    ).reset_index()


def ingest_archive(path: Path, root: Path = ROOT, chunksize: int = 250_000) -> dict:
    """Valida IDs/tempo/valores e escreve normalizado e minutos incrementalmente."""
    day_text = path.stem.rsplit("-", 3)[-3:]
    expected_day = date.fromisoformat("-".join(day_text))
    normalized = root / "data/phase_3/normalized/aggTrades" / expected_day.isoformat()
    normalized.mkdir(parents=True, exist_ok=True)
    partials, rows, duplicate_ids, agg_gaps, trade_gaps, part = [], 0, 0, 0, 0, 0
    previous_agg = previous_last_trade = None
    for frame in read_aggtrade_chunks(path, chunksize):
        if frame.empty:
            continue
        if (frame.price <= 0).any() or (frame.quantity <= 0).any():
            raise AggTradeQualityError("Preço/quantidade não positivos")
        if (frame.first_trade_id > frame.last_trade_id).any():
            raise AggTradeQualityError("Intervalo de trade IDs invertido")
        if (frame.event_time.dt.date != expected_day).any():
            raise AggTradeQualityError("Timestamp fora do dia declarado")
        ids = frame.aggregate_trade_id.to_numpy()
        diffs = np.diff(ids)
        duplicate_ids += int((diffs == 0).sum())
        agg_gaps += int((diffs > 1).sum())
        if (diffs < 0).any():
            raise AggTradeQualityError("aggregate_trade_id não monotônico")
        first_ids, last_ids = frame.first_trade_id.to_numpy(), frame.last_trade_id.to_numpy()
        trade_gaps += int((first_ids[1:] > last_ids[:-1] + 1).sum())
        if previous_agg is not None:
            duplicate_ids += int(ids[0] == previous_agg)
            agg_gaps += int(ids[0] > previous_agg + 1)
            trade_gaps += int(first_ids[0] > previous_last_trade + 1)
        previous_agg, previous_last_trade = int(ids[-1]), int(last_ids[-1])
        if duplicate_ids:
            raise AggTradeQualityError("aggregate_trade_id duplicado")
        output = normalized / f"part-{part:05d}.parquet"
        frame.to_parquet(output, compression="zstd", index=False)
        partials.append(_partial_minutes(frame))
        rows += len(frame)
        part += 1
    if not rows:
        raise AggTradeQualityError("Arquivo sem AggTrades")
    p = pd.concat(partials, ignore_index=True).sort_values(["minute", "first_agg_id"])
    minutes = p.groupby("minute", sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        base_volume=("base_volume", "sum"), quote_volume=("quote_volume", "sum"),
        aggtrade_count=("aggtrade_count", "sum"), underlying_trade_count=("underlying_trade_count", "sum"),
        taker_buy_base=("taker_buy_base", "sum"), taker_sell_base=("taker_sell_base", "sum"),
        taker_buy_quote=("taker_buy_quote", "sum"), first_agg_id=("first_agg_id", "first"),
        last_agg_id=("last_agg_id", "last"),
    ).reset_index().rename(columns={"minute": "open_time"})
    minute_path = root / "data/phase_3/minutes" / f"{expected_day.isoformat()}.parquet"
    minute_path.parent.mkdir(parents=True, exist_ok=True)
    minutes.to_parquet(minute_path, compression="zstd", index=False)
    return {"date": expected_day.isoformat(), "source": str(path.relative_to(root)), "source_sha256": digest(path),
            "rows": rows, "parquet_parts": part, "minutes": len(minutes), "duplicate_agg_ids": duplicate_ids,
            "aggregate_id_gap_events": agg_gaps, "underlying_trade_gap_events": trade_gaps,
            "minute_gap_events": int(minutes.open_time.diff().gt(pd.Timedelta(minutes=1)).sum()),
            "first_agg_id": int(minutes.first_agg_id.iloc[0]), "last_agg_id": int(minutes.last_agg_id.iloc[-1]),
            "minute_file": str(minute_path.relative_to(root)), "minute_sha256": digest(minute_path)}


def ingest_pilot(root: Path = ROOT) -> dict:
    download = json.loads((root / "data/phase_3/manifests/download.json").read_text(encoding="utf-8"))
    days = [ingest_archive(root / item["file"], root) for item in download["files"]]
    cross_day_gaps = sum(int(current["first_agg_id"] != previous["last_agg_id"] + 1)
                         for previous, current in zip(days, days[1:]))
    manifest = {"source_manifest": "data/phase_3/manifests/download.json", "days": days,
                "rows": sum(d["rows"] for d in days), "minutes": sum(d["minutes"] for d in days),
                "cross_day_aggregate_id_gap_events": cross_day_gaps,
                "quality_status": "validado; gaps contabilizados, sem imputação"}
    save_json(root / "data/phase_3/manifests/ingestion.json", manifest)
    return manifest


def load_minutes(root: Path = ROOT) -> pd.DataFrame:
    paths = sorted((root / "data/phase_3/minutes").glob("*.parquet"))
    if not paths:
        raise FileNotFoundError("Execute a ingestão de AggTrades")
    d = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True).sort_values("open_time").reset_index(drop=True)
    if d.open_time.duplicated().any():
        raise AggTradeQualityError("Minutos duplicados entre partições")
    return d


def reconstructed_candles(minutes: pd.DataFrame) -> pd.DataFrame:
    d = minutes.copy()
    return pd.DataFrame({
        "open_time": d.open_time, "open": d.open, "high": d.high, "low": d.low, "close": d.close,
        "volume": d.base_volume, "close_time": d.open_time + pd.Timedelta(minutes=1) - pd.Timedelta(microseconds=1),
        "quote_volume": d.quote_volume, "trades": d.underlying_trade_count.astype("int64"),
        "taker_base": d.taker_buy_base, "taker_quote": d.taker_buy_quote,
    })


def _micro_segment(d: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=d.index)
    total = d.base_volume.replace(0, np.nan)
    delta = d.taker_buy_base - d.taker_sell_base
    x["flow_imbalance"] = delta / total
    x["buy_share"] = d.taker_buy_base / total
    x["volume_delta"] = delta
    x["mean_aggtrade_size"] = d.base_volume / d.aggtrade_count
    x["avg_trades_per_aggtrade"] = d.underlying_trade_count / d.aggtrade_count
    x["quote_per_aggtrade"] = d.quote_volume / d.aggtrade_count
    x["aggtrades_per_second"] = d.aggtrade_count / 60
    for n in (5, 20, 60):
        x[f"cum_delta_{n}"] = delta.rolling(n).sum() / d.base_volume.rolling(n).sum().replace(0, np.nan)
        x[f"aggtrade_intensity_{n}"] = d.aggtrade_count / d.aggtrade_count.rolling(n).mean().replace(0, np.nan)
    x["underlying_trade_intensity_20"] = d.underlying_trade_count / d.underlying_trade_count.rolling(20).mean().replace(0, np.nan)
    x["size_shock_20"] = x.mean_aggtrade_size / x.mean_aggtrade_size.rolling(20).mean().replace(0, np.nan)
    x["activity_shock_20"] = d.quote_volume / d.quote_volume.rolling(20).mean().replace(0, np.nan)
    x["flow_persistence_5"] = np.sign(delta).rolling(5).mean()
    x["flow_persistence_20"] = np.sign(delta).rolling(20).mean()
    for n in (5, 20):
        ret = d.close / d.close.shift(n) - 1
        flow = delta.rolling(n).sum()
        x[f"price_flow_divergence_{n}"] = ret.abs().where(np.sign(ret) != np.sign(flow), 0.0).where(ret.notna())
    return x[list(MICRO_SPECS)].replace([np.inf, -np.inf], np.nan)


def make_micro_features(minutes: pd.DataFrame) -> pd.DataFrame:
    if minutes.empty or minutes.open_time.duplicated().any() or not minutes.open_time.is_monotonic_increasing:
        raise ValueError("Minutos devem ser únicos, ordenados e não vazios")
    required = ["base_volume", "quote_volume", "aggtrade_count", "underlying_trade_count",
                "taker_buy_base", "taker_sell_base", "close"]
    if minutes[required].isna().any().any():
        raise ValueError("Minuto de microestrutura incompleto")
    segments = minutes.open_time.diff().ne(pd.Timedelta(minutes=1)).cumsum()
    features = pd.concat([_micro_segment(group) for _, group in minutes.groupby(segments)], axis=0).sort_index()
    features.insert(0, "decision_time", minutes.open_time + pd.Timedelta(minutes=1))
    features.insert(1, "available_at", minutes.open_time + pd.Timedelta(minutes=1))
    return features
