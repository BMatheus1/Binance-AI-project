# 8. Testes de segurança

Foram validados: rejeição de produção, segredo ausente das saídas, ordens bloqueadas por padrão, consultas autenticadas independentes da autorização de ordem, kill switch persistente e fail-closed, journal idempotente, recuperação de timeout sem reenvio, status desconhecido bloqueando entradas e reconciliação obrigatória.

A suíte automatizada usa mocks. Nenhum teste automatizado envia ordens externas.
