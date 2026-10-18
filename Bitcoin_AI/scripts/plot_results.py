"""Gera figura científica estática a partir da avaliação já gravada."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "reports/final_evaluation.json").read_text(encoding="utf-8"))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained")
labels, scores, errors, model_loss, base_loss = [], [], [], [], []
for h, d in data["horizons"].items():
    m = d["comparison"][d["selected_before_test"]]
    ci = d["accuracy_daily_ci"]
    labels.append(h + " minuto" + ("s" if h != "1" else ""))
    scores.append(m["accuracy"] * 100)
    errors.append([(m["accuracy"] - ci["low"]) * 100, (ci["high"] - m["accuracy"]) * 100])
    model_loss.append(m["log_loss"])
    base_loss.append(d["comparison"]["frequency"]["log_loss"])
x = np.arange(len(labels))
axes[0].errorbar(x, scores, yerr=np.array(errors).T, fmt="o", color="#11776b", capsize=7, markersize=8)
axes[0].set(xticks=x, xticklabels=labels, ylabel="Acerto direcional (%)", title="Accuracy e IC de 95% por blocos diários", ylim=(49, 53), xlim=(-.5, 1.5))
axes[0].grid(axis="y", alpha=.2)
axes[1].bar(x - .18, base_loss, .36, color="#b8c3cf", label="Frequência histórica")
axes[1].bar(x + .18, model_loss, .36, color="#11776b", label="XGBoost calibrado")
axes[1].set(xticks=x, xticklabels=labels, ylabel="Log loss (menor é melhor)", title="Qualidade das probabilidades", ylim=(0, 1))
axes[1].legend(frameon=False, loc="upper right")
for i in range(2):
    axes[1].text(i - .18, base_loss[i] + .012, f"{base_loss[i]:.3f}", ha="center", fontsize=9)
    axes[1].text(i + .18, model_loss[i] + .012, f"{model_loss[i]:.3f}", ha="center", fontsize=9)
fig.suptitle("BTC/USDT | Teste independente: julho–setembro de 2026\nPolítica congelada: abstenção integral; resultado preditivo não demonstra lucro", fontsize=13)
out = ROOT / "reports/experiments"
fig.savefig(out / "evaluation.png", dpi=160)
fig.savefig(out / "evaluation.svg")
plt.close(fig)
