# 7. Endpoints e permissões

REST aceito: somente `https://demo-api.binance.com/api`. Quatro destinos indevidos de teste, incluindo hosts de produção, HTTP sem TLS e host externo, foram rejeitados localmente. Não existe fallback.

Na conta Demo consultada: `canTrade=true`, `canDeposit=true`, `canWithdraw=true`, tipo `SPOT`; saldos virtuais livres observados: 5.000 USDT e 5.000 USDC. `BTCUSDT` estava `TRADING`, sem ordens abertas, `minNotional=5`, `stepSize=0.00001` e quantidade máxima de mercado informada pela bolsa. Esses valores são temporais e devem ser consultados novamente antes de cada diagnóstico.
