# Arquitetura do motor autônomo

O `SupervisedDemoEngine` é um worker separado da inferência pesada. Ele lê avaliações persistidas, aplica gates determinísticos, registra a intenção antes do envio, usa exclusivamente o adaptador Binance Demo e acompanha a posição até a saída. A abertura do dashboard nunca autoriza ordens.
