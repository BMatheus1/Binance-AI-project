from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import SPECS
from .validation import assert_inputs


def align_probabilities(estimator, x) -> np.ndarray:
    output = np.full((len(x), 3), 1e-9)
    output[:, np.asarray(estimator.classes_, dtype=int)] = estimator.predict_proba(x)
    return output / output.sum(axis=1, keepdims=True)


def create_model(name: str, seed: int, threads: int):
    if name == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=400, random_state=seed))
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=80, max_depth=8, min_samples_leaf=100, max_features=.7, n_jobs=threads, random_state=seed)
    if name == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(n_estimators=100, max_depth=3, learning_rate=.05, subsample=.8, colsample_bytree=.8,
                             min_child_weight=30, reg_lambda=10, objective="multi:softprob", num_class=3, tree_method="hist", n_jobs=threads, random_state=seed)
    if name == "catboost":
        from catboost import CatBoostClassifier
        return CatBoostClassifier(iterations=100, depth=4, learning_rate=.05, l2_leaf_reg=10, loss_function="MultiClass",
                                 random_seed=seed, thread_count=threads, verbose=False, allow_writing_files=False)
    raise ValueError(f"Modelo desconhecido: {name}")


class Baseline:
    def __init__(self, name="frequency"):
        self.name = name
        self.classes_ = np.arange(3)

    def fit(self, x, y):
        y = np.asarray(y, dtype=int)
        self.frequency = (np.bincount(y, minlength=3) + 1) / (len(y) + 3)
        self.rules = {}
        sign = np.sign(x["return_1"].to_numpy())
        for s in [-1, 0, 1]:
            subset = y[sign == s]
            self.rules[s] = (np.bincount(subset, minlength=3) + 1) / (len(subset) + 3)
        return self

    def predict_proba(self, x):
        if self.name == "frequency":
            return np.tile(self.frequency, (len(x), 1))
        if self.name == "constant":
            p = np.full(3, .01)
            p[self.frequency.argmax()] = .98
            return np.tile(p, (len(x), 1))
        sign = np.sign(x["return_1"].to_numpy())
        # Direção prescrita; intensidade estimada apenas no treino.
        strength = max(self.frequency[0], self.frequency[2]) + .05
        tie = self.frequency[1]
        p = np.tile(self.frequency, (len(x), 1))
        for s in [-1, 1]:
            direction = 2 if (s > 0) == (self.name == "momentum") else 0
            p[sign == s, direction] = strength
            p[sign == s, 2 - direction] = 1 - tie - strength
        return p


@dataclass
class ModelBundle:
    estimator: object
    columns: list[str]
    horizon: int
    calibrator: object | None = None

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        assert_inputs(frame, self.columns)
        p = align_probabilities(self.estimator, frame[self.columns])
        if self.calibrator is not None:
            p = align_probabilities(self.calibrator, np.log(np.clip(p, 1e-9, 1)))
        return p

    def calibrate(self, frame: pd.DataFrame, y) -> None:
        if len(np.unique(y)) < 2:
            raise ValueError("Calibração exige ao menos duas classes")
        p = self.predict_proba(frame)
        self.calibrator = LogisticRegression(C=1, max_iter=300, random_state=42)
        self.calibrator.fit(np.log(np.clip(p, 1e-9, 1)), y)


def select_columns(train: pd.DataFrame, columns: list[str]) -> tuple[list[str], dict]:
    useful = [c for c in columns if train[c].std() > 1e-12]
    corr = train[useful].corr().abs()
    chosen, rejected = [], {}
    for col in useful:
        redundant = [other for other in chosen if corr.loc[col, other] > .98]
        if redundant:
            rejected[col] = {"reason": "correlação >0.98 no treino", "with": redundant}
        else:
            chosen.append(col)
    return chosen, rejected


def feature_groups() -> dict:
    price = [k for k, v in SPECS.items() if v[0] == "PREÇO"]
    groups = {"price": price}
    for label, category in [("action", "PRICE ACTION"), ("trend", "TENDÊNCIA"), ("volatility", "VOLATILIDADE"), ("volume", "VOLUME")]:
        groups["price_" + label] = price + [k for k, v in SPECS.items() if v[0] == category]
    groups["price_trend_volume"] = list(dict.fromkeys(groups["price_trend"] + groups["price_volume"]))
    groups["all_selected"] = list(SPECS)
    return groups
