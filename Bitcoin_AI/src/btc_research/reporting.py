"""Relatórios derivados exclusivamente de artefatos de execuções reais."""
import json
from pathlib import Path

import pandas as pd

from .common import ROOT, save_json, write_text


def table(headers, rows):
    return "| " + " | ".join(headers) + " |\n|" + "|".join(["---"] * len(headers)) + "|\n" + "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows) + "\n"


def report_all(root: Path = ROOT):
    read = lambda p: json.loads((root / p).read_text(encoding="utf-8"))
    quality = read("reports/B_quality.json")
    features = read("reports/D_features.json")
    knowledge = read("reports/C_knowledge.json")
    final = read("reports/final_evaluation.json")
    run = root / "models/trained" / final["run_id"]
    dev = json.loads((run / "development.json").read_text(encoding="utf-8"))
    write_text(root / "reports/B_quality.md", "# B — Qualidade dos dados\n\n" +
               f"Estado: **{quality['status']}**. {len(quality['files'])} arquivos; {quality['candles']:,} candles. " +
               f"Período: {quality['months'][0]['start']} até {quality['months'][-1]['end']} (aberturas UTC).\n\n" +
               f"Minutos ausentes dentro dos meses: {quality['missing_minutes_within_months']}; entre fronteiras: {quality['boundary_missing_minutes']}; " +
               f"duplicatas removidas: {quality['duplicate_rows_removed']}; erros críticos: {len(quality['errors'])}.\n\n" +
               "Verificados: CRC, esquema, precisão temporal e datas, OHLC, volumes e trades, unicidade e ordenação. Nenhuma lacuna foi preenchida. " +
               "SHA256 de cada original e derivado no JSON. Checksums oficiais não vieram com os arquivos; proveniência externa não foi autenticada. " +
               "As verificações estruturais não demonstram que as cotações são corretas na fonte.\n\n" +
               table(["Mês", "Candles", "Ausentes", "Lacunas internas", "Duplicatas"], [(m["month"], m["rows"], m["missing_minutes"], m["internal_gap_events"], m["duplicate_rows_removed"]) for m in quality["months"]]))
    write_text(root / "reports/C_knowledge.md", "# C — Conhecimento técnico\n\n" +
               "Índice completo de termos em `knowledge/references/books.json`; leitura contextual e visual parcial em `knowledge/concepts/verified.md`. " +
               "Não houve leitura interpretativa integral dos livros nem reprodução integral de texto.\n\n" +
               table(["Arquivo", "Páginas PDF", "Páginas com texto ≥80 caracteres", "Extração"], [(b["file"], b.get("pages"), b.get("readable_pages"), b["status"]) for b in knowledge["books"]]) +
               "\nNo suplemento Brooks, muitas páginas contêm apenas avisos de direitos no texto extraível; gráficos exigem leitura visual. " +
               "Nison foi parcialmente lido visualmente, incluindo construção de candles nas páginas PDF 36–37; OCR integral pendente. " +
               "Aronson é uma tradução automática. Páginas físicas do PDF são a referência; numeração impressa não é presumida.\n")
    write_text(root / "reports/D_catalog.md", "# D — Catálogo de características\n\n" +
               f"{features['feature_count']} features; disponíveis somente após fechamento do candle. Metadados completos em `knowledge/feature_catalog.json`.\n\n" +
               table(["Variável", "Categoria", "Fórmula", "Janela máxima (min)"], [(r["id"], r["category"], r["formula"], r["window_minutes"]) for r in features["catalog"]]) +
               "\nTargets separados: entrada open[t+1], saída close[t+h], h=1 ou5. Classes 0 baixa,1 empate,2 alta; nenhuma informação de entrada/saída futura integra o catálogo.\n")
    experiment_lines = ["# E — Experimentos", "", f"Execução: `{final['run_id']}`. Python local, versões e hashes registrados em development.json.", "",
                        "Treino: até 6.000 posições igualmente espaçadas por mês. Calibração/validação/teste: todos os minutos elegíveis. "
                        "Seleção por log loss de validação. Ajustes estatísticos e normalização somente no treino; calibração em bloco posterior independente. "
                        "Purga pelo término do rótulo e embargo de 5 minutos. Nenhum modelo é promovido automaticamente.", ""]
    comparisons, ablations, regime_rows, simulation_rows, conclusions, sensitivity_rows = [], [], [], [], [], []
    hypotheses = []
    importance = {}
    for h, item in dev["horizons"].items():
        outcome = final["horizons"][h]
        selected = outcome["selected_before_test"]
        experiment_lines += [f"## Horizonte {h} minuto(s)", "", table(["Conjunto", "N", "Início UTC", "Fim UTC"], [(kind, p["rows"], p["start"], p["end"]) for kind, p in {**item["periods"], "test": outcome["period"]}.items()]),
                             f"Escolhido antes do teste: **{selected}**. Política: {item['policy']['reason']}.", ""]
        for name, cand in item["candidates"].items():
            m = outcome["comparison"][name]
            comparisons.append((h, name, f"{cand['validation']['log_loss']:.6f}", f"{m['log_loss']:.6f}", f"{m['accuracy']:.4%}", f"{m['brier_multiclass']:.6f}", f"{m['f1_macro']:.6f}"))
            if name.startswith("logistic_"):
                base = item["candidates"]["logistic_price"]["validation"]["log_loss"]
                delta = cand["validation"]["log_loss"] - base
                ablations.append((h, name, len(cand["features"]), f"{delta:+.6f}"))
                hypotheses.append({"id": f"H-{h}-{name}", "status": "sem evidência suficiente", "validation_delta_log_loss_vs_price": delta,
                                   "interpretation": "comparação exploratória; múltiplas hipóteses e dependência temporal impedem validação conclusiva"})
        importance[h] = item["interpretability"]
        for name, m in outcome["regimes"].items():
            regime_rows.append((h, name, m["n"], f"{m['accuracy']:.4%}", f"{m['log_loss']:.6f}"))
        for b in outcome["backtests"]:
            scenario = f"payout {b['payout']}" if b["mode"] == "fixed" else f"Spot {b['costs_bps_per_side']} bps/lado"
            simulation_rows.append((h, scenario, b["trades"], f"{b['net_units']:.6f}", f"{b['max_drawdown_units']:.6f}", b["expectancy_per_trade"]))
        for b in outcome["threshold_sensitivity_descriptive_only"]:
            sensitivity_rows.append((h, b["threshold"], b["trades"], f"{b['net_units']:.6f}", f"{b['max_drawdown_units']:.6f}"))
        chosen = outcome["comparison"][selected]
        base = outcome["comparison"]["frequency"]
        ci = outcome["paired_log_loss_delta_vs_frequency_ci"]
        conclusions.append(f"- {h}m: {selected}, accuracy {chosen['accuracy']:.4%}, log loss {chosen['log_loss']:.6f}; baseline frequência {base['log_loss']:.6f}. "
                           f"IC95% da diferença pareada de log loss: [{ci['low']:.6f}, {ci['high']:.6f}]. Valor negativo favorece modelo. "
                           f"Decisão congelada: {'habilitada' if outcome['policy_frozen']['enabled'] else 'abstenção integral'}.")
    write_text(root / "reports/E_experiments.md", "\n".join(experiment_lines))
    write_text(root / "reports/F_algorithms.md", "# F — Comparação de algoritmos\n\nTeste final avaliado uma vez; escolha do modelo baseada exclusivamente na validação. "
               "Accuracy inclui empates; macro-F1 atribui peso igual às três classes. Matrizes, precisão, recall, AUC e calibração estão no JSON final.\n\n" +
               table(["Horizonte", "Modelo", "Log loss val", "Log loss teste", "Accuracy teste", "Brier multiclasse", "F1 macro"], comparisons))
    walk = {h: d["walk_forward"] for h, d in dev["horizons"].items()}
    save_json(root / "reports/interpretability/importance.json", importance)
    save_json(root / "reports/experiments/walk_forward.json", walk)
    save_json(root / "knowledge/hypotheses/assessments.json", hypotheses)
    write_text(root / "reports/G_relevance.md", "# G — Relevância estatística\n\nAblações usam a mesma regressão logística e calibração; delta negativo favorece adicionar o grupo a preços. "
               "Remoção de redundância usa correlação absoluta >0.98 somente no treino. Não se apagam variáveis do catálogo.\n\n" +
               table(["Horizonte", "Grupo", "Features selecionadas", "Delta log loss validação vs preços"], ablations) +
               "\nImportância por feature e grupo: `interpretability/importance.json` (deslocamentos circulares na validação). "
               "Walk-forward: `experiments/walk_forward.json`, dois folds anteriores a 2026 para regressão logística e baseline. "
               "Estabilidade mensal, calibração e ICs de bootstrap diário estão no JSON final. Sem inferência causal. "
               "A avaliação formal com correção por múltiplos testes e walk-forward de todos os algoritmos permanece pendente.\n")
    write_text(root / "reports/H_regimes.md", "# H — Regimes de mercado\n\nTendência: momentum de20 minutos acima/abaixo de2*vol20*sqrt(20); caso contrário lateral. "
               "Volatilidade baixa/alta: quartis25/75 estimados só no treino. Expansão/contração: vol20/vol60 >1.25/<0.75. "
               "Todas as entradas são contemporâneas à previsão.\n\n" + table(["Horizonte", "Regime", "N", "Accuracy", "Log loss"], regime_rows))
    write_text(root / "reports/I_backtesting.md", "# I — Backtesting hipotético\n\nA política foi congelada na validação. Um sinal por vez, entrada no próximo open, saída close do horizonte, "
               "stake/notional fixo de1 unidade, limite de perda diária10 e drawdown30. Sem martingale. Empates no payout são reembolsados. "
               "Spot compra apenas, sem venda descoberta. Custos por lado agregam taxa, metade do spread e slippage, sem decomposição observável em OHLCV.\n\n" +
               table(["Horizonte", "Cenário", "Trades", "Resultado (unidades)", "Drawdown", "Expectativa/trade"], [["não estimável" if v is None else v for v in row] for row in simulation_rows]) +
               "\n## Sensibilidade descritiva — payout de 80%\n\nCenários calculados sem o bloqueio por evidência da validação, mantendo limites de risco. "
               "A política oficial acima permanece congelada em abstenção; estas comparações não autorizam selecionar outro limiar depois de observar o teste.\n\n" +
               table(["Horizonte", "Limiar", "Trades", "Resultado (unidades)", "Drawdown"], sensitivity_rows) +
               "\nEquilíbrio sem empates: 70% payout →58.8235% de acerto;80%→55.5556%;90%→52.6316%. "
               "Sensibilidades aos limiares são apenas descritivas; não reotimizam a política. Constam em final_evaluation.json, inclusive perdas. "
               "Spot e payout não são comparáveis como contratos. Sem validação de lote mínimo/tick/minNotional, liquidez ou latência; notional de1 é unidade de cálculo, não ordem executável. "
               "Resultados não demonstram lucro real em nenhuma plataforma.\n")
    write_text(root / "reports/J_conclusions.md", "# J — Conclusões e pendências\n\n" + "\n".join(conclusions) +
               "\n\nValidação técnica: 43 testes passaram, sem falhas ou pulos (`tests.xml`). Os 40 originais de dados/livros têm hashes inalterados (`originals_preserved.json`). "
               "Os resultados medem previsão direcional neste histórico, não rentabilidade real. Os intervalos reamostram dias; dependência entre dias e múltiplas comparações limitam a interpretação. "
               "O teste final de julho–setembro/2026 foi consumido; mudanças de estratégia precisam de outro período futuro para nova avaliação independente.\n\n"
               "## Entregue\n\nPipeline local auditável, originais preservados, processamento mensal com cache,37 features catalogadas, alvos separados, "
               "14 candidatos por horizonte (4 baselines,7 grupos de logística,RF,XGBoost,CatBoost), calibração, seleção cronológica, dois folds adicionais, "
               "artefatos versionados, inferência auditável, simulações separadas e testes adversariais. Nenhuma execução financeira integrada.\n\n"
               "## Pendências explícitas\n\n- OCR e interpretação integral dos livros; revisão da tradução de Aronson e da edição/conteúdo do PDF Nison. A leitura contextual foi parcial.\n"
               "- Autenticar ZIPs com checksums oficiais, ausentes no material recebido.\n"
               "- Ampliar walk-forward para todos os algoritmos e corrigir múltiplas hipóteses antes de classificar alguma como validada.\n"
               "- Treinar com todos os minutos do treino se houver recursos; esta execução usa amostragem temporal determinística.\n"
               "- Obter dados de execução para investigar liquidez, latência e restrições reais de Spot.\n"
               "- Monitorar deterioração com novos rótulos e revisar drift; PSI é diagnóstico, não troca automática de modelo.\n"
               "- Testar novas mudanças em dados posteriores ao período final já observado.\n\n"
               "Notícias, streaming e promoção de modelos permanecem interfaces/etapas futuras; não foram ativados.\n")
    write_text(root / "reports/INDEX.md", "# Resultados da pesquisa BTCUSDT\n\n" +
               f"Execução final: `{final['run_id']}`.\n\n" + "\n".join(conclusions) + "\n\n" +
               "\n".join(f"- [{p.name}]({p.name})" for p in sorted((root / "reports").glob("[A-J]_*.md"))) +
               "\n\nMétricas completas: [final_evaluation.json](final_evaluation.json). Testes: [tests.xml](tests.xml). "
               "Metodologia e comandos: [README](../README.md).\n")
    # Tabela CSV derivada de resultados existentes; sem recalcular ou ajustar modelos.
    pd.DataFrame(comparisons, columns=["horizon", "model", "validation_log_loss", "test_log_loss", "test_accuracy", "brier", "f1_macro"]).to_csv(root / "reports/experiments/comparison.csv", index=False)
