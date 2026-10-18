import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def candles():
    rng = np.random.default_rng(7)
    n = 800
    o = 40000 + np.cumsum(rng.normal(0, 20, n))
    c = o + rng.normal(0, 10, n)
    c[::17] = o[::17]
    times = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    return pd.DataFrame({"open_time": times, "open": o, "high": np.maximum(o, c) + 5, "low": np.minimum(o, c) - 5,
                         "close": c, "volume": 2., "close_time": times + pd.Timedelta(minutes=1) - pd.Timedelta(milliseconds=1),
                         "quote_volume": 2 * c, "trades": 10, "taker_base": 1., "taker_quote": c, "ignore": 0})
