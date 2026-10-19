# Reconciliação e recuperação

Antes da primeira entrada após cada inicialização, o motor consulta intenções não resolvidas, ordens abertas e, quando há posição, saldo BTC disponível. Divergência aciona `RECOVERY_REQUIRED` e o kill switch. Timeout não causa reenvio automático: a ordem é consultada pelo identificador, coerente com a [regra oficial de status desconhecido após timeout/5xx](https://developers.binance.info/en/docs/products/spot/rest-api).
