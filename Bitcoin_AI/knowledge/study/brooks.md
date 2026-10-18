# Al Brooks — leitura sequencial e limites do suplemento

Estudo de 17/10/2026. Referências são páginas físicas do PDF. **O arquivo fornecido é um suplemento de audiobook**, confirmado na página 2: figuras, legendas, glossário e localização de trechos do áudio. Não contém a exposição integral do livro. O áudio não foi fornecido nem ouvido. OCR foi concluído nas 212 páginas; isso não significa que todos os gráficos tenham sido examinados individualmente.

## O conteúdo que pode ser estabelecido

A contribuição central é ler a barra como parte de uma sequência, condicionada ao estado recente do mercado. Uma barra aparentemente de reversão pode ser apenas pausa de uma tendência. Um rompimento frustrado pode preparar uma entrada na direção oposta; se essa tentativa também falhar, a direção original pode reaparecer. Cada etapa requer informação nova. O título final do padrão não pode ser atribuído à sua primeira barra.

A média usada nos gráficos é EMA de 20 barras (glossário, PDF 204). “High 1” e “High 2” não significam simplesmente primeira e segunda máximas de uma sessão. São tentativas de retomada durante uma correção em mercado ascendente ou lateral; uma tentativa adicional exige uma interrupção intermediária da sequência. Low 1/Low 2 são os correspondentes na direção contrária (PDF 204–205).

## Mapa dos 15 capítulos representados

Este mapa usa o sumário, legendas recuperadas e o glossário; a coluna de aplicação é interpretação de pesquisa. Uma legenda não substitui a discussão oral ausente.

| Capítulo | Material disponível e lição | Aplicação/ressalva | Páginas PDF |
|---|---|---|---|
| 1 — price action | Dojis, barras de tendência e reversão, inside/outside bars, segunda entrada | Geometria depende do contexto; uma barra forte também pode marcar exaustão | 12–33 |
| 2 — linhas | Linhas de tendência, canais, microlinhas e testes | Congelar os pontos usados antes da decisão; não redesenhar até obter um sinal vencedor | 34–44 |
| 3 — tendências | Tendência desde a abertura, spike/channel, faixas inclinadas, shrinking stairs | Separar direção, força e sobreposição; rótulo diário só fica conhecido depois | 45–57 |
| 4 — correções | EMA, duas pernas, contagem H/L, M2B/M2S, wedges | Contagem exige estado e política de reinício explícita | 58–77 |
| 5 — faixas | Tight trading range e barb wire; grandes movimentos em ambos os sentidos | Filtro de abstenção é candidato; lateralidade não define sozinha reversão | 78–90 |
| 6 — rompimentos | Entrada antecipada, pullback e teste do nível | Diferenciar detectar, executar e ganhar; testar ordens não executadas também | 91–95 |
| 7 — alvos | Measured moves e extremos anteriores | Não estimar o ponto de partida com extremos futuros | 96–98 |
| 8 — reversões | Quebra de linha anterior, teste de extremo, relação entre escalas | Verificar se a confirmação agrega valor suficiente para compensar o atraso | 99–118 |
| 9 — falhas | Armadilhas, falha da falha, wedges e cinco ticks | As constantes de ticks pertencem aos instrumentos dos exemplos | 119–138 |
| 10 — execução | Relação 1m/5m, entradas stop/limit, alvos e proteção | OHLC não revela fila de execução nem sequência intrabar | 139–157 |
| 11 — abertura | Gaps, primeira barra, primeira hora e contexto do dia anterior | BTC exige definição própria de sessões; não copiar a abertura da bolsa | 158–177 |
| 12 — exemplos intradiários | Juros, câmbio, soja, petróleo e E-mini | Diversidade de desenhos não comprova transferência estatística para BTC | 178–180 |
| 13 — escalas maiores | Diário, semanal, mensal e volume | Semelhança visual não significa parâmetros ou taxas iguais | 181–185 |
| 14 — opções | Exemplos de reversão com opções | Exige preços de opções e modelagem próprios; fora do atual dataset | 186–188 |
| 15 — seleção de operações | Casos preferidos e entradas a evitar | Inclui falhas ilustrativas; ainda não é amostra aleatória de oportunidades | 189–201 |

## Definições que precisam permanecer separadas

**Setup, barra de sinal e barra de entrada.** O setup contém uma ou mais barras. A barra de sinal é a última antes da barra em que a ordem executa. Para código causal, convém chamar inicialmente de *candidata a barra de sinal*: pode nunca ocorrer execução. Não rotular apenas os setups que mais tarde foram preenchidos sem também registrar os não executados (PDF 206–207).

**Inside bar versus harami.** A definição de inside bar usa máxima e mínima, com igualdade admitida; a de harami em Nison usa o corpo. Um evento não substitui o outro. As sequências `ii`, `iii` e `ioi` são relações entre barras; não equivalem a “três candles pequenos” (PDF 205).

**Doji.** O glossário admite corpo pequeno ou inexistente e dá exemplos em ticks próprios de cada escala. Isso é diferente de exigir igualdade exata entre abertura e fechamento. O mesmo limiar absoluto não deve ser usado em todas as épocas de BTC (PDF 203).

**Barb wire.** Três ou mais barras lateralizadas com bastante sobreposição e pelo menos um doji. O adjetivo “bastante” permanece qualitativo. Nossa adaptação precisa definir razão de sobreposição e amplitude relativa antes de observar os resultados (PDF 202 e figura 5.5, PDF 82).

**Swing.** A definição do glossário compara uma barra com a anterior e a posterior. Portanto, esse pivô só fica confirmado depois da barra posterior. O algoritmo deve guardar `pivot_time` e `available_at` separadamente. Pintar o pivô na data antiga é aceitável para visualização histórica, mas não para fingir que ele já estava disponível ao modelo (PDF 207).

**Falha.** O glossário a relaciona ao stop ou à ausência do lucro pretendido antes de reversão. É uma definição dependente do plano de negociação, não apenas do desenho. A taxa de “falhas” muda quando alvo, stop, prazo ou custos mudam (PDF 204).

## Exercícios visuais realizados

**Contagem de barras — figura 4.16, PDF 69, impressa 68.** O gráfico do E-mini mostra H1/H2 e L1/L2 em vários pontos, inclusive correções dentro de um movimento ascendente. A anotação demonstra que as contagens são locais, e não números globais da sessão. Uma reprodução mecânica precisa declarar quando a correção começa, quando uma tentativa fracassa e quando a contagem expira. O gráfico sozinho não resolve todas essas convenções.

**Barb wire — figura 5.5, PDF 82, impressa 81.** Há uma região de barras sobrepostas antes da expansão posterior. O resultado à direita não prova que o rompimento era previsível. O exercício útil é ocultar essa região futura e perguntar se a condição de sobreposição já era detectável e se ela deveria impedir entradas de continuação por um período definido.

**Reteste de rompimento — figura 6.4, PDF 93, impressa 92.** No gráfico de LEH, os pontos 1 e 2 aparecem em uma queda com média descendente; depois há uma região mais lateral e novo teste. Isso sugere estudar separadamente retestes durante impulso e depois de equilíbrio. A legenda qualifica o padrão como confiável, mas não fornece denominador, intervalo de confiança nem custo.

**Falha da falha — figura 9.29, PDF 136, impressa 135.** A sequência anotada no gráfico de RIMM mostra tentativas ao redor de uma estrutura descendente e uma expansão posterior para cima. O conteúdo observável é a sucessão de violações e recuperações. Para o modelo, essa sequência deve virar uma máquina de estados; o nome “falha da falha” não pode servir de explicação retrospectiva ilimitada.

**1m dentro de 5m — figura 10.3, PDF 141, impressa 140.** O exemplo de AAPL alinha os pontos 1–3 de um gráfico de 1m com o contexto descendente no painel de 5m. Adaptar exige usar somente o último candle de 5m encerrado. O painel histórico completo não demonstra o estado conhecido no meio de cada candle maior.

**Preço de sinal versus preço executável — figura 10.16, PDF 152, impressa 151.** As marcações A/B/C e a legenda sobre seis ticks para um alvo de quatro ilustram que movimento após o sinal e ganho realizado são grandezas diferentes. Não interpretar os dois ticks adicionais como tabela universal de comissão: há preço de entrada, margem de execução e hipótese de preenchimento. Não transplantar os ticks do E-mini para BTC.

**Entrada a evitar — figuras 15.19/15.20, PDF 200, impressa 199.** O painel inicial sugere um fundo em cunha numa queda forte. O painel ampliado mostra que a queda prosseguiu. Essa justaposição é mais instrutiva que um vencedor perfeito: o sinal local não dominou o contexto. Não inferir uma probabilidade a partir desse único fracasso.

## Formalização possível de H2, sem fingir equivalência integral

Uma versão inicial pode usar uma máquina de estados: tendência ascendente observada → correção detectada → primeira barra com máxima acima da anterior → nova interrupção por máxima menor → segunda tentativa. O glossário permite variantes; portanto, qualquer implementação exata será uma **variante de pesquisa**, não “o algoritmo oficial de Brooks”.

A entrada pode ser estudada de duas formas independentes: sinal após fechamento com execução na abertura seguinte; ou ordem stop previamente posicionada acima da barra de sinal. A segunda exige resolver candles que atravessam entrada e stop na mesma barra. Sem dados intrabar, marcar ambiguidade ou usar avaliação conservadora predefinida. Não aproveitar a mínima da barra e a máxima da mesma barra como se sua ordem fosse conhecida.

Para comparar primeira e segunda tentativas, agrupar eventos por correção. Caso contrário, a mesma oportunidade gera múltiplas observações fortemente dependentes. Somar custos de todas as tentativas, inclusive as que não chegaram à “boa” segunda entrada.

## O que permanece sem suporte

As legendas usam expressões como “sempre”, “nunca” e “confiável”. Aqui são afirmações do autor a investigar, não estimativas. O suplemento não permite reconstruir a argumentação oral completa, todos os critérios discricionários ou o histórico de desempenho. A inspeção detalhada cobriu os casos acima e a figura 1.5 da revisão anterior; os demais gráficos não recebem status de leitura visual concluída.
