# Diagnóstico de conectividade

## Causa identificada

Os endpoints configurados já correspondem aos endpoints oficiais atuais da Binance Spot Demo:

- REST: `https://demo-api.binance.com/api`
- WebSocket API: `wss://demo-ws-api.binance.com/ws-api/v3`
- Market streams: `wss://demo-stream.binance.com/ws` ou `/stream`, nas portas 443 e 9443

O diagnóstico inicial executado dentro do ambiente restrito resolveu DNS, porém recebeu falha TCP imediata na porta 443. A repetição fora dessa restrição aprovou TCP, TLS, REST e WebSocket. Portanto, as reconexões anteriores foram causadas pelo isolamento de rede do processo que iniciou o supervisor, e não por endpoint obsoleto, DNS incorreto ou credencial inválida.

O startup agora executa um preflight somente leitura antes de abrir os serviços. Uma falha no preflight não libera ordens: o sistema continua em `OBSERVE`, com kill switch ativo e a indisponibilidade visível no dashboard.

Depois que o transporte voltou a funcionar, o primeiro candle novo revelou uma incompatibilidade local independente da Binance: o worker tratava as entradas do catálogo `SPECS` como objetos, embora o catálogo congelado use tuplas. A leitura do lookback foi corrigida para o terceiro campo da tupla. Nenhum feature, modelo, limiar ou parâmetro da política foi alterado. Após a correção, o worker passou a gravar 12 avaliações causais por ciclo (quatro políticas × três ativos), incluindo abstenções e motivos.

## Evidência de 19/10/2026

- DNS: os três hosts Demo resolveram endereços IPv4.
- TLS: TLS 1.3, hostname verificado e certificado válido até 09/01/2027 nos três serviços.
- REST: `/api/v3/ping`, `/api/v3/time` e `exchangeInfo` responderam; `BTCUSDT` estava `TRADING`.
- WebSocket de mercado: evento real `trade` de `BTCUSDT` recebido nas portas 443 e 9443.
- WebSocket API: método público `ping` respondeu status 200.
- Autenticação: leitura da conta SPOT aceita, `canTrade=true` e saldos fictícios retornados.
- Filtros: `MIN_NOTIONAL=5`; o plano calculado para o teto de 10 USDT ficou dentro dos filtros vigentes.
- Segurança: kill switch ativo, modo `OBSERVE`, nenhuma autorização e `orders_sent=false`.

O arquivo `connectivity_status.json` contém os tempos, endereços, protocolo TLS e resultados completos sem chaves ou secrets.

Referências oficiais: [Binance Spot Demo Mode](https://developers.binance.info/en/docs/products/spot/demo-mode/general-info) e [Binance Spot REST API](https://developers.binance.info/en/docs/products/spot/rest-api).
