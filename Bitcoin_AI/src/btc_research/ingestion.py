"""Ingestão estrita e incremental. Originais são somente leitura."""
from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .audit import PATTERN
from .common import ROOT, config, digest, save_json

LOG = logging.getLogger(__name__)
COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
           "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]
CATEGORIES = {"open": "PREÇO", "high": "PREÇO", "low": "PREÇO", "close": "PREÇO",
              "volume": "VOLUME", "quote_volume": "VOLUME", "trades": "VOLUME",
              "taker_base": "VOLUME", "taker_quote": "VOLUME", "open_time": "TEMPO", "close_time": "TEMPO"}
SCHEMA_VERSION = "1.0"


class DataQualityError(ValueError):
    pass


def read_zip(path: Path) -> tuple[pd.DataFrame, dict]:
    match = PATTERN.fullmatch(path.name)
    if not match:
        raise DataQualityError(f"Arquivo incompatível ou desconhecido: {path.name}")
    month = match[1]
    sha = digest(path)
    checksum = path.with_name(path.name + ".CHECKSUM")
    checksum_status = "ausente; proveniência externa não autenticada"
    if checksum.exists():
        if checksum.read_text().split()[0].lower() != sha:
            raise DataQualityError(f"Checksum inválido: {path.name}")
        checksum_status = "sha256_conferido"
    try:
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:
                raise DataQualityError(f"CRC inválido: {path.name}")
            members = [m for m in z.namelist() if not m.endswith("/")]
            if members != [path.stem + ".csv"]:
                raise DataQualityError(f"Membros inesperados no ZIP: {members}")
            if z.getinfo(members[0]).file_size > 200_000_000:
                raise DataQualityError("CSV excede limite de 200 MB por arquivo")
            with z.open(members[0]) as f:
                df = pd.read_csv(f, header=None)
    except (zipfile.BadZipFile, pd.errors.ParserError) as e:
        raise DataQualityError(f"ZIP/CSV inválido: {path.name}: {e}") from e
    if len(df.columns) != 12 or df.empty:
        raise DataQualityError(f"Esperado esquema kline 12 colunas: {path.name}")
    df.columns = COLUMNS
    try:
        df = df.apply(pd.to_numeric, errors="raise")
    except (ValueError, TypeError) as e:
        raise DataQualityError("Schema incompatível: klines numéricas sem cabeçalho") from e
    if not np.isfinite(df.to_numpy(dtype=float)).all():
        raise DataQualityError("Dados ausentes ou não finitos")
    unit = "us" if month >= "2025-01" else "ms"
    for col in ["open_time", "close_time"]:
        values = df[col]
        if ((values % 1) != 0).any():
            raise DataQualityError("Timestamp fracionário")
        magnitude_ok = values.between(10**15, 10**16 - 1) if unit == "us" else values.between(10**12, 10**13 - 1)
        if not magnitude_ok.all():
            raise DataQualityError(f"Unidade temporal incompatível com {month}: esperado {unit}")
        df[col] = pd.to_datetime(values.astype("int64"), unit=unit, utc=True)
    if not (df.open_time.dt.strftime("%Y-%m") == month).all():
        raise DataQualityError("Datas fora do mês informado no arquivo")
    if not (df.open_time == df.open_time.dt.floor("min")).all():
        raise DataQualityError("Abertura desalinhada do intervalo 1m")
    expected_duration = pd.Timedelta(minutes=1) - pd.Timedelta(1, unit=unit)
    if not ((df.close_time - df.open_time) == expected_duration).all():
        raise DataQualityError("Fechamento incompatível com candle 1m completo")
    if (df.close_time >= pd.Timestamp.now(tz="UTC")).any():
        raise DataQualityError("Candle futuro ou ainda não encerrado")
    stats = validate_values(df)
    stats.update(file=path.name, sha256=sha, unit=unit, checksum=checksum_status,
                 unordered=not df.open_time.is_monotonic_increasing)
    df = df.drop(columns="ignore")
    df["source_file"] = path.name
    df["source_sha256"] = sha
    return df, stats


def validate_values(df: pd.DataFrame) -> dict:
    prices = df[["open", "high", "low", "close"]]
    if (prices <= 0).any().any() or not np.isfinite(prices).all().all():
        raise DataQualityError("Preço inválido")
    if ((df.high < prices.max(axis=1)) | (df.low > prices.min(axis=1))).any():
        raise DataQualityError("Relações OHLC inconsistentes")
    volumes = df[["volume", "quote_volume", "taker_base", "taker_quote", "trades"]]
    if (volumes < 0).any().any() or not np.isfinite(volumes).all().all():
        raise DataQualityError("Volume/negociações inválidos")
    if ((df.trades % 1 != 0) | (df.taker_base > df.volume + 1e-8) | (df.taker_quote > df.quote_volume + 1e-6)).any():
        raise DataQualityError("Volume agressor/trades inconsistente")
    if ((df.quote_volume < df.volume * df.low - 0.01) | (df.quote_volume > df.volume * df.high + 0.01)).any():
        raise DataQualityError("Volume cotado incompatível com faixa OHLC")
    return {"invalid_rows": 0}


def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    duplicates = df.duplicated("open_time", keep=False)
    compare = [c for c in COLUMNS if c in df and c != "ignore"]
    if duplicates.any() and (df.loc[duplicates].groupby("open_time")[compare].nunique() > 1).any().any():
        raise DataQualityError("Candles duplicados com valores conflitantes")
    count = int(df.duplicated("open_time").sum())
    return df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True), count


def ingest(root: Path = ROOT) -> dict:
    c = config(root)
    paths = sorted((root / c["raw"]).glob("*.zip"))
    if not paths:
        raise DataQualityError("Nenhum ZIP encontrado")
    report = {"status": "running", "schema_version": SCHEMA_VERSION, "months": [], "files": [], "errors": []}
    previous_path = root / "reports/B_quality.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    cache = {m["month"]: m for m in previous.get("months", [])} if previous.get("schema_version") == SCHEMA_VERSION else {}
    grouped = {}
    for p in paths:
        match = PATTERN.fullmatch(p.name)
        if not match:
            report["errors"].append(f"Arquivo não reconhecido, revisão manual: {p.name}")
        else:
            grouped.setdefault(match[1], []).append(p)
    prior_end = None
    for month, sources in sorted(grouped.items()):
        LOG.info("Validando %s", month)
        out = root / "data/processed" / f"{month}.parquet"
        signatures = {p.name: {"sha256": digest(p), "checksum": digest(p.with_name(p.name + '.CHECKSUM')) if p.with_name(p.name + '.CHECKSUM').exists() else None} for p in sources}
        old = cache.get(month, {})
        try:
            if old.get("sources") == signatures and out.exists() and old.get("output_sha256") == digest(out):
                stat = dict(old)
                stat["cache_hit"] = True
            else:
                frames = []
                details = []
                for p in sources:
                    frame, detail = read_zip(p)
                    frames.append(frame)
                    details.append(detail)
                df, duplicates = deduplicate(pd.concat(frames, ignore_index=True))
                gaps = df.open_time.diff().dropna() / pd.Timedelta(minutes=1) - 1
                start = pd.Timestamp(month, tz="UTC")
                stop = start + pd.offsets.MonthBegin(1)
                expected = int((stop - start) / pd.Timedelta(minutes=1))
                out.parent.mkdir(parents=True, exist_ok=True)
                temporary = out.with_suffix(".tmp")
                df.to_parquet(temporary, index=False, compression="zstd")
                temporary.replace(out)
                stat = {"month": month, "rows": len(df), "start": str(df.open_time.min()), "end": str(df.open_time.max()),
                        "missing_minutes": expected - len(df), "internal_gap_events": int((gaps > 0).sum()),
                        "duplicate_rows_removed": duplicates, "sources": signatures, "details": details,
                        "output_sha256": digest(out), "cache_hit": False}
            start = pd.Timestamp(stat["start"])
            stat["boundary_missing_minutes"] = max(0, int((start - prior_end) / pd.Timedelta(minutes=1)) - 1) if prior_end is not None else 0
            prior_end = pd.Timestamp(stat["end"])
            report["months"].append(stat)
            report["files"].extend(stat["details"])
        except (ValueError, OSError) as e:
            report["errors"].append(f"{month}: {e}")
    report.update(status="invalid" if report["errors"] else "validated",
                  candles=sum(m["rows"] for m in report["months"]),
                  missing_minutes_within_months=sum(m["missing_minutes"] for m in report["months"]),
                  boundary_missing_minutes=sum(m["boundary_missing_minutes"] for m in report["months"]),
                  duplicate_rows_removed=sum(m["duplicate_rows_removed"] for m in report["months"]),
                  decisions=["Duplicatas idênticas removidas só no derivado; conflitos impedem treinamento.",
                             "Lacunas preservadas; indicadores reiniciam e targets que cruzam lacunas são descartados.",
                             "Sem checksum externo não é possível autenticar proveniência; SHA local detecta alterações posteriores."])
    save_json(previous_path, report)
    if report["errors"]:
        raise DataQualityError("Falhas críticas; consulte reports/B_quality.json")
    return report


def require_quality(root: Path) -> dict:
    report = json.loads((root / "reports/B_quality.json").read_text(encoding="utf-8"))
    if report["status"] != "validated":
        raise DataQualityError("Qualidade não aprovada")
    for month in report["months"]:
        path = root / "data/processed" / (month["month"] + ".parquet")
        if not path.exists() or digest(path) != month["output_sha256"]:
            raise DataQualityError("Parquet alterado; executar ingestão novamente")
        for name, sig in month["sources"].items():
            source = root / config(root)["raw"] / name
            if not source.exists() or digest(source) != sig["sha256"]:
                raise DataQualityError("RAW alterado; executar ingestão novamente")
    return report
