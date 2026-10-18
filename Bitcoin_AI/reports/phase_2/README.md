# Fase 2 — resultado executivo

A Fase 2 foi concluída como pesquisa exploratória walk-forward. Nenhuma operação real foi executada e a política oficial permanece em **abstenção integral**.

## Resultado principal

| Horizonte | Melhor validação interna | Accuracy média | Log loss médio | Frequência histórica | Diferença |
|---|---|---:|---:|---:|---:|
| 1m | xgboost_contextual_regularized | 50.4241% | 0.765946 | 0.788588 | -0.022642 |
| 5m | xgboost_original | 51.2390% | 0.704938 | 0.707560 | -0.002623 |

A variante contextual do XGBoost mudou o log loss em -0.000056 no horizonte de 1m e +0.000785 em 5m contra o XGBoost original, nas mesmas validações. O ganho de 1m é pequeno e não foi testado em período independente; em 5m a variante piorou nos três folds. Portanto, os conhecimentos dos livros geraram hipóteses úteis, mas **não demonstraram uma vantagem nova e sustentável**.

Todos os modelos aprendidos superaram a frequência histórica em log loss após Holm, mas isso não se converteu em expectativa econômica demonstrada. Nenhum limiar de payout 80% reuniu ao mesmo tempo 200 operações e limite inferior positivo do IC diário. Os melhores resultados aparentes tiveram intervalos que incluíram zero.

O diagnóstico dos alvos encontrou retorno absoluto mediano de aproximadamente 2,62 bps em 1m e 6,02 bps em 5m. Apenas 8,36% e 30,88%, respectivamente, superaram 10 bps. Isso reforça que acertar direção pode significar prever movimentos pequenos demais para sustentar custos. Os alvos originais foram preservados; qualquer limiar econômico deverá ser um experimento futuro separado.

## Comparação com a Fase 1

A Fase 1 continua sendo a única avaliação no teste final consumido: 50,6549%/0,809687 em 1m e 51,6876%/0,717344 em 5m para accuracy/log loss. Os números acima usam períodos e amostragem diferentes, então não provam melhora sobre esse teste. A comparação causal disponível dentro da Fase 2 é entre candidatos nos mesmos folds: ganho contextual praticamente nulo em 1m e piora em 5m.

## O que mudou

- 17 features contextuais experimentais, mantidas fora do catálogo congelado da Fase 1.
- Três folds walk-forward para todos os algoritmos avaliados.
- Erros por tendência, volatilidade, movimentos abruptos, horário UTC, dia da semana, sequências e confiança.
- Permutação temporal das 37 features, ablação por categoria e correção de Holm.
- Calibração medida antes/depois e cenários econômicos separados para payout e Spot.

## Limite da evidência

Foram usadas até 3.000 observações por mês para controlar CPU e memória. Eventos raros têm estimativas frágeis. Julho–setembro/2026 permaneceu fora da Fase 2; não existe outro teste futuro independente nos arquivos recebidos. Resultados completos e negativos estão em [results.json](runs/20261017T223631458343Z-phase2/results.json).

## Verificação

47 testes automatizados passaram em 17/10/2026. A auditoria confirmou novamente os hashes inalterados dos 36 ZIPs e quatro PDFs. O artefato estruturado registra zero observações do período proibido.
