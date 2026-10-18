# E — Experimentos

Execução: `20261017T174250393322Z-research`. Python local, versões e hashes registrados em development.json.

Treino: até 6.000 posições igualmente espaçadas por mês. Calibração/validação/teste: todos os minutos elegíveis. Seleção por log loss de validação. Ajustes estatísticos e normalização somente no treino; calibração em bloco posterior independente. Purga pelo término do rótulo e embargo de 5 minutos. Nenhum modelo é promovido automaticamente.

## Horizonte 1 minuto(s)

| Conjunto | N | Início UTC | Fim UTC |
|---|---|---|---|
| train | 161999 | 2023-10-01 01:01:00+00:00 | 2025-12-31 23:52:00+00:00 |
| calibration | 129589 | 2026-01-01 00:05:00+00:00 | 2026-03-31 23:53:00+00:00 |
| validation | 131029 | 2026-04-01 00:05:00+00:00 | 2026-06-30 23:53:00+00:00 |
| test | 132469 | 2026-07-01 00:05:00+00:00 | 2026-09-30 23:53:00+00:00 |

Escolhido antes do teste: **xgboost**. Política: Nenhum limiar atingiu evidência mínima de expectativa positiva; abstenção integral.

## Horizonte 5 minuto(s)

| Conjunto | N | Início UTC | Fim UTC |
|---|---|---|---|
| train | 161998 | 2023-10-01 01:01:00+00:00 | 2025-12-31 23:45:00+00:00 |
| calibration | 129585 | 2026-01-01 00:05:00+00:00 | 2026-03-31 23:49:00+00:00 |
| validation | 131025 | 2026-04-01 00:05:00+00:00 | 2026-06-30 23:49:00+00:00 |
| test | 132465 | 2026-07-01 00:05:00+00:00 | 2026-09-30 23:49:00+00:00 |

Escolhido antes do teste: **xgboost**. Política: Nenhum limiar atingiu evidência mínima de expectativa positiva; abstenção integral.
