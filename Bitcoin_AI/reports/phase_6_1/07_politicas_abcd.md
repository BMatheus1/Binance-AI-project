# Comparação das políticas A, B, C e D

- A_quantitative: apenas os modelos e filtros quantitativos existentes.
- B_conservative_news: adiciona o classificador determinístico da Fase 6.
- C_qwen3_structured_news: usa Qwen3 somente como bloqueio de risco.
- D_event_market_reaction: combina o contexto validado com confirmação observável.

Todas recebem os mesmos snapshots, ativos, custos e limites. Sentimento positivo
nunca cria uma operação. Resultado Qwen inválido, insuficiente ou injetado força
abstenção na política C. A política D também se abstém quando há notícia sem reação
confirmada.

O avaliador pareado funciona e registra oportunidades e abstenções. Ainda não há
amostra prospectiva para comparar lucro líquido, drawdown ou retorno ajustado ao
risco. Nenhuma política foi promovida.

