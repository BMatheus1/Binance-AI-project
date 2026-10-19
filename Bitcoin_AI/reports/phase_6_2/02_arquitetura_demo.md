# 2. Arquitetura final da integração Demo

O modo padrão é `OBSERVE`. `PAPER` permanece local. `DEMO_DIAGNOSTIC` exige a variável de habilitação, kill switch liberado e frase explícita por execução. `DEMO_AUTONOMOUS` exige ainda diagnóstico reconciliado e aprovação prospectiva da política congelada.

Toda intenção de ordem é persistida em SQLite antes da requisição. Em timeout, o sistema consulta o `clientOrderId` e nunca repete cegamente a ordem. Estado desconhecido, encerramento parcial ou falha de reconciliação aciona o kill switch. A Spot Demo admite somente compra e venda da quantidade adquirida; não há margin, alavancagem, short ou fallback para produção.
