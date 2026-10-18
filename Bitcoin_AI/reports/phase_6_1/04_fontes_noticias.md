# Inventário das fontes de notícias

Fontes efetivamente integradas e consultadas:

- Federal Reserve: feed oficial de comunicados.
- SEC: feed oficial de comunicados.
- BLS: feed oficial configurado; respondeu HTTP 403 e não foi contornado.
- Bitcoin Core: feed Atom de releases do repositório oficial.
- go-ethereum: feed Atom de releases do repositório oficial.
- Agave: feed Atom de releases do cliente Solana mantido pela Anza.

Após o smoke persistente, o Event Store continha 75 eventos: 20 Federal Reserve,
25 SEC e 10 de cada feed de releases. O BLS não produziu eventos.

Reuters, Bloomberg, CNBC, Financial Times, Wall Street Journal, CNN, New York Times,
CoinDesk e The Block não foram integrados porque este trabalho não confirmou uma API
ou licença de redistribuição adequada. Nenhum bloqueio ou paywall foi contornado.
Somente metadados fornecidos pelos feeds são persistidos.

