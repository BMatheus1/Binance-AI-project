# Auditoria inicial

A Fase 6.4 evolui os serviços das Fases 6.1–6.3. O worker causal, o Event Store, o ledger, o adaptador estritamente Demo, o kill switch e o dashboard foram preservados. A falha observada após timeout na recomposição REST foi convertida em degradação recuperável: o candle recebido continua registrado e a previsão fica indisponível até existir novamente uma janela contínua.
