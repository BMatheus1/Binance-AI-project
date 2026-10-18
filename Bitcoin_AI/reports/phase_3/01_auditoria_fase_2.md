# 01 — Auditoria da Fase 2

- O alvo é multiclasse: baixa, empate e alta. A log loss principal usa três probabilidades que somam 1.
- A referência constante de 50% é válida somente no subconjunto binário sem empates; seu log loss é ln(2) = 0,693147. Para três classes, a referência correta é a frequência estimada no treino.
- A calibração da Fase 2 foi ajustada em bloco posterior ao treino e anterior à validação.
- O período julho–setembro/2026 continua marcado como teste final consumido e não foi aberto nesta fase.
- Significância estatística, calibração e resultado econômico são diagnósticos distintos. Nenhuma melhora estatística foi tratada como lucro.

Execução auditada: `20261017T223631458343Z-phase2`. Última validação da Fase 2: 2026-06-30 23:44:00+00:00.
