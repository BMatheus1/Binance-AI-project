# Fase 2 — plano experimental congelado

Data: 17/10/2026. Este documento foi criado antes da execução dos experimentos da Fase 2.

## Limite temporal

Julho–setembro/2026 foi consumido na Fase 1 e não será carregado, consultado ou usado para escolher features, modelos, regimes ou limiares. A Fase 2 termina em `2026-07-01` exclusivo. Seus resultados são validação interna walk-forward, não um novo teste final independente.

## Orçamento

- Três folds walk-forward com treino expansivo, calibração de três meses e validação posterior de três meses.
- Amostra determinística de até 3.000 observações por mês, formada depois do cálculo causal das features. O teto foi reduzido após uma corrida operacional interrompida por custo excessivo de convergência; períodos, hipóteses e candidatos não mudaram.
- Semente 42 e quatro threads.
- Pequeno conjunto predefinido de modelos e hiperparâmetros; sem busca indiscriminada.
- Métrica primária: log loss multiclasse. Secundárias: Brier, accuracy, F1 macro, calibração e métricas econômicas hipotéticas.

## Cinco famílias priorizadas

1. **Auditoria e erros.** Verificar dados, timestamps, causalidade, rótulos, separações, calibração, confiança, horários, dias, sequências e regimes. Rejeição: qualquer vazamento ou desalinhamento interrompe os experimentos.
2. **Relevância das 37 features.** Ablar grupos e fazer permutação temporal na validação. Rejeição: importância instável, negativa ou redundante não sustenta promoção.
3. **Features contextuais.** Avaliar interações objetivas de candle, rejeição, compressão, aceleração, volume e padrões simples descritos no estudo dos livros. São traduções matemáticas do projeto, não regras atribuídas literalmente aos autores. Rejeição: ausência de melhora estável em log loss nos folds.
4. **Modelos e regularização.** Reavaliar frequência, logística, Random Forest, XGBoost e CatBoost; comparar uma variante XGBoost moderadamente regularizada. Rejeição: ganho localizado, calibração pior ou correção de multiplicidade não favorável.
5. **Seleção econômica.** Avaliar abstenção, payouts fixos e Spot long-only com custos separados. Rejeição: IC diário inclui zero, baixa estabilidade, poucos sinais ou sensibilidade excessiva a custos/limiar.

Resultados negativos serão mantidos. Nenhuma operação real será executada e nenhuma política será promovida automaticamente.
