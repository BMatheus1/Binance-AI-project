# Binance Spot Demo

O adapter aceita exclusivamente `https://demo-api.binance.com/api`. Hosts de produção, URLs alternativas e HTTP são rejeitados na construção. Não existe fallback. A Binance documenta esse endereço em [Demo Mode for Spot Trading](https://developers.binance.info/en/docs/products/spot/demo-mode/general-info) e alerta que dados realistas da demo não equivalem a resultados reais.

Há métodos para saldo, exchange info, envio, consulta e cancelamento. Requisições assinadas usam timestamp, `recvWindow`, HMAC e cabeçalho de chave. `clientOrderId` duplicado é bloqueado. NEW, parcial, executada, cancelada e rejeitada são estados distintos; envio nunca é tratado como execução.

Nenhuma conectividade autenticada ou ordem demo foi executada nesta entrega. A política persistente do projeto proíbe integração autenticada automática. Consulte `16_manual_demo.md` para a preparação segura; a ativação exige ação posterior explícita do usuário.
