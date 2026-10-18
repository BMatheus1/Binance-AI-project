# Catálogo de eventos

Cada `NewsEvent` registra ID determinístico, fonte, título, URL, publicação, primeiro recebimento, análise, ativos afetados, categoria, resumo limitado, sentimento por ativo, intensidade, confiança, confiabilidade da fonte, confirmação, novidade, relações, hipótese de precificação, evidência de reação e detecção de instruções não confiáveis.

Categorias iniciais: macro, regulação, incidente de segurança, notícia de mercado e conteúdo não confiável. Sentimentos permitidos: positivo, negativo, neutro, ambíguo e não confiável.

O SQLite mantém `first_received_at` e chave única por evento. Repetições idênticas são descartadas; mudanças de conteúdo formam revisões. Consultas causais exigem publicação, recebimento e análise anteriores ou iguais ao instante da decisão.

`assess_market_reaction` registra retornos antes/depois do recebimento, razão de volume e spread. Movimento anterior ao recebimento acima do limiar marca `possibly_priced_in`; a função não cria direção. O contexto operacional ignora eventos com instruções maliciosas e mantém ajuste direcional igual a zero.
