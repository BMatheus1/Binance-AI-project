# Testes

- `python -m pytest -q`: 153 aprovados.
- `python -m pytest -q tests/test_phase6_3_dashboard.py`: 14 aprovados.
- `python -m compileall -q src scripts`: aprovado.
- `pnpm.cmd run typecheck`: aprovado.
- `pnpm.cmd run build`: aprovado, com sete páginas funcionais e a página 404 geradas.
- `git diff --check`: sem erros de whitespace.
- ciclo `start_dashboard.ps1` → `stop_dashboard.ps1` → novo início: aprovado, sem processo filho ocupando as portas.

Os testes da Fase 6.3 cobrem sessão, origem, token de leitura, CSRF, kill switch, ausência de rota de desbloqueio, sigilo de credenciais, residual, separação financeira, notícias, símbolos inválidos, CSV, WebSocket e SQLite somente leitura.
