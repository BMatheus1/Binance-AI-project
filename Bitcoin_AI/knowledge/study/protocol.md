# Protocolo proposto a partir do estudo

Versão bibliográfica de 17/10/2026. **Não executado.** Este documento concretiza perguntas para a próxima pesquisa; não altera o experimento existente e não é um pré-registro confirmatório completo. Os detalhes marcados como pendentes precisam ser fixados antes de abrir dados de avaliação novos.

## Tempo, informação e alvo

O código atual define `t` como a barra de um minuto recém-encerrada, entrada teórica em `open[t+1]` e saída em `close[t+h]`, para `h=1` ou `5`. O estudo preserva essa convenção. Execução na abertura seguinte é uma hipótese de simulação, não promessa de preenchimento sem latência.

Padrões de múltiplas barras somente existem após a última barra necessária. Se um martelo exige confirmação em `t+1`, o sinal se torna disponível depois do fechamento de `t+1`; não se pode usar o retorno desse candle como resultado posterior ao sinal confirmado.

Escala e horizonte devem aparecer em campos diferentes: um padrão calculado em candles de 5m pode alimentar uma previsão de um minuto, mas essa previsão só usa o último candle de 5m encerrado. Um candle de 5m das 12:00 até antes de 12:05 só estará disponível às 12:05; às 12:03, seu fechamento final ainda é desconhecido.

## Vocabulário matemático comum

Para uma barra válida, `R=H-L`, `B=abs(C-O)`, `LW=min(O,C)-L`, `UW=H-max(O,C)`. Quando `R>0`, `b=B/R`, `lw=LW/R`, `uw=UW/R` e `cp=(C-L)/R`.

Amplitude zero tem flag própria; as razões não autorizam interpretar a barra como rejeição. A política de valores numéricos deve ser consistente com o catálogo existente. Limiares são adaptações nossas. Nenhum limiar abaixo foi escolhido mediante busca de lucro no teste final.

Usar como primeira especificação exploratória uma janela de contexto de 20 barras, extremos calculados **até t−1** e volatilidade/amplitude de referência também anterior ao evento. Toda troca de janela conta como nova tentativa. Uma alternativa é trabalhar com descritores contínuos, evitando multiplicar thresholds antes de demonstrar incremento informacional.

## Quatro candidatos suficientemente concretos para implementação posterior

**H06 — rejeição de extremo.** Para um evento baixista, `U=max(H[t-20:t-1])`, exigir `H[t]>U` e `C[t]<U`; a versão altista usa o mínimo anterior e recuperação acima dele. Igualdades são excluídas na versão estrita. Entrada teórica apenas no candle seguinte. Comparar com rompimentos que fecham além do nível e com candles sem evento, pareados por tendência/volatilidade disponíveis. Não afirmar que qualquer janela de 20 barras é a resistência discricionária de Grimes.

**H03 — engolfo de corpo.** Exigir cores contrárias e corpo de `t` envolvendo o corpo de `t−1`: `min(Ot,Ct) <= min(Ot−1,Ct−1)` e `max(Ot,Ct) >= max(Ot−1,Ct−1)`, com pelo menos uma desigualdade estrita. Excluir corpos zero nessa versão. Guardar amplitude, direção e tendência anterior separadamente. Não exigir engolfo das sombras. A exceção de quase-doji descrita por Nison seria uma variante adicional, não incluída silenciosamente.

**H04 — harami versus inside bar.** Inside bar: `Ht <= Ht−1` e `Lt >= Lt−1`. Candidato a harami: corpo atual contido no anterior, `Bt <= 0,5 × Bt−1`, com `Bt−1>0`. O fator 0,5 é nossa escolha exploratória para “pequeno”. Comparar quatro grupos: apenas harami, apenas inside, ambos e nenhum, controlando pelo contexto. Não inferir direção de rompimento apenas da compressão.

**H05 — doji e sua frequência.** Candidato geométrico: `R>0` e `B/R <= 0,1`. Raridade: fração de candidatos nos 20 candles **anteriores**, sem incluir o atual. Comparar efeito do evento em estratos de frequência definidos no desenvolvimento, com tendência e amplitude controladas. O fator 0,1 e a janela de 20 são adaptações de pesquisa; não foram prescritos por Nison ou Brooks.

Para H02, H07–H10 e demais sequências, ainda falta congelar integralmente as convenções. O catálogo identifica isso; não haverá interpretação de um backtest como “teste da regra do livro” enquanto tais ambiguidades existirem.

## Avaliação em camadas

1. **Disponibilidade e frequência:** eventos por mês, lado, regime e escala; falhas de dados, padrões degenerados, gaps e sinais não executados. Raridade não é prova de qualidade.
2. **Informação incremental:** baseline com retornos/amplitudes/contexto; modelo simples com e sem o grupo candidato. Comparar log loss e Brier de probabilidades calibradas. Registrar frequência das classes, incluindo empate, e estabilidade mensal.
3. **Magnitude e percurso:** retorno por horizonte e excursões favorável/adversa como resultados de análise, nunca features futuras. Não confundir a ordem dos extremos dentro de um candle com uma trajetória observada.
4. **Economia:** simulação separada com custos de ida e volta, spread, slippage, latência, regras de sobreposição e preenchimento. Reportar giro, exposição, drawdown e concentração de resultados, além da média.

Não exigir que todas as hipóteses produzam uma operação. H04, por exemplo, pode revelar compressão ou incerteza útil para abstenção sem oferecer direção lucrativa.

## Seleção, múltiplas tentativas e independência

Usar blocos cronológicos de desenvolvimento, calibração e validação, com purga que alcance o fim de cada rótulo. Não deslocar a fronteira depois de ver um resultado desfavorável. A nova rodada não pode chamar julho–setembro/2026 de teste não observado.

Registrar todas as configurações, inclusive falhas e descartes. Modelos, features, filtros, lados, horizontes e métricas selecionadas após inspeção constituem parte da busca. A tabela de candidatos contém 16 perguntas; ela não limita automaticamente o número de testes a 16.

Para inferência confirmatória futura, primeiro congelar a família de comparações e a regra de seleção. Uma opção é correção de Holm para p-valores válidos da família declarada; outra é um teste conjunto de máximo que replique a seleção dentro da reamostragem. Isso exige projeto e implementação específicos. Não afirmar que já executamos o procedimento de White porque o livro o menciona.

Reamostragem deve respeitar dependência temporal e eventos sobrepostos. Considerar unidades de episódio e/ou blocos temporais, reportando sensibilidade ao tamanho do bloco. Um bootstrap de minutos independentes pode produzir precisão ilusória. O comprimento de bloco não deve ser escolhido para obter o menor p-valor.

## Controles negativos e testes de robustez

- Níveis placebo com a mesma escala de distância e tolerância dos níveis reais, gerados antes de examinar os desfechos. Não comparar linhas escolhidas visualmente com placebos desfavorecidos.
- Benchmark com exposição e frequência de decisão semelhantes, para separar direção média do mercado e timing.
- Ablar contexto, forma e interação, mantendo o orçamento de seleção comparável.
- Relatar concentração em poucos episódios e resultados com/sem os maiores ganhos como sensibilidade, mantendo o resultado integral como principal. Não excluir apenas perdas.
- Perturbações moderadas de parâmetros previamente declaradas; estabilidade em uma região é mais informativa que um pico isolado.
- Teste causal por modificação do futuro: alterar preços após `t` não pode mudar o sinal em `t`. Inclui pivôs, níveis, agregações maiores e contagem de tentativas.

## Critérios de decisão

Antes da rodada confirmatória, fixar magnitude mínima relevante, custo conservador, família de testes, quantidade mínima de episódios e tratamento de dados insuficientes. Esses números não foram inventados neste estudo bibliográfico.

“Não sustentada” significa que o resultado não passou os critérios declarados. “Inconclusiva” se aplica quando a amostra ou identificação não permite decidir. “Sustentada no período” ainda não significa durabilidade, causalidade ou aprovação para negociação real. Qualquer conclusão deve mencionar o universo de regras tentadas e as condições da amostra.

## Fora do escopo desta rodada

Open interest, livro de ofertas, volume exato por preço e opções precisam de dados próprios. O estudo não autoriza inferi-los de OHLCV. Padrões dependentes de abertura de bolsa exigem adaptação de sessão que se torne parte explícita da hipótese. Não haverá execução financeira real ou promoção automática de modelo.
