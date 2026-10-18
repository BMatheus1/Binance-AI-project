import numpy as np
import pandas as pd


def fit_regimes(train: pd.DataFrame) -> dict:
    return {"vol_low": float(train.realized_vol_20.quantile(.25)), "vol_high": float(train.realized_vol_20.quantile(.75)),
            "trend_rule": "momentum20 >/< 2*vol20*sqrt(20); caso contrário lateral",
            "vol_change_rule": "vol20/vol60 >1.25 expansão; <0.75 contração"}


def regimes(frame: pd.DataFrame, params: dict) -> pd.DataFrame:
    threshold = 2 * frame.realized_vol_20 * np.sqrt(20)
    return pd.DataFrame({"trend": np.select([frame.momentum_20 > threshold, frame.momentum_20 < -threshold], ["alta", "baixa"], default="lateral"),
                         "volatility": np.select([frame.realized_vol_20 < params["vol_low"], frame.realized_vol_20 > params["vol_high"]], ["baixa", "alta"], default="normal"),
                         "change": np.select([frame.vol_ratio > 1.25, frame.vol_ratio < .75], ["expansão", "contração"], default="estável")}, index=frame.index)
