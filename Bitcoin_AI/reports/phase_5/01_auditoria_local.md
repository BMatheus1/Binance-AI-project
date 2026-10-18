# 01 — Auditoria dos dados e modelos existentes

Os artefatos das Fases 1–4 permanecem referenciados por SHA-256 no manifesto de exportação. A Fase 4 congelou XGBoost em 1/5/15 minutos e CatBoost em 30 minutos, todos apenas para shadow. As previsões históricas de abril–junho/2026 contêm `decision_time`, `event_end`, alvo, retorno, entrada, saída e probabilidades baixa/empate/alta.

O exportador usa os Parquets já validados e reduz os candles aos seis campos exigidos: open, high, low, close, volume e amount. `amount` corresponde a `quote_volume` em USDT. Tempos são UTC, candles precisam ser contínuos e nenhuma linha em ou depois de 01/07/2026 pode ser exportada.

A comparação usa exatamente as mesmas 256 decisões para Kronos e os modelos congelados. Isso é uma análise exploratória incremental sobre a validação da Fase 4, não um novo teste independente.
