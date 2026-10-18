import numpy as np


def decisions(probabilities, threshold: float, payout: float = .8, enabled=True):
    """-1=abstenção, 0=baixa, 2=alta; empates reembolsados."""
    p = np.asarray(probabilities)
    if not 0.5 <= threshold <= 1 or not 0 < payout <= 1:
        raise ValueError("Limiar/payout inválido")
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all() or (p < 0).any() or not np.allclose(p.sum(axis=1), 1):
        raise ValueError("Probabilidades inválidas")
    direction = np.where(p[:, 2] > p[:, 0], 2, 0)
    win = p[np.arange(len(p)), direction]
    lose = p[np.arange(len(p)), 2 - direction]
    return np.where(enabled & (win >= threshold) & (win * payout > lose), direction, -1)
