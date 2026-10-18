# 09 — Plano para a Fase 3

1. Reservar candles posteriores a setembro/2026 sem consulta durante desenvolvimento e registrar antecipadamente o corte temporal.
2. Repetir somente as variantes selecionadas internamente ({'1': 'xgboost_contextual_regularized', '5': 'xgboost_original'}) contra frequência e o vencedor congelado da Fase 1.
3. Obter dados de execução, AggTrades e/ou snapshots de livro apenas se houver hipótese explícita; medir latência, spread, slippage, lote, tick e minNotional.
4. Executar previsão em tempo real em modo sombra, sem ordens, salvando entrada disponível, probabilidade, versão e resultado posterior.
5. Considerar dinheiro real somente após teste independente, calibração estável, expectativa líquida positiva com margem de segurança e revisão operacional. A Fase 2 não satisfaz essas condições.
