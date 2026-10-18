# D — Catálogo de características

37 features; disponíveis somente após fechamento do candle. Metadados completos em `knowledge/feature_catalog.json`.

| Variável | Categoria | Fórmula | Janela máxima (min) |
|---|---|---|---|
| return_1 | PREÇO | close/close.shift(1)-1 | 2 |
| log_return | PREÇO | log(close/close.shift(1)) | 2 |
| range_rel | VOLATILIDADE | (high-low)/close | 1 |
| body_rel | PRICE ACTION | abs(close-open)/open | 1 |
| body_fraction | PRICE ACTION | (close-open)/(high-low); zero se range=0 | 1 |
| lower_wick | PRICE ACTION | (min(open,close)-low)/(high-low); zero se range=0 | 1 |
| upper_wick | PRICE ACTION | (high-max(open,close))/(high-low); zero se range=0 | 1 |
| close_position | PRICE ACTION | (close-low)/(high-low); 0.5 se range=0 | 1 |
| direction_balance_5 | PRICE ACTION | mean(sign(close-open),5) | 5 |
| higher_high | TENDÊNCIA | 1(high>high.shift(1)) | 2 |
| higher_low | TENDÊNCIA | 1(low>low.shift(1)) | 2 |
| momentum_5 | TENDÊNCIA | close/close.shift(5)-1 | 6 |
| momentum_20 | TENDÊNCIA | close/close.shift(20)-1 | 21 |
| sma_distance_20 | TENDÊNCIA | close/mean(close,20)-1 | 20 |
| sma_slope_20 | TENDÊNCIA | mean(close,20)/mean(close,20).shift(5)-1 | 25 |
| ema_distance_20 | TENDÊNCIA | close/EMA finita normalizada span20 sobre60-1 | 60 |
| macd_rel | TENDÊNCIA | (EMAfinita12-EMAfinita26)/close; ambas janela60 | 60 |
| rsi_14 | TENDÊNCIA | RSI Cutler: mean(gain,14)/(mean(gain,14)+mean(loss,14)); neutro0.5 | 15 |
| atr_rel_14 | VOLATILIDADE | mean(max(high-low,abs(high-prevclose),abs(low-prevclose)),14)/close | 15 |
| realized_vol_20 | VOLATILIDADE | std(log_return,20,ddof1) | 21 |
| vol_ratio | VOLATILIDADE | std(log_return,20)/std(log_return,60); 1 se ambas zero | 61 |
| bollinger_z | VOLATILIDADE | (close-mean(close,20))/std(close,20); zero se std=0 | 20 |
| volume_rel_20 | VOLUME | volume/mean(volume,20); 1 se média=0 | 20 |
| volume_change | VOLUME | log1p(volume)-log1p(volume.shift(1)) | 2 |
| trade_intensity | VOLUME | trades/mean(trades,20); 1 se média=0 | 20 |
| taker_buy_ratio | VOLUME | taker_base/volume; 0.5 se volume=0 | 1 |
| signed_volume | VOLUME | sign(close-open)*volume/mean(volume,20) | 20 |
| breakout_20 | PRICE ACTION | close/max(high.shift(1),20)-1 | 21 |
| support_distance_20 | PRICE ACTION | close/min(low.shift(1),20)-1 | 21 |
| hour_sin | TEMPO | sin(2*pi*minute_of_day_at_decision/1440) | 1 |
| hour_cos | TEMPO | cos(2*pi*minute_of_day_at_decision/1440) | 1 |
| weekday_sin | TEMPO | sin(2*pi*day_of_week_at_decision/7) | 1 |
| weekday_cos | TEMPO | cos(2*pi*day_of_week_at_decision/7) | 1 |
| closed_5m_return | TENDÊNCIA | close/open-1 do último candle UTC completo de 5m | 10 |
| closed_15m_return | TENDÊNCIA | close/open-1 do último candle UTC completo de 15m | 30 |
| closed_30m_return | TENDÊNCIA | close/open-1 do último candle UTC completo de 30m | 60 |
| closed_60m_return | TENDÊNCIA | close/open-1 do último candle UTC completo de 60m | 120 |

Targets separados: entrada open[t+1], saída close[t+h], h=1 ou5. Classes 0 baixa,1 empate,2 alta; nenhuma informação de entrada/saída futura integra o catálogo.
