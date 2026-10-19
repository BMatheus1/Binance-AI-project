# Arquitetura

- Frontend: Next.js 16, React 19, TypeScript, Tailwind, Recharts, Lightweight Charts e Lucide.
- Backend: FastAPI, Pydantic e adaptadores já existentes das Fases 6–6.2.
- Tempo real: WebSocket local com snapshot periódico.
- Persistência consultada: SQLite e JSONL já produzidos pelo projeto.
- Execução Windows: `scripts/start_dashboard.ps1` e `scripts/stop_dashboard.ps1`.

O frontend não contém credenciais nem cliente Binance. Toda consulta autenticada passa pelo adaptador Demo do backend.
