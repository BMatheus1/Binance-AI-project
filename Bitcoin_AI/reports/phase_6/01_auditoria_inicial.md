# Auditoria inicial

Foram encontrados e reaproveitados:

- `live_market.py`: AggTrade, candle, bookTicker, profundidade, reconexão, detecção de gaps e livro local.
- `prospective.py`: ledger SHA-256 append-only, previsões causais e paper Spot com custos.
- `external.py`: eventos externos com publicação, recebimento e filtro macro causal.
- modelos congelados das Fases 1–5 e observador da Fase 4.

Lacunas identificadas: operação multiactivos, serviço persistente de RSS, deduplicação com revisões, classificação por ativo, comparação A/B, seleção entre ativos, risco de duração/prorrogação, broker paper idempotente e fronteira Binance Demo.

Os hashes congelados foram copiados para `preservation.json`. Nenhum dataset, modelo ou resultado anterior foi alterado, e o teste final já consumido não foi reaberto.
