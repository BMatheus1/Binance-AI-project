# Especialistas, padrões e avaliação econômica

## Seleção apoiada pelos artefatos anteriores

O registry verifica os hashes dos quatro artefatos selecionados pela Fase 4. XGBoost de 1, 5 e 15 minutos e CatBoost de 30 minutos continuam disponíveis. A proposta operacional usa somente XGBoost BTC/5m; os outros horizontes são contexto, sem soma de probabilidades nem independência presumida. ETH e SOL são monitorados, sem transferência indevida de um modelo de BTC.

O inventário histórico da Fase 4 contém 78 artefatos; a auditoria atual também encontra artefatos posteriores. A Fase 2 não persistiu seus modelos. Os resultados científicos permanecem nos caminhos originais e são referenciados pelo inventário desta fase.

Na avaliação anterior, nenhuma variante Kronos melhorou log loss com intervalo diário inteiramente favorável contra os especialistas, e todos os cenários Spot ficaram negativos após custos. Os 500 passos de fine-tuning e suas métricas já existentes não foram repetidos ou inventados. Consulte `reports/phase_5/08_full_results.md`.

## Fusão e comparação temporal

O método operacional é **seleção do especialista previamente congelado**, sem pesos arbitrários. Não foi treinado stacking usando previsões in-sample, retornos da sessão atual ou o holdout consumido. Qwen3 não é um especialista de preço e sua confiança textual não entra como p_up.

`expert_comparison.json` recalcula accuracy, log loss, Brier, ECE e sensibilidade a custos para as quatro variantes Kronos versus o especialista congelado, nos mesmos 256 instantes por horizonte, nos horizontes 1/5/15/30. São comparações exploratórias, não uma nova seleção. A calibração probabilística herdada tampouco calibra a magnitude de retorno Spot.

Para promover fusão, são necessários: previsões OOF purgadas de todos os especialistas no desenvolvimento; treinamento do meta-modelo somente nesse bloco; calibração posterior separada; seleção de estratégia em outro bloco; avaliação final futura intocada e bootstrap por blocos/dias. Comparações devem ter as mesmas entradas executáveis e custos. `chronological_roles` implementa blocos disjuntos, purga pelo fim do rótulo e rejeição de julho–setembro/2026, inclusive rótulos que cruzem sua fronteira.

## Padrões objetivos em pesquisa

`pattern_hypotheses` requer 61 candles fechados contínuos e valores finitos. Retornos são logarítmicos. São descrições sem ajuste de limiares e sem autorização de compra:

| Hipótese | Definição registrada |
|---|---|
| Continuação | retorno 20m > 0 e retorno 5m > 0 |
| Pullback | retorno 20m > 0 e retorno 5m < 0 |
| Rompimento | fechamento acima da máxima dos 20 candles anteriores; razão de volume registrada, confirmação ainda não validada |
| Retorno à média | fechamento abaixo da média dos 20 candles anteriores; z-score registrado; não implica reversão futura |
| Expansão de volatilidade | desvio dos últimos 5 retornos acima do desvio de 60 |
| Aceleração | retorno dos últimos 5 minutos menos retorno dos 5 anteriores > 0 |
| Livro | (profundidade bid − profundidade ask) / soma > 0 |
| Agressão | indisponível até existir janela AggTrades sincronizada no contrato |
| Reação a eventos | indisponível até validação temporal do efeito incremental |

O contrato registra horizonte, features, disponibilidade, invalidação por novo candle/dados antigos, resultado OOS e risco-retorno desconhecidos. Nenhum padrão está promovido. Para promovê-lo, é preciso frequência, expectativa líquida, intervalo por blocos, ablação e avaliação futura; ausência de evidência não é preenchida com zero.

## Pequenas oscilações e custos

`executable_net` usa compra no ask e venda no bid. O spread já está nos preços e não é subtraído novamente. Calcula o custo da compra com taxa e a receita de saída após slippage e taxa. Custos desconhecidos deixam o líquido desconhecido. Um ganho bruto pequeno pode continuar negativo após custos; testes verificam isso sem arredondar a perda.

Na proposta operacional, o custo é a estimativa preexistente do AssetSelector, identificada como estimativa, não taxa real. Magnitude esperada, p(lucro líquido), razão risco-retorno e expectativa líquida permanecem desconhecidas. A categoria economicamente validada continua bloqueada. A exceção é a modalidade explicitamente experimental Demo congelada.

`planned_risk` registra 10 USDT, stop existente de 50 bps (0,05 USDT antes de custos), perda planejada acrescida dos custos estimados e prazo. Não são garantias contra gaps/slippage. A distância do stop não foi otimizada nesta avaliação; falta comprovação de sua viabilidade estatística.

## Saídas e ablações

`ExitExperiment` e `exit_candidate` permitem comparar stop inicial, alvo líquido, trailing/proteção do ganho, continuidade, reversão validada, deterioração de liquidez e extensão limitada a três minutos com líquido positivo. São funções de pesquisa testadas, **não habilitadas no executor congelado**. Não afastam o stop e não estendem perdas. Avaliar regras diferentes exige as mesmas entradas e caminhos bid/ask posteriores, com custos e sem observar o caminho para escolher a regra.

Sem notícias, o motor central mantém exatamente a mesma proposta: uma ablação funcional verifica isso. Ainda não existem previsões OOS pareadas para declarar contribuição incremental de notícias, microestrutura, regime ou timing. Tampouco há entradas suficientes com caminhos executáveis para uma comparação econômica de saídas adaptativas. Esses resultados estão explicitamente indisponíveis em `expert_comparison.json`, em vez de métricas artificiais.

Os retornos de `forecast_outcomes` são rótulos diagnósticos baseados em candles. Não equivalem a fills no instante real da decisão, nem a uma carteira executável com oportunidades sobrepostas. Resultados financeiros da Demo exigem as execuções efetivas, com taxas e resíduos.
