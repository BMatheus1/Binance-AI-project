# 03 — Operação do observador

O smoke test público rodou por 130 segundos após o congelamento. Foram recebidas 6244 mensagens, com 0 reconexões, 0 eventos de gap de AggTrade e 0 invalidações do livro. O livro terminou válido: True.

Candles encerrados novos: 2. Previsões registradas: 28; resolvidas: 4; pendentes: 8; abstenções técnicas: 0. Atraso interno até o callback: {'n': 6244, 'median': 0.22699999999999998, 'p95': 0.744, 'max': 1818.416}. Delta assinado entre relógio da origem e recebimento: {'n': 1755, 'median': -974.5540000000001, 'p05': -975.2479, 'p95': -817.0654999999999, 'min': -975.673, 'max': 744.208}. Latência origem→recebimento não negativa: {'n': 14, 'median': 141.851, 'p95': 679.46605, 'max': 744.208}.

O teste valida o caminho operacional e a ordem imutável previsão→resultado. A amostra é insuficiente para qualquer conclusão econômica. Nenhuma ordem foi enviada.
