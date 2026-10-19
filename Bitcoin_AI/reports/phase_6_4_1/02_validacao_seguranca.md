# Validação dos controles de segurança

## Testes automatizados

A suíte completa terminou com **168 testes aprovados**. O build de produção do dashboard também foi concluído com sucesso.

Os cenários pedidos estão cobertos por testes determinísticos, sem rede e sem credenciais:

| Requisito | Cobertura |
|---|---|
| Produção inacessível | allowlist rejeita REST e WebSocket de produção, HTTP e hosts externos; não existe fallback |
| Sem operação sem autorização | motor com avaliação válida e kill switch limpo permanece em `OBSERVE` sem sessão vinculada |
| Timeout sem duplicação | intenção é persistida antes do envio; recuperação consulta o mesmo `clientOrderId` uma vez e nunca repete a ordem |
| Estado desconhecido | diário passa para `UNKNOWN`, aciona kill switch e exige reconciliação |
| Perda de conexão | falha de reconciliação muda o motor para `RECOVERY_REQUIRED`, rearma o kill switch e não cria posição |
| Limites e filtros | valor, saldo, `MIN_NOTIONAL`, quantidade, spread, profundidade, slippage, cooldown, frequência e perda diária são verificados |
| Reinicialização | posição permanece no SQLite; autorização do processo anterior é invalidada pelo novo `boot_id` |

## Evidência operacional supervisionada

Após reiniciar os processos com acesso de rede, o coletor recebeu milhares de mensagens reais da Binance Demo sem acrescentar reconexões. O warmup carregou 240 candles fechados para BTCUSDT, ETHUSDT e SOLUSDT, com cotação e profundidade disponíveis. O motor permaneceu em `OBSERVE`, `orders_enabled=false`, sem sessão e sem posição.

O protocolo de 24 horas continua em andamento. Problemas históricos registrados antes da correção permanecem no relatório acumulado por motivos de auditoria; eles não foram apagados nem reclassificados.
