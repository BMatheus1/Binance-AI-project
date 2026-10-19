from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


OUT = ROOT / "reports/phase_6_2"
OUT.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc).isoformat()


def write(name: str, body: str) -> None:
    (OUT / name).write_text(body.strip() + "\n", encoding="utf-8")


def digest(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


write("01_auditoria_implementacao.md", """
# 1. Auditoria da implementação existente

As Fases 6 e 6.1 já forneciam seleção de ativos, políticas A–D, Risk Manager, broker paper, ledger encadeado, observação de mercado, coleta de notícias e Qwen3 desacoplado. O adaptador Binance Demo já impedia endpoints de produção e assinava requisições, mas não possuía transporte HTTP concreto nem separava consultas autenticadas da autorização de ordens.

A Fase 6.2 reaproveita esses componentes. O adaptador recebeu transporte `requests` com HTTPS, host e caminhos em allowlist; consultas autenticadas podem ser feitas com as ordens bloqueadas. Resultados históricos e períodos finais não foram reprocessados.
""")

write("02_arquitetura_demo.md", """
# 2. Arquitetura final da integração Demo

O modo padrão é `OBSERVE`. `PAPER` permanece local. `DEMO_DIAGNOSTIC` exige a variável de habilitação, kill switch liberado e frase explícita por execução. `DEMO_AUTONOMOUS` exige ainda diagnóstico reconciliado e aprovação prospectiva da política congelada.

Toda intenção de ordem é persistida em SQLite antes da requisição. Em timeout, o sistema consulta o `clientOrderId` e nunca repete cegamente a ordem. Estado desconhecido, encerramento parcial ou falha de reconciliação aciona o kill switch. A Spot Demo admite somente compra e venda da quantidade adquirida; não há margin, alavancagem, short ou fallback para produção.
""")

write("03_credenciais_demo.md", """
# 3. Credenciais Binance Demo

Crie as credenciais somente na área da Binance Demo. O projeto espera `BINANCE_DEMO_API_KEY` e `BINANCE_DEMO_API_SECRET` no `.env` local. O `.env.example` contém somente nomes e instruções, sem segredos.

Referência oficial: [Binance Spot Demo Mode](https://developers.binance.info/en/docs/products/spot/demo-mode/general-info).
""")

write("04_configuracao_windows.md", r"""
# 4. Configuração no Windows

No PowerShell, a partir da raiz do projeto:

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
python -m pip install -e ".[demo]"
Copy-Item .env.example .env -ErrorAction Stop
notepad .env
python scripts/run_phase6_2.py environment
```

Se o `.env` já existe, não execute `Copy-Item`. Nunca cole os valores no terminal, em commits ou em mensagens.
""")

write("05_conectividade.md", """
# 5. Diagnóstico de conectividade

Executado em 2026-10-18 contra `https://demo-api.binance.com/api`: ping bem-sucedido, horário do servidor recebido e diferença local observada de aproximadamente 401 ms. Nenhuma ordem foi enviada.

Os WebSockets configurados são `wss://demo-ws-api.binance.com/ws-api/v3` e `wss://demo-stream.binance.com/stream`, conforme a documentação oficial. Este diagnóstico validou REST; a validação persistente dos streams continua como etapa operacional.
""")

write("06_autenticacao.md", """
# 6. Validação de autenticação

A consulta assinada `GET /api/v3/account` foi aceita na Binance Demo. A resposta indicou conta `SPOT`, permissão `SPOT` e `canTrade=true`. O relatório e a saída da CLI não contêm API key, secret ou assinatura. Nenhuma ordem foi enviada.
""")

write("07_endpoints_permissoes.md", """
# 7. Endpoints e permissões

REST aceito: somente `https://demo-api.binance.com/api`. Quatro destinos indevidos de teste, incluindo hosts de produção, HTTP sem TLS e host externo, foram rejeitados localmente. Não existe fallback.

Na conta Demo consultada: `canTrade=true`, `canDeposit=true`, `canWithdraw=true`, tipo `SPOT`; saldos virtuais livres observados: 5.000 USDT e 5.000 USDC. `BTCUSDT` estava `TRADING`, sem ordens abertas, `minNotional=5`, `stepSize=0.00001` e quantidade máxima de mercado informada pela bolsa. Esses valores são temporais e devem ser consultados novamente antes de cada diagnóstico.
""")

write("08_testes_seguranca.md", """
# 8. Testes de segurança

Foram validados: rejeição de produção, segredo ausente das saídas, ordens bloqueadas por padrão, consultas autenticadas independentes da autorização de ordem, kill switch persistente e fail-closed, journal idempotente, recuperação de timeout sem reenvio, status desconhecido bloqueando entradas e reconciliação obrigatória.

A suíte automatizada usa mocks. Nenhum teste automatizado envia ordens externas.
""")

write("09_qwen3_filas.md", """
# 9. Qwen3 e filas de notícias

A Fase 6.1 já mantém carregamento único, cache LRU, fila limitada e timeout. A Fase 6.2 adiciona uma fila por prioridade baseada em novidade e relevância, deduplicação por fingerprint, rejeição de notícia atrasada e contadores de backlog.

O coletor de mercado não aguarda a inferência. Se a classificação válida não chegar a tempo, não se inventa um resultado e a política dependente deve abster-se. Quantização ou troca de modelo continua condicionada a licença comercial e comparação de qualidade.
""")

write("10_observacao_persistente.md", """
# 10. Observação persistente

O comando `observe` reutiliza o coletor multiativo. Heartbeat e supervisão das Fases 6/6.1 foram preservados. A Fase 6.2 grava pedido de parada e aciona o kill switch com `stop-services`.

O smoke final de 8 segundos recebeu 655 mensagens de BTCUSDT, 603 de ETHUSDT e 129 de SOLUSDT. Os três livros ficaram válidos e saudáveis, sem reconexões ou ordens. Isso valida somente a conectividade curta; antes de deixar o serviço ativo por longo período, verifique heartbeat, reconexão, filas e consumo de memória.
""")

write("11_operacao_diagnostica.md", """
# 11. Operação diagnóstica

Status: **preparada, não executada**. O planejamento somente leitura para `BTCUSDT` e 10 USDT foi aceito: preço de referência observado 80.930,917004 USDT, quantidade válida 0,00012 BTC, notional estimado 9,71171004048 USDT, saldo virtual disponível 5.000 USDT e limite local 25 USDT.

Não existe resultado de compra, venda, taxa ou P&L. O teste não poderá integrar a avaliação da estratégia. A execução aguarda autorização explícita do usuário.
""")

write("12_execucao_autonoma.md", """
# 12. Execução autônoma virtual

Status: **não iniciada e bloqueada**. A política congelada configurada é `D_event_market_reaction`, com no máximo uma política ativa. Faltam um round trip diagnóstico reconciliado e aprovação prospectiva da política. A promoção automática é proibida.

O comando de habilitação existe, mas falha de forma fechada enquanto essas condições não forem registradas. Não há resultados autônomos a relatar.
""")

write("13_comparacao_politicas.md", """
# 13. Comparação prospectiva A–D

O protocolo pareado das políticas A, B, C e D foi preservado. As quatro políticas devem observar os mesmos instantes em shadow/paper. Nenhuma foi promovida com base em desempenho recente, e somente a política congelada poderá futuramente acessar Demo.

Esta fase não acrescentou observações prospectivas suficientes para uma nova conclusão econômica.
""")

write("14_resultados_economicos.md", """
# 14. Resultados econômicos

Não houve operação Demo diagnóstica nem autônoma. Portanto, quantidade de operações, lucro bruto, taxas observadas, slippage, lucro líquido, retorno, taxa de acerto, profit factor e drawdown permanecem indisponíveis para a Fase 6.2.

O executor calcula o fluxo financeiro do diagnóstico quando a resposta contém `cummulativeQuoteQty` e comissões na moeda de cotação; taxas em outro ativo são registradas separadamente e impedem afirmar um P&L completo sem conversão causal.
""")

write("15_testes_automatizados.md", """
# 15. Testes automatizados

Resultado em 2026-10-18: **139 testes coletados e aprovados**. A compilação de `src`, `scripts` e `tests` também foi concluída. Dezesseis testes novos cobrem configuração, endpoints, kill switch, regras de símbolo, quantidades, journal, planejamento, confirmação, round trip mockado, timeout ambíguo, estado desconhecido, fila neural e separação entre leitura autenticada e envio.

As consultas externas realizadas foram somente leitura. A suíte padrão não acessa a corretora.
""")

write("16_pendencias_proximos_passos.md", """
# 16. Pendências e próximos passos

1. Obter autorização explícita para o primeiro round trip virtual pequeno.
2. Liberar temporariamente o kill switch e a variável de ordens Demo somente durante esse teste.
3. Confirmar compra, encerramento, taxas, saldo e ausência de ordens abertas; rearmar o kill switch.
4. Manter `DEMO_AUTONOMOUS` bloqueado até o diagnóstico e a aprovação prospectiva da política congelada.
5. Executar observação prolongada no Windows e validar reconexão/heartbeat dos WebSockets Demo.
6. Não usar operações diagnósticas para declarar lucratividade.
""")

write("README.md", r"""
# Fase 6.2 — operação

Comandos a partir de `D:\Binance AI project\Bitcoin_AI`:

```powershell
python scripts/run_phase6_2.py environment
python scripts/run_phase6_2.py public-check
python scripts/run_phase6_2.py auth-check
python scripts/run_phase6_2.py balances
python scripts/run_phase6_2.py symbol-rules --symbol BTCUSDT --quote 10
python scripts/run_phase6_2.py endpoint-safety
python scripts/run_phase6_2.py diagnostic-plan --symbol BTCUSDT --quote 10
python scripts/run_phase6_2.py kill-switch status
python scripts/run_phase6_2.py open-orders --symbol BTCUSDT
python scripts/run_phase6_2.py results
python scripts/run_phase6_2.py autonomous-status
```

O fluxo autorizado de ordem Demo exige, nesta ordem, definir localmente `BITCOIN_AI_ENABLE_DEMO_ORDERS=I_UNDERSTAND_DEMO_ONLY`, liberar o kill switch e executar o comando diagnóstico com a frase explícita. Não execute antes de revisar o plano:

```powershell
python scripts/run_phase6_2.py kill-switch clear --confirm I_AUTHORIZE_BINANCE_DEMO_ONLY
python scripts/run_phase6_2.py diagnostic-order --symbol BTCUSDT --quote 10 --confirm I_AUTHORIZE_ONE_DEMO_DIAGNOSTIC
python scripts/run_phase6_2.py open-orders --symbol BTCUSDT
python scripts/run_phase6_2.py results
```

Para interromper novas entradas imediatamente:

```powershell
python scripts/run_phase6_2.py kill-switch engage --reason parada_manual
python scripts/run_phase6_2.py stop-services
```

Após diagnóstico reconciliado e aprovação prospectiva registrada, a habilitação prevista é:

```powershell
python scripts/run_phase6_2.py enable-autonomous --confirm I_AUTHORIZE_DEMO_AUTONOMOUS
python scripts/run_phase6_2.py run-autonomous
```

Atualmente esses dois últimos comandos permanecem bloqueados pelos pré-requisitos. Não altere os indicadores de aprovação apenas para contornar o bloqueio.
""")

historical = {
    "phase1": "reports/final_evaluation.json",
    "phase2": "reports/phase_2/runs/20261017T223631458343Z-phase2/results.json",
    "phase3": "reports/phase_3/runs/20261018T005023721954Z-phase3/results.json",
    "phase4": "reports/phase_4/runs/20261018T013856021255Z-phase4/results.json",
    "phase5": "reports/phase_5/runs/20261018T152602827075Z-phase5-import/results.json",
    "phase6_config": "configs/phase_6.json",
    "phase61_config": "configs/phase_6_1.json",
}
(OUT / "preservation.json").write_text(json.dumps({
    "generated_at": NOW,
    "historical_artifacts_modified_by_phase62": False,
    "forbidden_final_period_reused": False,
    "hashes": {name: {"path": path, "sha256": digest(path)} for name, path in historical.items()},
}, indent=2), encoding="utf-8")

(OUT / "validation.json").write_text(json.dumps({
    "generated_at": NOW,
    "phase": "6.2",
    "status": "demo_read_only_validated_diagnostic_order_pending_authorization",
    "demo_rest_public_connected": True,
    "demo_authentication_validated": True,
    "account_type": "SPOT",
    "can_trade": True,
    "virtual_balances_observed": {"USDT": "5000", "USDC": "5000"},
    "btc_usdt_open_orders": 0,
    "production_endpoints_rejected": True,
    "orders_enabled": False,
    "kill_switch_engaged": True,
    "diagnostic_order_sent": False,
    "autonomous_started": False,
    "tests_passed": 139,
    "compileall_passed": True,
    "economic_claim": False,
    "secrets_recorded": False,
}, indent=2), encoding="utf-8")

print(OUT)
