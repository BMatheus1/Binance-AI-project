# I — Backtesting hipotético

A política foi congelada na validação. Um sinal por vez, entrada no próximo open, saída close do horizonte, stake/notional fixo de1 unidade, limite de perda diária10 e drawdown30. Sem martingale. Empates no payout são reembolsados. Spot compra apenas, sem venda descoberta. Custos por lado agregam taxa, metade do spread e slippage, sem decomposição observável em OHLCV.

| Horizonte | Cenário | Trades | Resultado (unidades) | Drawdown | Expectativa/trade |
|---|---|---|---|---|---|
| 1 | payout 0.7 | 0 | 0.000000 | 0.000000 | não estimável |
| 1 | payout 0.8 | 0 | 0.000000 | 0.000000 | não estimável |
| 1 | payout 0.9 | 0 | 0.000000 | 0.000000 | não estimável |
| 1 | Spot 5 bps/lado | 0 | 0.000000 | 0.000000 | não estimável |
| 1 | Spot 10 bps/lado | 0 | 0.000000 | 0.000000 | não estimável |
| 1 | Spot 20 bps/lado | 0 | 0.000000 | 0.000000 | não estimável |
| 5 | payout 0.7 | 0 | 0.000000 | 0.000000 | não estimável |
| 5 | payout 0.8 | 0 | 0.000000 | 0.000000 | não estimável |
| 5 | payout 0.9 | 0 | 0.000000 | 0.000000 | não estimável |
| 5 | Spot 5 bps/lado | 0 | 0.000000 | 0.000000 | não estimável |
| 5 | Spot 10 bps/lado | 0 | 0.000000 | 0.000000 | não estimável |
| 5 | Spot 20 bps/lado | 0 | 0.000000 | 0.000000 | não estimável |

## Sensibilidade descritiva — payout de 80%

Cenários calculados sem o bloqueio por evidência da validação, mantendo limites de risco. A política oficial acima permanece congelada em abstenção; estas comparações não autorizam selecionar outro limiar depois de observar o teste.

| Horizonte | Limiar | Trades | Resultado (unidades) | Drawdown |
|---|---|---|---|---|
| 1 | 0.55 | 96 | -0.000000 | 12.600000 |
| 1 | 0.58 | 0 | 0.000000 | 0.000000 |
| 1 | 0.6 | 0 | 0.000000 | 0.000000 |
| 1 | 0.65 | 0 | 0.000000 | 0.000000 |
| 5 | 0.55 | 888 | -24.000000 | 30.200000 |
| 5 | 0.58 | 347 | 11.200000 | 16.000000 |
| 5 | 0.6 | 123 | 1.200000 | 10.800000 |
| 5 | 0.65 | 1 | -1.000000 | 1.000000 |

Equilíbrio sem empates: 70% payout →58.8235% de acerto;80%→55.5556%;90%→52.6316%. Sensibilidades aos limiares são apenas descritivas; não reotimizam a política. Constam em final_evaluation.json, inclusive perdas. Spot e payout não são comparáveis como contratos. Sem validação de lote mínimo/tick/minNotional, liquidez ou latência; notional de1 é unidade de cálculo, não ordem executável. Resultados não demonstram lucro real em nenhuma plataforma.
