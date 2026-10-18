# 09 — Fontes oficiais

- Arquivos públicos Binance Spot: <https://data.binance.vision/data/spot/daily/aggTrades/BTCUSDT/>
- Esquema, checksums e política de timestamps: <https://github.com/binance/binance-public-data/>
- Streams oficiais Spot (`aggTrade`, `kline`, `bookTicker`, diff depth): <https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md>
- Endpoints públicos sem autenticação: <https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md>

O manifesto `data/phase_3/manifests/download.json` registra a URL e o SHA-256 verificado de cada um dos 14 ZIPs. A interpretação de `is_buyer_maker` é explícita: `false` indica comprador agressor e `true` vendedor agressor. Um AggTrade representa a agregação associada a uma ordem taker; `underlying_trade_count` é calculado pela faixa `last_trade_id - first_trade_id + 1` e não transforma o registro agregado em trades individuais inventados.
