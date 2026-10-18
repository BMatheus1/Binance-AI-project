# 03 — Relevância das features

As 37 variáveis foram permutadas individualmente por deslocamento circular dentro de cada validação. Delta positivo indica piora ao destruir a variável; o método mede associação preditiva, não causalidade. As ablações de categorias usam a mesma logística e calibração.

## Horizonte 1m

| Feature | Delta médio de log loss | Sinal estável nos folds |
|---|---:|---:|
| atr_rel_14 | +0.012269 | 3/3 |
| realized_vol_20 | +0.005035 | 3/3 |
| range_rel | +0.004639 | 3/3 |
| weekday_sin | +0.002329 | 3/3 |
| breakout_20 | +0.001399 | 2/3 |
| ema_distance_20 | +0.000967 | 2/3 |
| vol_ratio | +0.000494 | 3/3 |
| momentum_20 | +0.000414 | 3/3 |
| macd_rel | +0.000383 | 3/3 |
| volume_change | +0.000296 | 3/3 |
| sma_slope_20 | +0.000282 | 3/3 |
| higher_high | +0.000240 | 3/3 |
| hour_cos | +0.000224 | 2/3 |
| close_position | +0.000215 | 3/3 |
| sma_distance_20 | +0.000211 | 2/3 |
| signed_volume | +0.000198 | 3/3 |
| weekday_cos | +0.000185 | 3/3 |
| closed_15m_return | +0.000163 | 3/3 |
| higher_low | +0.000155 | 2/3 |
| momentum_5 | +0.000144 | 2/3 |
| taker_buy_ratio | +0.000115 | 2/3 |
| return_1 | +0.000106 | 3/3 |
| support_distance_20 | +0.000100 | 2/3 |
| log_return | +0.000092 | 2/3 |
| upper_wick | +0.000085 | 3/3 |
| rsi_14 | +0.000079 | 2/3 |
| body_fraction | +0.000075 | 2/3 |
| closed_60m_return | +0.000050 | 3/3 |
| closed_30m_return | +0.000007 | 1/3 |
| hour_sin | -0.000001 | 1/3 |
| closed_5m_return | -0.000017 | 1/3 |
| lower_wick | -0.000052 | 2/3 |
| bollinger_z | -0.000057 | 0/3 |
| direction_balance_5 | -0.000063 | 0/3 |
| body_rel | -0.000082 | 2/3 |
| trade_intensity | -0.000187 | 1/3 |
| volume_rel_20 | -0.000263 | 1/3 |

A importância foi instável para várias features; nenhuma foi apagada do catálogo original.

## Horizonte 5m

| Feature | Delta médio de log loss | Sinal estável nos folds |
|---|---:|---:|
| ema_distance_20 | +0.001742 | 3/3 |
| realized_vol_20 | +0.000666 | 3/3 |
| support_distance_20 | +0.000463 | 2/3 |
| atr_rel_14 | +0.000370 | 2/3 |
| rsi_14 | +0.000356 | 3/3 |
| breakout_20 | +0.000335 | 2/3 |
| macd_rel | +0.000267 | 3/3 |
| lower_wick | +0.000146 | 2/3 |
| momentum_5 | +0.000141 | 1/3 |
| closed_15m_return | +0.000111 | 3/3 |
| upper_wick | +0.000086 | 3/3 |
| higher_low | +0.000074 | 1/3 |
| weekday_sin | +0.000071 | 3/3 |
| range_rel | +0.000069 | 3/3 |
| bollinger_z | +0.000061 | 2/3 |
| closed_60m_return | +0.000046 | 2/3 |
| sma_slope_20 | +0.000041 | 2/3 |
| volume_rel_20 | +0.000040 | 3/3 |
| trade_intensity | +0.000029 | 2/3 |
| taker_buy_ratio | +0.000028 | 2/3 |
| sma_distance_20 | +0.000024 | 2/3 |
| body_rel | +0.000021 | 2/3 |
| hour_cos | +0.000018 | 3/3 |
| higher_high | +0.000016 | 2/3 |
| weekday_cos | +0.000016 | 3/3 |
| direction_balance_5 | +0.000003 | 2/3 |
| momentum_20 | -0.000001 | 2/3 |
| close_position | -0.000005 | 2/3 |
| log_return | -0.000012 | 1/3 |
| closed_30m_return | -0.000013 | 2/3 |
| closed_5m_return | -0.000023 | 1/3 |
| vol_ratio | -0.000027 | 2/3 |
| return_1 | -0.000033 | 1/3 |
| volume_change | -0.000043 | 1/3 |
| signed_volume | -0.000063 | 1/3 |
| hour_sin | -0.000109 | 0/3 |
| body_fraction | -0.000112 | 2/3 |

A importância foi instável para várias features; nenhuma foi apagada do catálogo original.
