# H — Regimes de mercado

Tendência: momentum de20 minutos acima/abaixo de2*vol20*sqrt(20); caso contrário lateral. Volatilidade baixa/alta: quartis25/75 estimados só no treino. Expansão/contração: vol20/vol60 >1.25/<0.75. Todas as entradas são contemporâneas à previsão.

| Horizonte | Regime | N | Accuracy | Log loss |
|---|---|---|---|---|
| 1 | trend:lateral | 126357 | 50.6501% | 0.810154 |
| 1 | trend:baixa | 3034 | 50.9558% | 0.806415 |
| 1 | trend:alta | 3078 | 50.5523% | 0.793777 |
| 1 | volatility:normal | 61965 | 51.3532% | 0.746467 |
| 1 | volatility:alta | 15337 | 51.9658% | 0.705617 |
| 1 | volatility:baixa | 55167 | 49.5060% | 0.909631 |
| 1 | change:expansão | 18563 | 51.0262% | 0.798933 |
| 1 | change:estável | 87836 | 50.7947% | 0.799925 |
| 1 | change:contração | 26070 | 49.9194% | 0.850237 |
| 5 | trend:lateral | 126353 | 51.6015% | 0.717213 |
| 5 | trend:baixa | 3034 | 53.8563% | 0.719869 |
| 5 | trend:alta | 3078 | 53.0864% | 0.720204 |
| 5 | volatility:normal | 61965 | 52.0907% | 0.699460 |
| 5 | volatility:alta | 15337 | 51.6855% | 0.698655 |
| 5 | volatility:baixa | 55163 | 51.2354% | 0.742628 |
| 5 | change:expansão | 18563 | 52.4969% | 0.716489 |
| 5 | change:estável | 87832 | 51.8570% | 0.711855 |
| 5 | change:contração | 26070 | 50.5409% | 0.736445 |
