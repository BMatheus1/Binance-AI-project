# Auditoria da arquitetura existente

Data da revisão: 2026-10-18.

O trabalho continuou sobre a Fase 6 sem reiniciar o projeto. Foram reutilizados o
Event Store SQLite, o coletor público multiativo, o seletor de ativos, o gerenciador
de risco, o paper broker, o adaptador demo bloqueado, o ledger e o serviço de feeds.

As extensões da Fase 6.1 são: interface NLP estruturada, Qwen3 local, fila assíncrona
limitada, cache LRU, políticas C e D, deduplicação entre fontes, detecção de eventos,
supervisor, heartbeat e logs rotativos. Os resultados históricos não foram usados
para escolher a nova política. Julho a setembro de 2026 permanece consumido e não
foi reutilizado como teste independente.

A execução padrão continua sendo observação. Não existe caminho para ordens reais.

