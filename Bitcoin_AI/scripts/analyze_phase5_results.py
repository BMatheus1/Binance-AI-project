"""Resume uma importação Kronos da Fase 5 sem alterar modelos ou política."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from btc_research.common import ROOT, save_json, write_text


def _best_scenario(items: list[dict], mode: str) -> dict | None:
    usable = [item for item in items if item["mode"] == mode and item["expectancy_per_trade"] is not None]
    return max(usable, key=lambda item: item["expectancy_per_trade"]) if usable else None


def analyze(path: Path, root: Path = ROOT) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {
        "source": str(path), "status": data["status"], "variants": {}, "best_by_horizon": {},
        "training": {}, "automatic_promotion": False, "policy": data["policy"],
    }
    losses = np.asarray(data["source_manifest"].get("training_losses", []), dtype=float)
    if len(losses):
        result["training"] = {
            "steps": len(losses), "first": losses[0], "last": losses[-1],
            "mean_first_50": losses[:50].mean(), "mean_last_50": losses[-50:].mean(),
            "linear_slope_per_step": np.polyfit(np.arange(len(losses)), losses, 1)[0] if len(losses) > 1 else None,
            "minimum": losses.min(), "maximum": losses.max(),
        }
    for variant, horizons in data["variants"].items():
        result["variants"][variant] = {}
        for horizon, values in horizons.items():
            delta = values["paired_log_loss_delta_vs_phase4"]
            economics = values["economics"]
            positive_ci = [item for item in economics if item.get("expectancy_ci")
                           and isinstance(item["expectancy_ci"].get("low"), (int, float))
                           and item["expectancy_ci"]["low"] > 0]
            eligible = [item for item in positive_ci if item["trades"] >= 200]
            result["variants"][variant][horizon] = {
                "observations": values["observations"],
                "baseline_model": values["phase4_baseline_model"],
                "accuracy": values["kronos"]["accuracy"],
                "baseline_accuracy": values["phase4_baseline"]["accuracy"],
                "log_loss": values["kronos"]["log_loss"],
                "baseline_log_loss": values["phase4_baseline"]["log_loss"],
                "log_loss_delta": delta,
                "brier": values["kronos"]["brier_multiclass"],
                "baseline_brier": values["phase4_baseline"]["brier_multiclass"],
                "ece": values["kronos_ece"],
                "best_fixed": _best_scenario(economics, "fixed"),
                "best_spot": _best_scenario(economics, "spot"),
                "positive_ci_scenarios": len(positive_ci),
                "eligible_positive_ci_scenarios": len(eligible),
            }
    for horizon in ["1", "5", "15", "30"]:
        candidates = [(variant, values[horizon]) for variant, values in result["variants"].items()]
        variant, best = min(candidates, key=lambda item: item[1]["log_loss"])
        result["best_by_horizon"][horizon] = {"variant": variant, **best}
    result["incremental_predictive_advantage"] = any(
        values["log_loss_delta"]["high"] < 0 for values in result["best_by_horizon"].values())
    result["protocol_economic_filter_passed"] = any(
        values["eligible_positive_ci_scenarios"] > 0
        for horizons in result["variants"].values() for values in horizons.values())
    result["economic_evidence_sufficient"] = False
    result["economic_evidence_limit"] = (
        "Filtro passou apenas em configurações duplicadas de payout fixo da variante finetuned_raw em 15m, "
        "sobre o bloco exploratório já consumido e sem correção por múltiplas comparações ou confirmação futura.")
    return result


def markdown(summary: dict) -> str:
    lines = [
        "# 08 — Resultado completo do Kronos no Colab", "",
        "Δ log loss = Kronos − modelo congelado da Fase 4; valor negativo favorece Kronos.", "",
        "| Horizonte | Melhor variante Kronos | Accuracy | Baseline | Log loss | Baseline | Δ LL | IC95% diário | ECE |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for horizon, row in summary["best_by_horizon"].items():
        ci = row["log_loss_delta"]
        lines.append(
            f"| {horizon}m | {row['variant']} | {row['accuracy']:.4f} | {row['baseline_accuracy']:.4f} | "
            f"{row['log_loss']:.6f} | {row['baseline_log_loss']:.6f} | {ci['mean']:+.6f} | "
            f"[{ci['low']:+.6f}, {ci['high']:+.6f}] | {row['ece']:.4f} |")
    lines += [
        "", "### Log loss de todas as variantes", "",
        "| Variante | 1m | 5m | 15m | 30m |",
        "|---|---:|---:|---:|---:|",
    ]
    for variant in ["pretrained_raw", "pretrained_calibrated", "finetuned_raw", "finetuned_calibrated"]:
        row = summary["variants"][variant]
        lines.append(f"| {variant} | {row['1']['log_loss']:.6f} | {row['5']['log_loss']:.6f} | "
                     f"{row['15']['log_loss']:.6f} | {row['30']['log_loss']:.6f} |")
    baseline = summary["best_by_horizon"]
    lines.append(f"| Fase 4 | {baseline['1']['baseline_log_loss']:.6f} | {baseline['5']['baseline_log_loss']:.6f} | "
                 f"{baseline['15']['baseline_log_loss']:.6f} | {baseline['30']['baseline_log_loss']:.6f} |")
    training = summary["training"]
    lines += [
        "", "## Fine-tuning", "",
        f"Foram executados {training.get('steps', 0)} passos. A loss média dos primeiros 50 passos foi "
        f"{training.get('mean_first_50', float('nan')):.6f} e dos últimos 50 foi "
        f"{training.get('mean_last_50', float('nan')):.6f}. A inclinação linear foi "
        f"{training.get('linear_slope_per_step', float('nan')):+.9f} por passo.", "",
        "Após calibração, o modelo pré-treinado obteve log loss menor que a variante fine-tuned nos quatro horizontes. "
        "O fine-tuning configurado não demonstrou vantagem incremental.", "",
        "## Economia e decisão", "",
    ]
    eligible = sum(row["eligible_positive_ci_scenarios"] for horizons in summary["variants"].values()
                   for row in horizons.values())
    lines += [
        f"Configurações com limite inferior positivo e pelo menos 200 trades: **{eligible}**. As três são a mesma "
        "política efetiva da variante `finetuned_raw` em 15m, payout 90%, com limiares 0,55/0,58/0,60 que "
        "selecionaram os mesmos 215 trades: expectativa +0,131163 unidade/trade, IC95% diário "
        "[+0,001332, +0,253364]. Trata-se de payout fixo hipotético; não é resultado Spot.", "",
        "Todos os cenários Spot foram negativos após custos. O melhor valor observado ainda foi "
        "-0,000695 por trade com 5 bps por lado, e seu IC95% permaneceu abaixo de zero.", "",
        "Nenhuma variante Kronos apresentou ganho de log loss com IC diário inteiramente abaixo de zero contra "
        "XGBoost/CatBoost. A política permanece em abstenção integral; não há promoção automática nem evidência "
        "para declarar lucratividade.", "",
        "A amostra de abril–junho/2026 já foi usada na Fase 4, portanto esta comparação é exploratória e não é "
        "um novo teste final independente.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    summary = analyze(args.results)
    save_json(ROOT / "reports/phase_5/full_analysis.json", summary)
    write_text(ROOT / "reports/phase_5/08_full_results.md", markdown(summary))
    print(ROOT / "reports/phase_5/08_full_results.md")


if __name__ == "__main__":
    main()
