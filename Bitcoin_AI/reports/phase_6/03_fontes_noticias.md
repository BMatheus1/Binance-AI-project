# Fontes de notícias

## Ativas na configuração inicial

| Fonte | Integração | Autenticação | Frequência | Conteúdo armazenado | Situação |
|---|---|---|---:|---|---|
| Federal Reserve | RSS oficial `press_all.xml` | Não | 120 s | Metadados fornecidos pelo feed | Implementada e consultada |
| SEC | RSS oficial de press releases | Não | 120 s | Metadados fornecidos pelo feed | Implementada e consultada |
| BLS | RSS oficial `bls_latest.rss` | Não | 120 s | Metadados fornecidos pelo feed | Implementada; HTTP 403 no smoke de 18/10/2026 |

Referências verificadas em 18/10/2026: [Federal Reserve RSS](https://www.federalreserve.gov/feeds/feeds.htm), [SEC RSS](https://www.sec.gov/about/rss-feeds) e [BLS RSS](https://www.bls.gov/feed/).

Cada consulta usa HTTPS, timeout, limite de 2 MB, User-Agent identificável, intervalo mínimo por fonte, até três tentativas e isolamento de falhas. O serviço armazena somente título, link e resumo entregue pelo feed; não raspa artigos.

No smoke público de 18/10/2026, Federal Reserve e SEC retornaram 45 eventos no total, persistidos no Event Store. O BLS retornou HTTP 403 e não forneceu eventos. A falha foi registrada; o coletor não tentou contornar a restrição.

## Opcionais, ainda inativas

Reuters, Bloomberg, CNBC, CNN, NYT, Financial Times, WSJ, CoinDesk, The Block, X e Reddit não foram ativados. API, licença, autenticação, redistribuição e periodicidade precisam ser verificadas e aprovadas para cada provedor. O código não contorna paywall nem scraping proibido. Comunicados oficiais de exchanges e projetos exigem um catálogo versionado antes de entrar no experimento.

Uma falha de feed não remove o gerenciamento de risco. Conteúdo externo é sempre dado não confiável e nunca altera configuração nem chama broker.
