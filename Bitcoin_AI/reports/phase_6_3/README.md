# Fase 6.3 — Dashboard profissional local

O dashboard foi implementado em `dashboard/frontend` e `btc_research.dashboard_api`. Ele consolida dados reais já persistidos pelas Fases 6, 6.1 e 6.2 e consultas autenticadas da Binance Spot Demo quando a conexão está disponível.

Estado validado em 18/10/2026:

- Next.js App Router com páginas de visão geral, mercados, operações, resultados, inteligência, notícias e saúde;
- FastAPI local em `127.0.0.1:8000` e frontend em `127.0.0.1:3000`;
- WebSocket local para snapshots, REST para consultas e exportações CSV;
- uma operação diagnóstica formada por dois registros reconciliados, excluída das métricas de estratégia;
- 75 eventos reais no Event Store;
- zero posições intencionais e zero resultado de estratégia calculável;
- kill switch ativo e negociação autônoma bloqueada;
- 153 testes Python aprovados, TypeScript aprovado e build de produção aprovado.

No encerramento da validação, uma nova consulta à Binance Demo falhou por `ConnectionError`. O dashboard apresentou `unavailable` sem reutilizar saldos como se fossem atuais. O último saldo autenticado fica documentado como histórico, com horário de captura, e não como cotação ao vivo.

Consulte `dashboard/README.md` para instalar, iniciar e encerrar.
