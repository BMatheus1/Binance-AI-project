# Resultados da pesquisa BTCUSDT

Execução final: `20261017T174250393322Z-research`.

Estudo bibliográfico posterior: [dossiês dos quatro autores, síntese e cobertura](../knowledge/study/README.md). Esta etapa ampliou a análise dos livros, sem modificar a execução final ou reutilizar seu teste.

Fase 2: [resultado executivo, nove relatórios e artefatos reproduzíveis](phase_2/README.md). A Fase 2 usa somente validações anteriores a julho/2026; não reabre o teste final consumido.

Fase 3: [piloto oficial de AggTrades, microestrutura, coletor público, ledger prospectivo e paper trading](phase_3/README.md). O piloto usa 01–14/10/2026, posterior ao teste final já consumido, e permanece exploratório.

Fase 4: [auditoria estatística, modelos congelados, horizontes 1/5/15/30m e observação prospectiva](phase_4/README.md). Julho–setembro/2026 permaneceu vedado; a execução histórica usa somente desenvolvimento anterior a julho e mantém abstenção integral.

Fase 5: [experimento GPU completo e comparação auditável do Kronos-mini](phase_5/README.md). O Kronos não superou os modelos congelados e não foi promovido.

Fase 6: [serviços multiactivos, notícias oficiais, políticas A/B, risco e simulação](phase_6/README.md). A engenharia inicial está pronta em observação; ainda não existem resultados econômicos prospectivos.

Fase 6.1: [Qwen3 local, políticas A/B/C/D, supervisor persistente e auditoria de
licenças](phase_6_1/README.md). A engenharia passou em 123 testes; a validação
econômica prospectiva permanece pendente e nenhuma ordem foi enviada.

- 1m: xgboost, accuracy 50.6549%, log loss 0.809687; baseline frequência 0.861573. IC95% da diferença pareada de log loss: [-0.072525, -0.033281]. Valor negativo favorece modelo. Decisão congelada: abstenção integral.
- 5m: xgboost, accuracy 51.6876%, log loss 0.717344; baseline frequência 0.729788. IC95% da diferença pareada de log loss: [-0.024622, -0.003589]. Valor negativo favorece modelo. Decisão congelada: abstenção integral.

- [A_audit.md](A_audit.md)
- [B_quality.md](B_quality.md)
- [C_knowledge.md](C_knowledge.md)
- [D_catalog.md](D_catalog.md)
- [E_experiments.md](E_experiments.md)
- [F_algorithms.md](F_algorithms.md)
- [G_relevance.md](G_relevance.md)
- [H_regimes.md](H_regimes.md)
- [I_backtesting.md](I_backtesting.md)
- [J_conclusions.md](J_conclusions.md)

Métricas completas: [final_evaluation.json](final_evaluation.json). Testes: [tests.xml](tests.xml). Metodologia e comandos: [README](../README.md).
