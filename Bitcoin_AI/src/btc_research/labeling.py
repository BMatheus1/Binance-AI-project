from __future__ import annotations

import numpy as np
import pandas as pd


def make_targets(d: pd.DataFrame, horizons=(1, 5), tolerance: float = 0.0) -> pd.DataFrame:
    """0=baixa, 1=empate, 2=alta. Entrada next_open; saída close[t+h]."""
    if tolerance < 0 or d.open_time.duplicated().any() or not d.open_time.is_monotonic_increasing:
        raise ValueError("Configuração ou sequência temporal inválida")
    t = pd.DataFrame({"decision_time": d.open_time + pd.Timedelta(minutes=1), "entry_price": d.open.shift(-1)})
    segment = d.open_time.diff().ne(pd.Timedelta(minutes=1)).cumsum()
    for h in horizons:
        valid = segment.eq(segment.shift(-h)) & d.open_time.shift(-h).eq(d.open_time + pd.Timedelta(minutes=h))
        ret = (d.close.shift(-h) / t.entry_price - 1).where(valid)
        y = pd.Series(np.select([ret < -tolerance, ret > tolerance], [0, 2], default=1), index=d.index, dtype="float64").where(valid)
        t[f"return_{h}m"] = ret
        t[f"target_{h}m"] = y
        t[f"exit_price_{h}m"] = d.close.shift(-h).where(valid)
        t[f"event_end_{h}m"] = (d.open_time.shift(-h) + pd.Timedelta(minutes=1)).where(valid)
    return t
