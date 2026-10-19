# 9. Qwen3 e filas de notícias

A Fase 6.1 já mantém carregamento único, cache LRU, fila limitada e timeout. A Fase 6.2 adiciona uma fila por prioridade baseada em novidade e relevância, deduplicação por fingerprint, rejeição de notícia atrasada e contadores de backlog.

O coletor de mercado não aguarda a inferência. Se a classificação válida não chegar a tempo, não se inventa um resultado e a política dependente deve abster-se. Quantização ou troca de modelo continua condicionada a licença comercial e comparação de qualidade.
