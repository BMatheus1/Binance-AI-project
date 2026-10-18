# 06 — Comparação de modelos

Todos os experimentos respeitaram o plano congelado e três folds walk-forward. As novas features são traduções matemáticas próprias, calculadas com candles encerrados.

## Horizonte 1m

Selecionado na validação interna: **xgboost_contextual_regularized**.

| Modelo | Log loss médio | Brier médio | Accuracy média | Holm p vs frequência |
|---|---:|---:|---:|---:|
| frequency | 0.788588 | 0.522483 | 48.6906% | 1.0000 |
| logistic_original | 0.767322 | 0.520258 | 49.5055% | 0.0015 |
| logistic_contextual | 0.766916 | 0.519976 | 49.6907% | 0.0015 |
| random_forest_original | 0.766334 | 0.519419 | 50.5019% | 0.0015 |
| xgboost_original | 0.766002 | 0.519511 | 50.1574% | 0.0015 |
| xgboost_contextual_regularized | 0.765946 | 0.519468 | 50.4241% | 0.0015 |
| catboost_original | 0.766713 | 0.519839 | 50.0315% | 0.0015 |

A seleção é exploratória; não existe teste independente posterior disponível.

## Horizonte 5m

Selecionado na validação interna: **xgboost_original**.

| Modelo | Log loss médio | Brier médio | Accuracy média | Holm p vs frequência |
|---|---:|---:|---:|---:|
| frequency | 0.707560 | 0.502286 | 49.6722% | 1.0000 |
| logistic_original | 0.706768 | 0.502267 | 50.6797% | 0.0093 |
| logistic_contextual | 0.706446 | 0.502365 | 50.7242% | 0.0029 |
| random_forest_original | 0.705645 | 0.501784 | 51.5539% | 0.0015 |
| xgboost_original | 0.704938 | 0.501909 | 51.2390% | 0.0015 |
| xgboost_contextual_regularized | 0.705722 | 0.501982 | 51.2242% | 0.0015 |
| catboost_original | 0.706688 | 0.502029 | 50.8908% | 0.0127 |

A seleção é exploratória; não existe teste independente posterior disponível.
