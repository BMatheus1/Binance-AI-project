# 07 — Calibração probabilística

Cada algoritmo foi ajustado no treino e calibrado em um bloco posterior separado. ECE, Brier e log loss foram medidos somente no bloco de validação seguinte.

## Horizonte 1m

| Modelo | ECE médio | Log loss bruto | Log loss calibrado |
|---|---:|---:|---:|
| frequency | 0.005167 | n/a | 0.788588 |
| logistic_original | 0.009729 | 0.769987 | 0.767322 |
| logistic_contextual | 0.011237 | 0.769058 | 0.766916 |
| random_forest_original | 0.007181 | 0.767055 | 0.766334 |
| xgboost_original | 0.005945 | 0.767010 | 0.766002 |
| xgboost_contextual_regularized | 0.007753 | 0.767116 | 0.765946 |
| catboost_original | 0.008570 | 0.769861 | 0.766713 |

## Horizonte 5m

| Modelo | ECE médio | Log loss bruto | Log loss calibrado |
|---|---:|---:|---:|
| frequency | 0.005561 | n/a | 0.707560 |
| logistic_original | 0.006862 | 0.707953 | 0.706768 |
| logistic_contextual | 0.008813 | 0.707744 | 0.706446 |
| random_forest_original | 0.006302 | 0.705517 | 0.705645 |
| xgboost_original | 0.010110 | 0.704747 | 0.704938 |
| xgboost_contextual_regularized | 0.008697 | 0.705358 | 0.705722 |
| catboost_original | 0.010743 | 0.708337 | 0.706688 |
