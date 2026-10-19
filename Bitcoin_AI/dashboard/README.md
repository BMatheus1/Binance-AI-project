# Bitcoin AI Trader Dashboard — Fase 6.3

Dashboard local de observação para os dados das Fases 6, 6.1 e 6.2. O comando de início também executa o worker causal de decisões da Fase 6.1.

## Arquitetura

- `frontend/`: Next.js App Router, TypeScript, Tailwind CSS, Recharts, Lightweight Charts e Lucide.
- `btc_research.dashboard_api`: FastAPI integrada aos SQLite, JSONL, ledgers e controles existentes.
- WebSocket `/api/ws`: snapshots de overview, mercados e saúde a cada dois segundos.
- REST: operações, notícias, resultados, logs sanitizados e exportação CSV.

A API escuta somente em `127.0.0.1`. O navegador cria uma sessão HttpOnly local. Em navegadores embutidos que recusam cookies entre portas de loopback, as rotas de leitura usam um token efêmero mantido apenas na memória e validam a origem. Ações sensíveis continuam exigindo cookie HttpOnly, origem permitida e token CSRF. A única ação operacional exposta é **acionar** o kill switch. Não há endpoint para limpá-lo, enviar ordens ou habilitar `DEMO_AUTONOMOUS`.

## Instalação

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
python -m pip install -e ".[demo,dashboard]"
cd dashboard\frontend
pnpm.cmd install
pnpm.cmd run build
```

## Iniciar

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
powershell -ExecutionPolicy Bypass -File scripts\start_dashboard.ps1 -OpenBrowser
```

Abra [http://127.0.0.1:3000](http://127.0.0.1:3000). A API responde em [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz).

O script aciona o kill switch antes de iniciar, mantém o modo `OBSERVE` e sobe três processos: coletor/analisador, API e frontend. A página **Inteligência** consulta `runtime/phase_6_1/evaluations.sqlite3` a cada cinco segundos. Cada candle fechado e sincronizado gera 12 avaliações (três ativos × quatro políticas) e um ciclo no ledger encadeado.

Para executar somente o coletor/analisador, sem abrir o dashboard:

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
$env:PYTHONPATH = "$PWD\src"
python scripts\run_phase6_2.py kill-switch engage --reason observe_only
python scripts\run_phase6_1.py serve
```

Existe uma trava de instância única para impedir dois workers escrevendo no mesmo heartbeat e ledger.

## Encerrar

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_dashboard.ps1
```

O encerramento aciona o kill switch antes de parar os processos. Os logs ficam em `runtime/phase_6_3/`.

## Estados sem dados

O dashboard não preenche lacunas com valores artificiais. O modelo congelado é específico de BTC; ETH e SOL são avaliados e abstêm com `model_scope_unavailable_for_asset`. O retorno bruto esperado permanece nulo até existir calibração prospectiva válida. Qwen3 é carregado sob demanda somente quando há notícia causalmente disponível; sua indisponibilidade veta C/D sem interromper A/B. Operações diagnósticas permanecem fora das métricas de estratégia.
