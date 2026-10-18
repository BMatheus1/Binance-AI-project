# 08 — Monitoramento e notícias

Indicadores mínimos: atraso origem→recebimento, reconexões, IDs duplicados/perdidos, validade do livro, minutos completos, taxa de abstenção, deriva das features, calibração e resultado paper por dia.

Notícias entram somente por `ExternalEvent`: fonte, identificador, publicação, recebimento, categoria, confiabilidade e hipótese de relevância. O filtro macro pode elevar risco e forçar abstenção; ele não cria sinal direcional e não usa conteúdo futuro.
