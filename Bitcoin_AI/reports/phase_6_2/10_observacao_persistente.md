# 10. Observação persistente

O comando `observe` reutiliza o coletor multiativo. Heartbeat e supervisão das Fases 6/6.1 foram preservados. A Fase 6.2 grava pedido de parada e aciona o kill switch com `stop-services`.

O smoke final de 8 segundos recebeu 655 mensagens de BTCUSDT, 603 de ETHUSDT e 129 de SOLUSDT. Os três livros ficaram válidos e saudáveis, sem reconexões ou ordens. Isso valida somente a conectividade curta; antes de deixar o serviço ativo por longo período, verifique heartbeat, reconexão, filas e consumo de memória.
