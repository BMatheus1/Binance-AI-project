# Fase 6.4.3 — experimento ativo Binance Spot Demo

O motor existente recebeu o modo `DEMO_ACTIVE_EXPERIMENTAL`. Nenhum modelo foi treinado, promovido ou substituído. A política histórica A/5m com limiar 0,60 continua preservada. O perfil novo está em `configs/phase_6_4_3.json`; sua versão e hash são congelados no SQLite ao preparar cada sessão.

## Regras do novo experimento

- **AI_SIGNAL:** probabilidade direcional `up` de cinco minutos >= 0,53, maior que `down`, e momentum real dos últimos cinco candles positivo. Essa probabilidade não significa chance de lucro líquido. Os demais horizontes, padrões causais e notícias continuam no contexto auditável, sem promoção de contribuição não validada. Qwen3 é opcional.
- **EXPLORATORY_PROBE:** exige confirmação específica permitindo exploração; pelo menos 180 segundos desde a autorização ou última saída; no máximo duas sondagens. Não são entradas aleatórias e não representam previsão de vantagem econômica. O contexto e os motivos são registrados.
- Ambas exigem previsão real disponível, integridade temporal, dados completos, livro atualizado, spread <= 3 bps, profundidade >= 10.000 USDT por lado, volatilidade <= 30 bps, reconciliação saudável e autorização do processo atual.
- BTCUSDT Spot Demo, alvo máximo 10 USDT por compra, exposição acumulada incluindo residuais <= 10 USDT para dimensionamento, uma posição, até seis entradas e 60 minutos. Lote, taxas e residual podem reduzir o valor da próxima compra. Se não houver lote de entrada e saída válido, não compra.
- Perda **planejada** <= 0,10 USDT por operação e reserva acumulada <= 0,50 USDT por sessão, incluindo teto de taxas e reserva de slippage. Perdas realizadas acumuladas também bloqueiam novas entradas ao alcançar 0,50 USDT. Não se compensam perdas com ganhos para liberar esse limite. Há ainda os limites diários preexistentes. Stops, ordens a mercado e indisponibilidade não garantem perda máxima realizada.
- Cooldown de dois minutos; stop de preço de 50 bps; saída por perda líquida estimada de 0,10 USDT, take profit líquido estimado, trailing, deterioração do mercado, novo sinal contrário, kill switch ou prazo. Prazo planejado de cinco minutos, absoluto de oito minutos, sem extensão na versão inicial. Saídas antecipadas são permitidas.
- Objetivo adaptativo congelado pela regra: `min(0,04; max(0,02; valor_entrada * volatilidade_na_entrada_bps / 10000))` USDT. Trailing ativa com pico líquido estimado >= 0,015 USDT e devolução >= 0,01 USDT. São regras experimentais de saída; não garantem capturar o máximo.

## Execução e contabilidade

O mesmo adaptador Demo, diário de intenções e gerenciador de posições executam as ordens. Uma intenção é persistida antes do envio. Timeout consulta o identificador original, sem repetir a compra. Uma execução parcial cancela a quantidade restante e consulta seu estado; fills são recuperados por `orderId` quando necessário. Histórico incompleto, cancelamento incerto e saída parcial bloqueiam novas entradas para reconciliação auditada. Quantidades, respostas e taxas conhecidas permanecem persistidas.

Após reinício, ordens terminais confirmadas podem recompor o inventário de entrada ou confirmar uma saída concluída, sem reenviar a compra. A autorização é invalidada e o kill switch permanece ativo; somente o gerenciamento de saída continua. Ordens desconhecidas, autenticação inválida e divergências de saldo não viram autorização automática.

O gerenciamento usa thread própria e continua sem Qwen3/notícias. Se REST estiver indisponível, não há garantia de executar stop no horário; a falha e a recuperação ficam registradas. A sessão nunca é retomada automaticamente.

O P/L realizado usa o custo proporcional do BTC efetivamente vendido e suas taxas. BTC não vendável por lote mínimo fica em `demo_residuals`, com custo separado, sem ser creditado como lucro realizado; o fluxo de caixa integral aparece separadamente. Taxa em ativo sem conversão confiável deixa o resultado líquido desconhecido. Marca aberta usa bid executável menos taxas estimadas e slippage; o dashboard invalida marcas com mais de 15 segundos. Custos estimados e efetivos são distintos.

As explorações ficam fora das métricas de desempenho das estratégias no dashboard. Resultados permanecem agrupados por sessão e origem. Diagnósticos antigos continuam separados. A avaliação econômica prospectiva não é usada para ajustar este perfil durante a sessão.

## Procedimento exato no PowerShell

```powershell
cd "D:\Binance AI project\Bitcoin_AI"
.\scripts\start_dashboard.ps1 -OpenBrowser
python .\scripts\run_phase6_4.py health
python .\scripts\run_phase6_4.py reconciliation-check
python .\scripts\audit_phase6_4_3.py
```

Se os serviços já estiverem em execução, não execute `start_dashboard.ps1` novamente. Após atualização de código, use `stop_dashboard.ps1` e depois `start_dashboard.ps1`; o encerramento preserva o banco da observação e recusa matar o monitor se houver posição não encerrada.

`reconciliation-check` e o preflight exigem kill switch ativo. Para bloquear novas compras: `python .\scripts\run_phase6_4.py stop-session`. Uma posição existente continua sob responsabilidade do monitor de saída. Nunca use o preflight para autorizar ordens.

Para preparar o perfil de 60 minutos **com até duas explorações**:

```powershell
python .\scripts\run_phase6_4.py prepare-session --mode DEMO_ACTIVE_EXPERIMENTAL --allow-probes
```

Preparar não autoriza nem envia ordens. Revise o ID, perfil e limites retornados. Somente quando decidir autorizar a sessão específica, substitua `ID_DA_SESSAO` pelo ID retornado:

```powershell
python .\scripts\run_phase6_4.py authorize-session --session-id ID_DA_SESSAO --confirm I_AUTHORIZE_60_MIN_10_USDT_DEMO_ACTIVE_WITH_PROBES
```

Alternativa **somente sinais da IA**, sem explorações:

```powershell
python .\scripts\run_phase6_4.py prepare-session --mode DEMO_ACTIVE_EXPERIMENTAL
python .\scripts\run_phase6_4.py authorize-session --session-id ID_DA_SESSAO --confirm I_AUTHORIZE_60_MIN_10_USDT_DEMO_ACTIVE_AI_ONLY
```

Não execute as duas alternativas para a mesma sessão. A confirmação anterior da Fase 6.4 não autoriza este novo perfil. Reinício exige novo preparo e nova confirmação.

Após autorizar, acompanhe:

```powershell
python .\scripts\run_phase6_4.py health
python .\scripts\run_phase6_4.py positions
python .\scripts\run_phase6_4.py results
python .\scripts\run_phase6_4.py observation-status
```

Abra [Robô Autônomo](http://127.0.0.1:3000/autonomous). A mesma preparação e autorização estão disponíveis na página, com cookie local, Origin, CSRF e confirmação digitada. Abrir a página não inicia negociação. O botão Encerrar sessão bloqueia compras e mantém a gestão de uma posição aberta.

Para verificar o primeiro ciclo, procure uma posição `OPEN` com fills BUY reais, seguida de `CLOSED` com fills SELL, `entry_category`, taxas, motivo e `net_quote` conhecido ou motivo de indisponibilidade. Um teste com mocks ou um HTTP 200 não comprova um ciclo Demo. A primeira compra em até dez minutos é um objetivo condicionado aos gates; bloqueios legítimos prevalecem.

```powershell
python .\scripts\run_phase6_4.py stop-session
.\scripts\stop_dashboard.ps1
```

## Evidências e pendências

- `tests.xml`: resultado da suíte automatizada, sem envio de ordens.
- `preservation.json`: comparação dos 257 arquivos protegidos com o manifesto anterior, incluindo modelos/configurações/relatórios e registro do holdout.
- `preflight.json`: leituras reais da Demo, taxas, filtros, reconciliação e observação; não constitui autorização e deve ser atualizado antes da sessão.
- SQLite e ledger existentes em `runtime/phase_6_4` mantêm o estado auditável; avaliações e decisões centrais permanecem em `runtime/phase_6_1`.

Cada sessão exige autorização específica após o desenvolvimento. A primeira sessão autorizada e seus fills reais estão documentados na atualização abaixo. O protocolo de 24 horas continua no banco anterior, com falhas e lacunas preservadas; tempo transcorrido e estabilidade são resultados diferentes. Não há comprovação de lucratividade.

Referências oficiais: [hosts Binance Demo](https://developers.binance.com/en/docs/products/spot/demo-mode/general-info) e [comissões](https://developers.binance.com/en/docs/products/spot/faqs/commission_faq). Não existe fallback de negociação para produção.

## Verificação de 19/10/2026

Suíte final: **244 testes aprovados**, sem falhas ou testes pulados (`tests.xml`). Build do frontend e verificação TypeScript aprovadas. Dashboard e API responderam HTTP 200; o controle de autorização rejeitou chamadas sem cookie (401) e sem CSRF (403), sem alterar a sessão.

Pré-voo autenticado somente leitura: conta Demo com `canTrade=true`, zero ordens abertas, zero intenções desconhecidas, taxa estimada conservadora de 0,10% por lado. A ordem de aproximadamente 10 USDT e sua quantidade de saída passaram pelos filtros no preço observado. Esses dados são instantâneos; os filtros são consultados novamente antes de cada ordem.

Sessão preparada: `demo-20261019T221154-2da6a152`, processo `28104`, boot `c7fe86b8970e43a7bea8dcca166d0866`, hash de perfil `2f276a9f23aa1bc78e7475ad282ad381f5ce0d29fd203e0c4cd887659a961486`. Estado registrado: OBSERVE, kill switch ativo, sem posição aberta. Reiniciar novamente invalida esse vínculo.

O processo atualizado registrou decisões centrais para essa sessão às 22:13:08, 22:14:07, 22:15:05 e 22:16:02 UTC, entre outras. Foram recusadas por falta de autorização e pela janela de exploração ainda não iniciada. Isso demonstra avaliação real contínua; não é um teste de execução de ordens.

O diário continuou com quatro ordens antigas `RECONCILED`; a mais recente havia sido criada às 19:48:04 UTC, antes deste desenvolvimento. Não houve nova ordem nesta fase. A comparação dos 257 arquivos protegidos não encontrou alterações. A observação preservada tinha aproximadamente **8,47 horas** na captura, portanto o mínimo de 24 horas não estava concluído. Consulte `runtime_evidence.json`, `preflight.json`, `preservation.json` e `validation.json`.

Na captura anterior à autorização, o teste real de ponta a ponta ainda estava pendente. Não havia alegação de lucro ou de estabilidade operacional por 24 horas concluída.

## Sessão autorizada: primeiro ciclo real confirmado

Após a confirmação humana **“Autorizo a sessão Demo descrita”**, a sessão `demo-20261019T221154-2da6a152` foi autorizada às 19:32:38 de São Paulo, com expiração às **20:32:38 de 19/10/2026**. O processo e os parâmetros congelados foram mantidos. As ordens abaixo foram enviadas pelo motor existente, sem disparo manual de compra ou venda pelo auditor.

| Registro | Resultado confirmado na Binance Demo |
| --- | --- |
| Origem | `EXPLORATORY_PROBE`, fora das métricas preditivas |
| Compra | Ordem `74984954594`, `FILLED` |
| Quantidade comprada bruta | 0,00012000 BTC |
| Preço médio de compra | 82.080,01 USDT/BTC |
| Valor efetivo da compra | 9,84960120 USDT |
| Taxa de entrada | 0,00000012 BTC |
| Quantidade líquida adquirida | 0,00011988 BTC |
| Venda automática | Ordem `74986113039`, `FILLED` |
| Quantidade vendida | 0,00011000 BTC |
| Preço médio de venda | 82.086,00 USDT/BTC |
| Valor bruto da venda | 9,02946000 USDT |
| Taxa de saída | 0,00902946 USDT |
| Motivo da saída | `planned_horizon`, prazo de cinco minutos |
| P/L realizado da parcela vendida | **−0,01740839893893894 USDT** |
| Residual BTC abaixo do lote vendável | 0,00000988 BTC |
| Fluxo de caixa USDT do ciclo | −0,82917066 USDT, com BTC residual retido |

O fluxo de caixa não equivale ao prejuízo realizado: parte do custo permanece atribuída ao BTC residual, que continua sendo inventário e não foi contabilizado como lucro. A operação encerrou com perda realizada apesar de o preço de venda ser ligeiramente superior ao de compra; taxas superaram esse movimento.

O primeiro envio aconteceu aproximadamente três minutos e meio após a autorização, dentro do objetivo operacional de dez minutos. A posição foi registrada aberta às 19:36:08 e encerrada às 19:41:14, horário de São Paulo. A verificação independente por consultas de ordem e trades ocorreu às 19:41:46. Foram encontrados **zero ordens abertas e zero intenções pendentes**; a reconciliação do motor permaneceu saudável.

O dashboard confirmou a posição encerrada, o mesmo resultado líquido e uma exploração contabilizada. As métricas das estratégias preditivas continuaram com zero operações, sem incluir a sondagem. Evidências: `authorized_session.json`, `live_entry.json`, `pos-d1a7dae45aa447bd9fb9bc7ef3c87d19-exchange_verified.json`, `live_dashboard_open_position.json`, `live_cycle_result.json` e o monitor JSONL da sessão. `validation.json` registra agora o ciclo Demo efetivamente confirmado.

Para conferir novamente sem enviar ordens:

```powershell
python .\scripts\verify_active_demo_cycle.py --position-id pos-d1a7dae45aa447bd9fb9bc7ef3c87d19
python .\scripts\run_phase6_4.py positions
python .\scripts\run_phase6_4.py results
```

A sessão permanece autorizada até sua expiração ou um bloqueio de segurança; não foi encerrada automaticamente pelo auditor após a primeira operação. A observação de 24 horas e a validação econômica continuam independentes e ainda não foram declaradas concluídas. Nenhuma ordem de produção foi enviada.
