"""Simulações independentes: aposta fixa e Spot long-only. Sem ordens reais."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .decision import decisions
from .validation import daily_block_ci


def break_even(payout: float) -> float:
    if not 0 < payout <= 1:
        raise ValueError("Payout líquido deve estar em (0,1]")
    return 1 / (1 + payout)


def simulate(frame: pd.DataFrame, p, h: int, threshold=.6, payout=.8, mode="fixed", costs_bps=10,
             enabled=True, daily_limit=10, drawdown_limit=30) -> tuple[dict, pd.DataFrame]:
    if mode not in {"fixed", "spot"} or costs_bps < 0 or not 0 <= costs_bps < 10000:
        raise ValueError("Modo/custo inválido")
    if frame.decision_time.duplicated().any() or not frame.decision_time.is_monotonic_increasing or len(p) != len(frame):
        raise ValueError("Previsões devem estar alinhadas e ordenadas")
    signals = decisions(p, threshold, payout, enabled)
    if mode == "spot":
        signals = np.where(signals == 2, 2, -1)
    times = pd.DatetimeIndex(frame.decision_time)
    ends = pd.DatetimeIndex(frame[f"event_end_{h}m"])
    y = frame[f"target_{h}m"].to_numpy(dtype=int)
    if (ends <= times).any():
        raise ValueError("Saída deve ser posterior à entrada")
    returns = frame[f"return_{h}m"].to_numpy()
    free_at, equity, peak, day_pnl, active_day = None, 0., 0., 0., None
    records = []
    for i in np.flatnonzero(signals >= 0):
        time = times[i]
        if free_at is not None and time < free_at:
            continue
        day = time.floor("D")
        if day != active_day:
            day_pnl, active_day = 0., day
        if day_pnl <= -daily_limit or peak - equity >= drawdown_limit:
            continue
        if mode == "fixed":
            pnl = 0. if y[i] == 1 else payout if y[i] == signals[i] else -1.
        else:
            # Um USDT de notional fixo por trade; taxa+spread+slippage agregados por lado.
            cost = costs_bps / 10000
            pnl = (1 + returns[i]) * (1 - cost) / (1 + cost) - 1
        records.append({"decision_time": time, "event_end": ends[i], "direction": int(signals[i]), "target": int(y[i]),
                        "pnl": float(pnl), "win": bool(y[i] != 1 and y[i] == signals[i]), "tie": bool(y[i] == 1)})
        equity += pnl
        peak = max(peak, equity)
        day_pnl += pnl
        free_at = ends[i]
    trades = pd.DataFrame(records, columns=["decision_time", "event_end", "direction", "target", "pnl", "win", "tie"])
    pnl = trades.pnl.to_numpy(dtype=float)
    curve = np.r_[0., np.cumsum(pnl)]
    losses = streak = 0
    for loss in pnl < 0:
        streak = streak + 1 if loss else 0
        losses = max(losses, streak)
    result = {"mode": mode, "hypothetical": True, "n_predictions": len(frame), "trades": len(trades),
              "signal_coverage": float((signals >= 0).mean()) if len(signals) else 0.,
              "executed_coverage": len(trades) / len(frame) if len(frame) else 0.,
              "abstention_rate": float((signals < 0).mean()) if len(signals) else 1.,
              "hit_rate_excluding_ties": float(trades.loc[~trades.tie.astype(bool), "win"].mean()) if len(trades) and (~trades.tie.astype(bool)).any() else None,
              "ties": int(trades.tie.sum()) if len(trades) else 0, "tie_rule": "fixed: reembolso; spot: retorno realizado menos custos",
              "expectancy_per_trade": float(pnl.mean()) if len(pnl) else None, "net_units": float(pnl.sum()),
              "max_drawdown_units": float(np.max(np.maximum.accumulate(curve) - curve)), "max_loss_streak": losses,
              "threshold": threshold, "payout": payout if mode == "fixed" else None, "costs_bps_per_side": costs_bps if mode == "spot" else None,
              "break_even_non_ties": break_even(payout) if mode == "fixed" else None,
              "expectancy_ci": daily_block_ci(pnl, trades.decision_time) if len(trades) else None,
              "risk": {"fixed_notional": 1, "non_overlapping": True, "daily_loss_limit": daily_limit, "max_drawdown": drawdown_limit},
              "limitations": "Entrada next_open idealizada; sem livro de ofertas/latência, tick/lot/minNotional e liquidez real não simulados. Custos são cenários, não tarifas observadas."}
    if len(trades):
        result["monthly_pnl"] = trades.groupby(trades.decision_time.dt.strftime("%Y-%m")).pnl.sum().to_dict()
    return result, trades
