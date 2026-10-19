# Auditoria das fontes

O backend usa somente artefatos existentes: banco de execução da Fase 6.2, Event Store da Fase 6, telemetria JSONL de mercado e controles persistentes de segurança. Bancos SQLite são abertos em modo somente leitura e com `query_only=ON`.

Dados ausentes não são sintetizados. Métricas sem operações de estratégia ficam nulas; Qwen3 fica `unknown` sem telemetria ativa; saldos ficam indisponíveis quando a Binance Demo não responde.
