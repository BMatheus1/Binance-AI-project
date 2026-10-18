# 04 — Experimentos A–D

A, B, C e D usam o mesmo intervalo, divisões, regressão logística, calibração e métricas. D escolhe atributos apenas no treino por regressão L1; a validação não participa da escolha.

## Horizonte 1m

| Variante | Features | Accuracy | Log loss | Brier | ECE |
|---|---:|---:|---:|---:|---:|
| A_original_xgboost_37 | 37 | 51.3112% | 0.768756 | 0.517803 | 0.008259 |
| B_aggtrades | 20 | 50.7310% | 0.771100 | 0.518791 | 0.014042 |
| C_combined | 57 | 51.1720% | 0.767460 | 0.517078 | 0.010390 |
| D_selected_train_only | 24 | 51.3112% | 0.767187 | 0.517064 | 0.012374 |
| frequência do treino | 0 | 49.1761% | 0.794935 | 0.521346 | 0.019345 |

Menor log loss observado: **D_selected_train_only**. Isso seleciona uma versão para observação prospectiva; não promove negociação.

## Horizonte 5m

| Variante | Features | Accuracy | Log loss | Brier | ECE |
|---|---:|---:|---:|---:|---:|
| A_original_xgboost_37 | 37 | 50.6388% | 0.707734 | 0.503022 | 0.024775 |
| B_aggtrades | 20 | 49.9419% | 0.708786 | 0.502609 | 0.019251 |
| C_combined | 57 | 50.7782% | 0.708599 | 0.504045 | 0.031464 |
| D_selected_train_only | 24 | 50.5923% | 0.708511 | 0.503900 | 0.029632 |
| frequência do treino | 0 | 48.4321% | 0.708184 | 0.502120 | 0.015767 |

Menor log loss observado: **A_original_xgboost_37**. Isso seleciona uma versão para observação prospectiva; não promove negociação.
