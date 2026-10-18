# Diagnóstico operacional da conta demo

O adaptador aceita somente https://demo-api.binance.com/api, exige habilitação
explícita e rejeita ambiente diferente. Não existe fallback para produção e o
projeto não implementa execução real.

Continuam pendentes antes de qualquer teste operacional:

1. criar uma chave exclusiva da Binance Spot Demo;
2. armazenar segredo fora do código;
3. confirmar conectividade e permissões mínimas;
4. testar autenticação, saldo, idempotência, parcial, cancelamento e reconciliação;
5. validar kill switch e recuperação de falha;
6. obter autorização explícita do usuário para habilitar ordens demo.

Nenhuma credencial foi solicitada ou usada e nenhuma ordem demo foi enviada.

