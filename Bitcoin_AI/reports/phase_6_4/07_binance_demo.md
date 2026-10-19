# Integração Binance Demo

REST `https://demo-api.binance.com/api`, WebSocket API `wss://demo-ws-api.binance.com/ws-api/v3` e mercado `wss://demo-stream.binance.com/stream`, conforme a [documentação oficial Demo](https://developers.binance.info/en/docs/products/spot/demo-mode/general-info). O cliente rejeita hosts de produção e não possui fallback. Market orders usam identificadores persistidos e `Decimal`.
