# 5. Diagnóstico de conectividade

Executado em 2026-10-18 contra `https://demo-api.binance.com/api`: ping bem-sucedido, horário do servidor recebido e diferença local observada de aproximadamente 401 ms. Nenhuma ordem foi enviada.

Os WebSockets configurados são `wss://demo-ws-api.binance.com/ws-api/v3` e `wss://demo-stream.binance.com/stream`, conforme a documentação oficial. Este diagnóstico validou REST; a validação persistente dos streams continua como etapa operacional.
