# 04 — Comparação dos horizontes

| Horizonte | Selecionado para shadow | Accuracy | Log loss | Brier | ECE | Mediana |retorno| |
|---:|---|---:|---:|---:|---:|---:|
| 1m | xgboost | 50.6180% | 0.774881 | 0.522223 | 0.003585 | 0.023665% |
| 5m | xgboost | 51.7793% | 0.702095 | 0.500329 | 0.002652 | 0.053897% |
| 15m | xgboost | 52.4751% | 0.694784 | 0.498628 | 0.001455 | 0.095029% |
| 30m | catboost | 52.3299% | 0.694014 | 0.498673 | 0.005271 | 0.135218% |

Todos os modelos usaram as mesmas linhas dentro de cada horizonte. A seleção é apenas para shadow; não habilita sinais financeiros.