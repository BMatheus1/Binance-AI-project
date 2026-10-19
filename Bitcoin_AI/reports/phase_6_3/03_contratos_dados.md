# Contratos de dados

Os endpoints retornam envelopes com `generated_at` e `data`. Estados incertos usam `null`, `unknown`, `stale` ou `unavailable`.

Operações carregam `category` e `strategy_evaluation_eligible`. O diagnóstico reconciliado usa `category=diagnostic` e nunca alimenta win rate, drawdown ou P&L da estratégia. Notícias expõem metadados, classificações e links; o corpo integral e segredos não são enviados ao frontend.
