# Segurança

API e frontend vinculam-se apenas a `127.0.0.1`. CORS aceita somente as origens locais configuradas. Leituras exigem sessão local; navegadores embutidos podem usar token efêmero em memória com validação de origem.

O único endpoint mutável aciona o kill switch e exige cookie HttpOnly, origem aceita, CSRF e frase de confirmação. Não existem rotas para limpar o kill switch, enviar ordens ou habilitar negociação autônoma. Testes confirmam que variáveis de credencial não aparecem nas respostas.
