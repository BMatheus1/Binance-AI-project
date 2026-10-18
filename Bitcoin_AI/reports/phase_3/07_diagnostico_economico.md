# 07 — Diagnóstico econômico

Todos os resultados são hipotéticos. O histórico de AggTrades não contém bid/ask; por isso, o retrospectivo Spot usa cenários explícitos de custo por lado. Spread real é reservado ao coletor prospectivo.

## Horizonte 1m — D_selected_train_only

| Mercado | Parâmetro | Trades | Expectativa | IC diário |
|---|---:|---:|---:|---|
| fixed | limiar=0.52; payout=0.7 | 80 | 0.009999999999999976 | indisponível (<10 dias) |
| fixed | limiar=0.52; payout=0.8 | 678 | 0.013864306784660765 | indisponível (<10 dias) |
| fixed | limiar=0.52; payout=0.9 | 2087 | 0.011403929084810749 | indisponível (<10 dias) |
| spot | limiar=0.52; custo/lado=5bps | 365 | -0.0009237257819788517 | indisponível (<10 dias) |
| spot | limiar=0.52; custo/lado=10bps | 365 | -0.0019223032667432414 | indisponível (<10 dias) |
| spot | limiar=0.52; custo/lado=20bps | 365 | -0.003916468483323714 | indisponível (<10 dias) |
| fixed | limiar=0.55; payout=0.7 | 63 | -0.01904761904761904 | indisponível (<10 dias) |
| fixed | limiar=0.55; payout=0.8 | 463 | 0.025917926565874726 | indisponível (<10 dias) |
| fixed | limiar=0.55; payout=0.9 | 491 | 0.05519348268839104 | indisponível (<10 dias) |
| spot | limiar=0.55; custo/lado=5bps | 243 | -0.0008923476972526578 | indisponível (<10 dias) |
| spot | limiar=0.55; custo/lado=10bps | 243 | -0.0018909565444362457 | indisponível (<10 dias) |
| spot | limiar=0.55; custo/lado=20bps | 243 | -0.0038851843919556588 | indisponível (<10 dias) |
| fixed | limiar=0.58; payout=0.7 | 27 | -0.05555555555555559 | indisponível (<10 dias) |
| fixed | limiar=0.58; payout=0.8 | 36 | -0.04999999999999998 | indisponível (<10 dias) |
| fixed | limiar=0.58; payout=0.9 | 36 | 0.00277777777777778 | indisponível (<10 dias) |
| spot | limiar=0.58; custo/lado=5bps | 14 | -0.001119387649960327 | indisponível (<10 dias) |
| spot | limiar=0.58; custo/lado=10bps | 14 | -0.0021177695705410426 | indisponível (<10 dias) |
| spot | limiar=0.58; custo/lado=20bps | 14 | -0.00411154424427571 | indisponível (<10 dias) |
| fixed | limiar=0.6; payout=0.7 | 7 | 0.21428571428571425 | indisponível (<10 dias) |
| fixed | limiar=0.6; payout=0.8 | 7 | 0.2857142857142857 | indisponível (<10 dias) |
| fixed | limiar=0.6; payout=0.9 | 7 | 0.35714285714285715 | indisponível (<10 dias) |
| spot | limiar=0.6; custo/lado=5bps | 0 | n/a | indisponível (<10 dias) |
| spot | limiar=0.6; custo/lado=10bps | 0 | n/a | indisponível (<10 dias) |
| spot | limiar=0.6; custo/lado=20bps | 0 | n/a | indisponível (<10 dias) |

A amostra de validação tem três dias; não permite intervalo diário confiável nem conclusão econômica robusta.

## Horizonte 5m — A_original_xgboost_37

| Mercado | Parâmetro | Trades | Expectativa | IC diário |
|---|---:|---:|---:|---|
| fixed | limiar=0.52; payout=0.7 | 62 | 0.04193548387096773 | indisponível (<10 dias) |
| fixed | limiar=0.52; payout=0.8 | 282 | -0.026241134751773056 | indisponível (<10 dias) |
| fixed | limiar=0.52; payout=0.9 | 665 | -0.03127819548872179 | indisponível (<10 dias) |
| spot | limiar=0.52; custo/lado=5bps | 196 | -0.0009927652972005208 | indisponível (<10 dias) |
| spot | limiar=0.52; custo/lado=10bps | 196 | -0.0019912737769177073 | indisponível (<10 dias) |
| spot | limiar=0.52; custo/lado=20bps | 196 | -0.003985301190005729 | indisponível (<10 dias) |
| fixed | limiar=0.55; payout=0.7 | 62 | 0.04193548387096773 | indisponível (<10 dias) |
| fixed | limiar=0.55; payout=0.8 | 282 | -0.026241134751773056 | indisponível (<10 dias) |
| fixed | limiar=0.55; payout=0.9 | 324 | 0.035185185185185194 | indisponível (<10 dias) |
| spot | limiar=0.55; custo/lado=5bps | 196 | -0.0009927652972005208 | indisponível (<10 dias) |
| spot | limiar=0.55; custo/lado=10bps | 196 | -0.0019912737769177073 | indisponível (<10 dias) |
| spot | limiar=0.55; custo/lado=20bps | 196 | -0.003985301190005729 | indisponível (<10 dias) |
| fixed | limiar=0.58; payout=0.7 | 62 | 0.04193548387096773 | indisponível (<10 dias) |
| fixed | limiar=0.58; payout=0.8 | 81 | -0.022222222222222244 | indisponível (<10 dias) |
| fixed | limiar=0.58; payout=0.9 | 81 | 0.03209876543209879 | indisponível (<10 dias) |
| spot | limiar=0.58; custo/lado=5bps | 54 | -0.0009508056282806632 | indisponível (<10 dias) |
| spot | limiar=0.58; custo/lado=10bps | 54 | -0.001949356046718383 | indisponível (<10 dias) |
| spot | limiar=0.58; custo/lado=20bps | 54 | -0.003943467211682423 | indisponível (<10 dias) |
| fixed | limiar=0.6; payout=0.7 | 24 | -0.15000000000000002 | indisponível (<10 dias) |
| fixed | limiar=0.6; payout=0.8 | 24 | -0.09999999999999998 | indisponível (<10 dias) |
| fixed | limiar=0.6; payout=0.9 | 24 | -0.04999999999999998 | indisponível (<10 dias) |
| spot | limiar=0.6; custo/lado=5bps | 13 | -0.0010986642600819062 | indisponível (<10 dias) |
| spot | limiar=0.6; custo/lado=10bps | 13 | -0.0020970668937063076 | indisponível (<10 dias) |
| spot | limiar=0.6; custo/lado=20bps | 13 | -0.004090882931513282 | indisponível (<10 dias) |

A amostra de validação tem três dias; não permite intervalo diário confiável nem conclusão econômica robusta.
