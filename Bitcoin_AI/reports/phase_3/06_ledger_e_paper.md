# 06 — Ledger imutável e paper trading

O ledger é append-only e encadeado por SHA-256. Uma previsão registra versão, features, probabilidades, qualidade e decisão antes do resultado; a resolução é um novo registro e não altera a previsão. A verificação detecta edição, remoção ou reordenação.

O simulador Spot usa compra no ask e venda no bid observados, taxas por lado e latência registrada. O simulador de payout permanece separado. Não existe cliente autenticado, envio de ordem, credencial ou movimentação financeira.
