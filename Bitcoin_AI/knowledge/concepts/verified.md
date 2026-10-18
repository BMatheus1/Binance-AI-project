# Referências verificadas e formalizações próprias

**Atualização do estudo em 17/10/2026:** [dossiês aprofundados e cobertura](../study/README.md). OCR concluído nas 528 páginas de Brooks/Nison; passagens analisadas em 324 páginas dos quatro arquivos, com inspeções visuais registradas separadamente. A revisão integral permanece pendente. Aronson está interrompido no capítulo 6 e Brooks é suplemento de audiobook. As notas abaixo documentam a etapa inicial; suas menções a OCR não executado descrevem aquele estado histórico, substituído pelo registro atual. As novas propostas estão em `knowledge/study/hypotheses.json` e não foram incorporadas aos modelos.

Páginas abaixo são posições físicas do PDF, contadas a partir de1. Não são inferidas pelo nome do arquivo. Não houve leitura integral interpretativa. O índice automático é apenas um mapa de localização, não uma interpretação dos livros. Nenhum conceito bibliográfico constitui evidência de lucro.

## Adam Grimes

**The Art & Science of Technical Analysis: Market Structure, Price Action & Trading Strategies**, Adam Grimes, Wiley,2012. Título/autor confirmados na página PDF3 e copyright na4; número da edição não confirmado. Capítulo1, páginas PDF30–32 (impressas14–16), lidas com extração textual.

Conceitos: movimentos direcionais alternam com períodos de equilíbrio; estrutura se descreve por pontos e movimentos passados. Pivôs definidos também pelo candle seguinte só são reconhecíveis após essa confirmação. Usar um pivô retrospectivo como se fosse conhecido antes seria vazamento.

Formalização própria: `momentum_20=close[t]/close[t-20]-1`; `higher_high` e `higher_low` comparam somente candles já fechados. Não implementamos pivôs futuros. Regime de tendência usa momentum comparado à volatilidade histórica. Hipótese H-TENDÊNCIA: variáveis de tendência reduzem log loss fora da amostra em relação a preços/retornos. Avaliação: ablação de categoria, validação cronológica, estabilidade mensal e dois folds anteriores. Limitação: esta operacionalização não reproduz integralmente o método do autor.

## Al Brooks

**Reading Price Charts Bar by Bar**, suplemento do audiobook, Al Brooks, copyright2009. Natureza do arquivo confirmada na página PDF2. O material fornecido tem212 páginas; não é o livro textual integral. Página PDF16 (impressa15), figura1.5, inspecionada visualmente: mostra barras de reversão dentro de contexto lateral. A extração textual dessa página recupera principalmente o aviso de direitos, não o gráfico.

Formalização própria: proporções do corpo/pavios e posição do fechamento, condicionadas a regime observável. Hipótese H-PRICE ACTION: geometria do candle acrescenta informação além dos retornos. As regras dependem apenas de O,H,L,C atuais, disponíveis no fechamento. Avaliação: regressão com/sem o grupo e métricas por regime. A legenda e o exemplo não justificam prever uma direção específica automaticamente; nenhum sinal do gráfico foi copiado para o dataset.

## David R. Aronson

**Evidence-Based Technical Analysis: Applying the Scientific Method and Statistical Inference to Trading Signals** (arquivo em tradução automática), David R.Aronson, Wiley, copyright2007 conforme PDF2. Edição específica não confirmada. A marca de tradução automática aparece no arquivo. Capítulo1, página PDF17, leitura textual; introdução PDF15 também lida.

Conceito: regras objetivas devem ser suficientemente precisas para permitir avaliação repetível; testar muitas regras traz risco de viés de seleção. Formalização metodológica própria: fórmulas versionadas, separação treino/calibração/validação/teste, purga dos rótulos e comparações com frequência histórica. Hipótese H-VALIDAÇÃO: vantagem preditiva aparente sobrevive a períodos futuros independentes. A avaliação atual não implementa os testes específicos do estudo do autor nem corrige a multiplicidade de todos os experimentos; conclusões permanecem exploratórias.

## Steve Nison

**Japanese Candlestick Charting Techniques**, Steve Nison. Capa PDF1 informa segunda edição, mas a correspondência completa entre capa, conteúdo e edição não foi verificada; há páginas de sumário fora da sequência numérica. Todas as316 páginas estão sem camada textual útil. Foram inspecionadas visualmente capa, páginas iniciais/sumário e páginas PDF35–37. OCR integral não executado.

Capítulo3, páginas PDF36–37 (impressas23–24): construção de candles, corpo entre abertura e fechamento, sombras até os extremos e doji como abertura/fechamento próximos. Figuras3.3–3.7 inspecionadas visualmente.

Formalização própria: `body_fraction=(C-O)/(H-L)`; `lower_wick=(min(O,C)-L)/(H-L)`; `upper_wick=(H-max(O,C))/(H-L)`. Em amplitude zero, as três valem0. São descritores; não constituem prova de rejeição ou fluxo de ordens. Hipótese exploratória: o grupo ajuda na previsão direcional quando combinado ao contexto. Não foram atribuídas regras numéricas de martelo/doji ao autor; limiares específicos exigiriam pesquisa adicional.

## Hipóteses adicionais de engenharia

H-PREÇO: retornos passados contêm informação incremental em relação à frequência de classes. H-VOLATILIDADE: regime de amplitude/volatilidade muda o desempenho condicional. H-VOLUME: intensidade e proporção agressora acrescentam informação. H-TEMPO: sazonalidade UTC altera as probabilidades. São propostas próprias desta implementação, sem atribuição bibliográfica não verificada.

Cada hipótese começa **implementada/em avaliação**, não validada. Resultados de ablação são registrados em `knowledge/hypotheses/assessments.json`. Uma melhoria isolada não basta para promoção de status. Referências e hipóteses não são alimentadas como texto nos modelos: o aprendizado usa somente features numéricas derivadas de dados reais.
