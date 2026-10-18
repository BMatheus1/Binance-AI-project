# 01 — Auditoria estatística

O alvo permanece multiclasse: 0 baixa, 1 empate e 2 alta. A decisão ocorre após o fechamento do candle `t`, a entrada histórica é `open[t+1]` e a saída é `close[t+h]`. A log loss usa as três probabilidades na mesma observação; a referência constante de 50% só é válida ao excluir empates. Para a amostra multiclasse, os baselines são frequência aprendida no treino e uniforme 1/3.

Features terminam em `decision_time`, alvos permanecem separados, indicadores reiniciam em lacunas e a purga exige `event_end` anterior ao bloco seguinte. Julho–setembro/2026 não foi lido. Nenhuma inconsistência crítica foi encontrada. A seleção curta da Fase 3 continua classificada como exploratória, não como teste independente.
