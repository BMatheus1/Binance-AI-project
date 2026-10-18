# Manual de configuração Binance Demo

1. Confirme se Demo Trading está disponível para sua região e conta na interface oficial da Binance.
2. Crie uma chave **dentro do Demo Mode**. Nunca reutilize chave real.
3. Mantenha a chave sem permissão de saque e aplique as restrições oferecidas pela conta demo.
4. Armazene localmente em variáveis `BINANCE_DEMO_API_KEY` e `BINANCE_DEMO_API_SECRET`. `.env` e `.env.*` são ignorados pelo Git.
5. Execute primeiro os testes. A configuração padrão continua desabilitada.
6. A frase de habilitação reconhecida pelo adapter é `BITCOIN_AI_ENABLE_DEMO_ORDERS=I_UNDERSTAND_DEMO_ONLY`. Defini-la apenas prepara o adapter; nenhum script entregue envia ordens automaticamente.
7. Verifique `readiness()`: host deve ser `demo-api.binance.com`, `production_endpoint_accessible=false` e `ready=true`.
8. Valide saldo, regras do símbolo, ordem mínima, consulta, cancelamento, parcial, rejeição, timeout e reconciliação em teste opcional separado.
9. Para interromper, remova a variável de habilitação e acione o kill switch. Posições virtuais existentes devem ser reconciliadas antes de encerrar o processo.

Não coloque valores das chaves em comandos, logs, relatórios ou tickets. A versão entregue não executou autenticação e permanece em observação.
