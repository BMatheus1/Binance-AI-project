# 03 — Catálogo causal de microestrutura

Todas as variáveis ficam disponíveis no fim do minuto (`open_time + 1min`) e reiniciam após lacunas.

| Feature | Fórmula |
|---|---|
| `flow_imbalance` | (taker_buy_base-taker_sell_base)/base_volume |
| `buy_share` | taker_buy_base/base_volume |
| `volume_delta` | taker_buy_base-taker_sell_base |
| `mean_aggtrade_size` | base_volume/aggtrade_count |
| `avg_trades_per_aggtrade` | underlying_trade_count/aggtrade_count |
| `quote_per_aggtrade` | quote_volume/aggtrade_count |
| `aggtrades_per_second` | aggtrade_count/60 |
| `cum_delta_5` | soma(volume_delta,5)/soma(base_volume,5) |
| `cum_delta_20` | soma(volume_delta,20)/soma(base_volume,20) |
| `cum_delta_60` | soma(volume_delta,60)/soma(base_volume,60) |
| `aggtrade_intensity_5` | aggtrade_count/média(aggtrade_count,5) |
| `aggtrade_intensity_20` | aggtrade_count/média(aggtrade_count,20) |
| `aggtrade_intensity_60` | aggtrade_count/média(aggtrade_count,60) |
| `underlying_trade_intensity_20` | underlying_trade_count/média(underlying_trade_count,20) |
| `size_shock_20` | mean_aggtrade_size/média(mean_aggtrade_size,20) |
| `activity_shock_20` | quote_volume/média(quote_volume,20) |
| `flow_persistence_5` | média(sinal(volume_delta),5) |
| `flow_persistence_20` | média(sinal(volume_delta),20) |
| `price_flow_divergence_5` | abs(retorno5) se sinais de retorno e delta5 divergem; senão 0 |
| `price_flow_divergence_20` | abs(retorno20) se sinais de retorno e delta20 divergem; senão 0 |