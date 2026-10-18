# Síntese crítica dos quatro arquivos

17/10/2026 — estudo bibliográfico e desenho de pesquisa. Não houve retreinamento, alteração de sinais, backtest novo nem reutilização do teste final nesta etapa.

## A contribuição de cada autor

Grimes oferece uma estrutura para relacionar contexto, padrão, entrada, invalidação e gestão. Brooks detalha sequências locais, tentativas e falhas. Nison fornece uma taxonomia de candles e enfatiza sua interpretação no contexto. Aronson pergunta como saber se alguma dessas ideias tem poder preditivo real e como a própria busca pode produzir falsas descobertas.

Essas funções são complementares, mas não equivalem a quatro votos independentes. Vários conceitos são versões do mesmo evento: um rompimento frustrado pode ser chamado de failure test, spring/upthrust ou aparecer dentro de um padrão de candle. Tratar cada nome como confirmação adicional infla a confiança sem necessariamente acrescentar informação.

## Concordâncias que resistem à leitura crítica

1. **Contexto antecede o nome.** Uma sombra inferior longa pode aparecer tanto no martelo quanto no enforcado. Uma barra contrária pode ser apenas correção. Fonte: Nison PDF 40–43; Brooks PDF 16, 203–206; Grimes PDF 56–61, 170–172.
2. **Mudar de tendência não exige inverter a direção.** Lateralizar é um desfecho próprio, que precisa entrar na avaliação. Fonte: Nison PDF 40–41, 96; Grimes PDF 159–162; Brooks PDF 206, 209.
3. **Há diferença entre uma ideia e uma vantagem demonstrada.** Exemplos ajudam a formular regras, mas não estimam desempenho sem um conjunto de oportunidades e fracassos. Fonte: Aronson PDF 218–220; Grimes PDF 228, 308.
4. **O instante da informação importa.** Confirmação posterior deve atrasar o sinal. Pivôs com barra à direita não existem antecipadamente. Fonte: Brooks PDF 207; Nison PDF 22, 77; adaptação causal no protocolo.
5. **A gestão pertence à hipótese.** Entrada, saída, prazo e custos podem transformar um padrão informativo em uma operação inviável. Fonte: Grimes PDF 247–250, 300–304; Brooks PDF 152; Aronson PDF 33.

## Tensões que não devem ser escondidas

| Tema | Diferença encontrada | Consequência para a pesquisa |
|---|---|---|
| Detalhe barra a barra | Brooks atribui utilidade a numerosas microestruturas; Grimes explicita maior preocupação com ruído e aleatoriedade (PDF 198) | Testar incremento de detalhes sobre um modelo simples de contexto |
| Confluência | Nison propõe combinar técnicas (PDF 183); Grimes pede ferramentas que acrescentem informação (PDF 205–208) | Medir contribuição marginal e redundância, em vez de contar confirmações |
| Escalas muito curtas | Nison traz cautela abaixo de 30m com exceções (PDF 161); Brooks mostra 1m/5m (PDF 140–144) | Avaliar cada frequência e horizonte no dataset; nenhum livro resolve a transferência para BTC |
| Stop e ruído | Brooks ilustra stop próximo à barra de sinal (PDF 155); Grimes discute stops além do ruído estrutural (PDF 249–250, 180) | Comparar planos completos com sizing e custos consistentes; distância menor não significa risco menor |
| Discrição | Nison aceita variações e subjetividade; Aronson exige regras reproduzíveis para testá-las | Registrar a tradução matemática como nossa variante e reconhecer o que ela deixa de representar |
| Reação em níveis | Nison descreve polaridade (PDF 211); Grimes mostra aparente respeito até a linhas aleatórias (PDF 116–118) | Incluir níveis placebo e regras de tolerância equivalentes |

## Exemplos de leituras que o sistema deve evitar

“Há três confirmações: candle, momentum e MACD.” As três podem resumir o mesmo deslocamento. A pergunta adequada é quanto cada uma melhora a previsão depois de considerar as outras.

“A tendência acabou; portanto, a próxima vela cai.” O término pode produzir faixa lateral; além disso, duração da tendência e direção da próxima vela são alvos diferentes.

“O H2 foi perfeito porque veio antes da alta.” Só é um exemplo útil se a contagem e o estado de tendência já eram conhecidos antes da alta, inclusive nos casos em que o H2 falhou.

“Uma taxa de acerto superior a 50% paga os custos.” A afirmação ignora magnitudes, exposição, spreads e frequência de negociação. O estudo não converteu melhora de log loss em rentabilidade.

“Estudamos quatro livros, portanto temos quatro fontes de evidência para operar.” Os livros fornecem hipóteses e métodos. Evidência sobre BTC exige observações adequadas e avaliação independente.

## O que muda no entendimento do projeto

O catálogo inicial descrevia formas e movimentos de maneira genérica. Agora há distinções verificáveis entre corpo e amplitude, inside bar e harami, tendência e horizonte, tentativa e falha, informação e execução. Há também referências suficientes para desenhar testes de mecanismos específicos, em vez de acrescentar dezenas de indicadores sem uma pergunta.

O ganho mais imediato é metodológico: toda hipótese nova deverá declarar a definição, o momento em que se torna observável, um baseline comparável, o desfecho que a enfraquece e o conjunto de alternativas tentadas. A hipótese de preço não precisa ser a hipótese de lucro. Um estudo de previsão pode ser informativo mesmo se os custos inviabilizarem negociar.

As seguintes relações são **propostas nossas**, não conclusões dos livros nem resultados já medidos:

- Geometria de candle pode ser mais informativa condicionada à tendência e à posição dentro de uma faixa.
- Frequência recente de dojis pode modular a utilidade de um novo doji.
- Rejeição rápida após ultrapassar um extremo anterior pode diferir de consolidação junto ao extremo.
- A informação de um padrão pode decair antes de cinco minutos, ou surgir apenas em um horizonte maior.
- Um filtro de abstenção pode melhorar a qualidade média e, simultaneamente, reduzir o número de oportunidades a ponto de tornar a estimativa inconclusiva.

## Ordem de pesquisa sugerida

Primeiro, formas simples e verificáveis: engolfo de corpo, harami versus inside bar, rejeição de extremo e frequência de dojis. Depois, contexto e interação de escalas encerradas. Em seguida, sequências com estado, como segunda tentativa e Anti. Por último, famílias raras, gaps clássicos, opções e medidas que exigem dados adicionais.

Essa ordem privilegia verificabilidade e disponibilidade de dados. Ela não é um ranking de lucratividade. As propostas estão detalhadas em `protocol.md` e `hypotheses.json`, com status de não testadas.

## Alcance real

O OCR foi concluído nas 528 páginas de Nison e Brooks; a extração nativa foi feita nos quatro arquivos. A análise produziu dossiês com passagens de todos os capítulos de Grimes, dos capítulos disponíveis de Aronson, dos temas dos 20 capítulos de Nison e das legendas/glossário dos 15 capítulos representados no suplemento Brooks. Isso não equivale a leitura integral de todas as páginas, nem inspeção de todos os gráficos.

As ausências têm naturezas diferentes: a exposição integral de Brooks e o restante de Aronson não estão nos arquivos; já os exemplos ainda não revisados de Grimes e Nison estão disponíveis e permanecem no registro de leitura pendente. O registro não usa processamento automático como prova de compreensão.
