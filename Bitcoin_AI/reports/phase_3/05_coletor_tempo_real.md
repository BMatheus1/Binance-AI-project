# 05 — Coletor público em tempo real

`btc_research.live_market` implementa os streams públicos `aggTrade`, `kline_1m`, `bookTicker` e `depth@100ms`. Cada registro inclui horário da origem, horário local de recebimento, tipo e payload bruto, particionado em JSONL.

AggTrade IDs repetidos e saltos são registrados. O livro local segue a sequência oficial: eventos são armazenados em buffer, o snapshot REST público é aplicado e somente então os deltas contíguos são aceitos. Qualquer salto invalida o livro e força nova sincronização. Dados incompletos geram abstenção técnica.

## Smoke test público

Recebidas 430 mensagens em 15 segundos, com 0 reconexões, 0 IDs duplicados, 0 IDs ausentes e 0 invalidações. Livro válido ao final: True.
