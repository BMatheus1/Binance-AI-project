# Fase 6.4.1 — habilitação segura na Binance Demo

Esta entrega mantém `BTCUSDT`, política `A_quantitative`, horizonte de 5 minutos e teto de 10 USDT congelados. A plataforma inicia em `OBSERVE`, rearma o kill switch antes dos serviços e só aceita autorização temporária pela CLI, vinculada ao `boot_id` do motor.

Consulte `connectivity_status.json` para a evidência técnica executada, `operational_snapshot.json` para uma amostra imutável do worker ativo, `01_diagnostico_conectividade.md` para a causa da falha, `02_validacao_seguranca.md` para os testes e `03_comandos_operacionais.md` para a sequência de operação.

Nenhuma sessão foi autorizada e nenhuma ordem foi enviada nesta correção.
