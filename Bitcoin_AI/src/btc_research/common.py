from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_json(path: Path, value) -> None:
    def convert(x):
        if isinstance(x, (np.integer, np.floating)):
            return x.item()
        if isinstance(x, (Path, pd.Timestamp)):
            return str(x)
        if isinstance(x, np.ndarray):
            return x.tolist()
        raise TypeError(type(x).__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=convert, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def config(root: Path = ROOT) -> dict:
    c = json.loads((root / "configs/research.json").read_text(encoding="utf-8"))
    if c["entry_convention"] != "next_open" or c["tie_tolerance"] < 0:
        raise ValueError("Convenção de entrada/tolerância não suportada")
    return c


def versions() -> dict:
    result = {}
    for name in ["numpy", "pandas", "pyarrow", "scikit-learn", "xgboost", "catboost", "pypdf", "pytest", "joblib",
                 "torch", "transformers", "huggingface_hub", "safetensors", "pydantic"]:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
