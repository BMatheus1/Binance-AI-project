# Correção urgente da reconciliação — Fase 6.4

## Causa e reprodução

A CLI da Fase 6.4 carregava `.env` antes de autorizar, mas `run_phase6_1.py serve` não o carregava. O processo contínuo estava sem `BINANCE_DEMO_API_KEY`, `BINANCE_DEMO_API_SECRET` e sem o flag de habilitação Demo. Depois da autorização externa, a primeira consulta assinada periódica falhava antes de chegar à Binance:

```text
SupervisedDemoEngine._reconcile()
  -> BinanceDemoBroker.open_orders("BTCUSDT")
  -> BinanceDemoBroker._call(..., signed=True)
  -> RuntimeError: Binance Demo orders are disabled; credentials are incomplete
```

O evento histórico guardou apenas `reconciliation_failed:RuntimeError`; portanto, não existe traceback histórico completo recuperável. A cadeia acima foi reproduzida em um processo isolado sem carregar `.env`. Os frames sanitizados estão em `root_cause_reproduction.json`. A auditoria preservou os 41 eventos de falha da sessão anterior, duas sessões encerradas, zero entradas e zero posições experimentais. As duas intenções do diagnóstico de 18/10 continuam `RECONCILED`.

## Correções

- O serviço contínuo carrega `.env` de forma silenciosa antes de construir o motor. Nenhuma credencial entra em relatórios ou logs.
- Reconciliação autenticada passa a ocorrer em OBSERVE, antes da preparação de sessão, com sincronização do relógio, consulta de saldo/permissão e ordens abertas.
- Preparar e autorizar exigem evidência recente de reconciliação saudável do processo atual. A autorização é revalidada após os checks REST.
- Toda falha de reconciliação invalida a autorização, rearma o kill switch e bloqueia entradas. A recuperação de transporte volta a OBSERVE; ela nunca reautoriza a sessão.
- Timeout/conexão transitória em consultas de leitura usa espera progressiva de 5, 15, 30 e 60 segundos. O scheduler respeita a espera e não acumula chamadas.
- Credenciais ausentes, assinatura/permissão inválida, TLS não confiável, estado desconhecido, ordens pendentes e divergência de saldo exigem intervenção. São registrados categoria, códigos HTTP/API e frames sanitizados.
- Posição `ENTRY_SUBMITTING`, `EXIT_SUBMITTING` ou `RECOVERY_REQUIRED` nunca é reenviada automaticamente. Seu estado persistido é verificado em cada ciclo, inclusive após reinício.
- O motor usa executor dedicado e ciclos sem sobreposição. A consulta a inferências não é necessária para aplicar kill switch ou prazo de saída. O pool de notícias/Qwen pode estar ocupado sem enfileirar o monitor de posições atrás dele.
- O WebSocket tem limite de inatividade, reconecta em falha de handshake/stream, invalida livro/cotações ao desconectar e registra códigos de fechamento quando disponíveis. Novas entradas exigem stream vivo e livro sincronizado.

Os modelos, limiares, política A, BTCUSDT, horizonte de 5 minutos e teto de 10 USDT foram preservados. O tratamento de ordens desconhecidas respeita a distinção entre falha de transporte e estado de execução desconhecido descrita na [documentação oficial de erros Binance](https://github.com/binance/binance-spot-api-docs/blob/master/errors.md).

## Conectividade e observação preservada

As 225 reconexões iniciais permanecem no histórico da observação. Elas ocorreram no período de rede isolada previamente identificado. A auditoria posterior também encontrou dez desconexões reais no processo anterior: BTC=2, ETH=4, SOL=4, com `ConnectionClosedError` e lacunas de sequência registradas. Os registros antigos não possuem código de fechamento suficiente para atribuir uma causa de rede específica a cada queda; esse detalhe agora é coletado.

A última hora da auditoria anterior ao reinício teve 100% de disponibilidade amostrada da API Demo. O snapshot após a correção mostrou 99,1% de disponibilidade por estado do worker e 100% da API na janela de 60 minutos, com zero reconexões no novo processo. São percentuais por amostra; estado `analyzing` não significa que uma nova previsão já terminou. O Qwen em CPU pode aumentar a latência de inferência, e avaliações antigas continuam sujeitas ao bloqueio por validade temporal.

O protocolo continua com o mesmo ID `obs-20261019T134818-5f0db660`, iniciado às 13:48:18 UTC de 19/10/2026. O tempo mínimo de 24 horas ainda não foi concluído. Reinícios, falhas, gaps e dados anteriores permanecem auditáveis; as janelas recentes complementam os totais integrais.

## Evidências e validação

- `audit_20261019T191846Z.json`: auditoria anterior ao reinício e localização dos backups consistentes dos quatro SQLite.
- `root_cause_reproduction.json`: reprodução isolada do erro de configuração, sem requisição assinada enviada.
- `reconciliation_check.json`: consulta independente somente leitura, `healthy=true`, zero intenções pendentes e zero ordens abertas.
- `healthy_runtime_snapshot.json`: reconciliação saudável no motor contínuo, credenciais presentes sem valores, OBSERVE, kill switch ativo, zero posições e autorização encerrada; endpoint do dashboard HTTP 200.
- `final_runtime_evidence.json`: estado da versão final às 19:26:32 UTC, sem sessão/posição, diário ainda com apenas as duas ordens diagnósticas antigas reconciliadas; conexão disponível e 186 testes aprovados.
- Suíte completa: 186 testes aprovados. Build do dashboard e compileall aprovados.
- Testes incluem recuperação REST com backoff, invalidação de autorização, erro permanente de autenticação/permissão, TLS, ordem desconhecida, saldo divergente, reinício, capacidade independente para posições e reconexão WebSocket após erro/timeout.

Nenhuma ordem foi enviada durante esta correção. O adaptador permanece restrito ao host Demo por allowlist, sem fallback para produção. Nenhuma sessão nova foi preparada ou autorizada contra a conta nesta correção.

## Comandos

Os serviços foram deixados ativos em OBSERVE. Para verificar:

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
Get-Content .\runtime\phase_6_4\engine.json
python .\scripts\run_phase6_2.py kill-switch status
python .\scripts\run_phase6_4.py reconciliation-check
python .\scripts\run_phase6_4.py observation-status
```

O comando `reconciliation-check` exige kill switch ativo e executa apenas leituras. Confira `reconciliation.state=healthy`, `last_error=null`, zero ordens/intenções pendentes e a disponibilidade atual em `http://127.0.0.1:3000/autonomous`.

Se for necessário reiniciar os serviços, mantendo a observação existente:

```powershell
.\scripts\stop_dashboard.ps1
.\scripts\start_dashboard.ps1
```

O startup rearma o kill switch. Aguarde a primeira reconciliação saudável antes de preparar outra sessão.

Somente quando o usuário decidir autorizar novas operações virtuais:

```powershell
$demoSession = python .\scripts\run_phase6_4.py prepare-session | ConvertFrom-Json
python .\scripts\run_phase6_4.py authorize-session --session-id $demoSession.session_id --confirm I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL
```

Essa autorização permite ordens exclusivamente Demo quando todos os controles e a política congelada aprovarem. Pode haver zero operações se os sinais permanecerem inelegíveis.

Para interromper novas entradas:

```powershell
python .\scripts\run_phase6_4.py stop-session
```
