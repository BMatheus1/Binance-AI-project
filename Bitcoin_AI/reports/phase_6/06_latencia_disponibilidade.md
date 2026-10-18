# Latência e disponibilidade

Ainda não existe uma amostra operacional longa. Portanto, latência típica, disponibilidade e perda de eventos permanecem **não medidas**.

Um ciclo público foi executado em 18/10/2026. Federal Reserve e SEC responderam e produziram 45 eventos; o BLS respondeu HTTP 403 após as tentativas configuradas. Isso valida ingestão e isolamento de falhas, mas uma única consulta não estima disponibilidade nem atraso típico.

O esquema já separa `published_at`, `first_received_at` e `analyzed_at`. O experimento calculará atraso publicação→recebimento, recebimento→análise, falhas por fonte, revisões, duplicatas e ciclos pulados. Uma notícia recebida depois da decisão nunca entra retroativamente.

O monitor de mercado é independente do scheduler de notícias. Falha ou atraso que torne dados incompletos bloqueia entradas no Risk Manager.

O smoke multiactivos de 15 segundos recebeu 363 mensagens BTCUSDT, 603 ETHUSDT e 150 SOLUSDT. Os três livros terminaram sincronizados, sem reconexões, IDs AggTrade ausentes, duplicatas ou invalidações de profundidade. A duração curta comprova integração operacional, não disponibilidade prolongada.
