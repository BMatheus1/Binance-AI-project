# Steve Nison — candles, contexto e combinações

Estudo de 17/10/2026 de *Japanese Candlestick Charting Techniques*. O PDF de 316 páginas não possui texto nativo; foi submetido a OCR local em todas as páginas. A leitura semântica e a inspeção visual são registradas separadamente em `coverage.json`. As referências abaixo usam posições físicas do PDF, não uma soma fixa com a página impressa.

A capa e o conteúdo não tiveram a correspondência de edição certificada. O sumário tem páginas fora de ordem e o deslocamento entre paginação física e impressa muda ao longo do arquivo. Isso, isoladamente, não prova perda de conteúdo textual: pode haver supressão de folhas em branco. O arquivo chega à conclusão, glossários e índice; não foi tratado como uma cópia editorial autenticada.

## Capítulos 1–3: o que um candle acrescenta

Nison apresenta os candles como forma de organizar abertura, máxima, mínima e fechamento. O ganho imediato é descritivo e visual. Na modelagem, a representação não cria dados novos além desses preços: pode tornar certas relações mais fáceis de extrair. Uma comparação justa verifica se essas relações acrescentam informação além dos retornos e amplitudes já disponíveis (PDF 20–23, 35–37).

O próprio autor explicita subjetividade, diferenças entre definições e necessidade do fechamento. Também diz que candles, por si só, não oferecem alvos de preço. Essas ressalvas impedem transformar o nome de um padrão em uma ordem completa (PDF 20–23).

A história do método está no capítulo 2, localizado no PDF 27; foi mapeada, mas não recebeu revisão histórica detalhada. Antiguidade e popularidade não serão usadas como prova estatística.

## Capítulo 4: reversão não significa direção oposta

O livro compara mudança de tendência com um veículo que para: pode permanecer parado, seguir adiante ou inverter a direção. Logo, um padrão de reversão pode antecipar lateralização. Ele ainda distingue fechar uma posição existente e abrir uma posição contrária ao movimento principal (PDF 40–43).

**Martelo e enforcado.** A mesma geometria recebe interpretação diferente conforme o movimento anterior. O corpo está na parte superior da amplitude, a sombra inferior é longa e a superior pequena ou ausente. O texto e o glossário mencionam sombra inferior de pelo menos aproximadamente duas vezes o corpo como referência clássica. A cor não é condição indispensável. Para o enforcado, a confirmação baixista posterior recebe ênfase especial (PDF 42–43, 296).

A figura 4.4, inspecionada no PDF 42, mostra exatamente a mesma família geométrica em contextos distintos. Isso invalida uma implementação que transforme toda sombra inferior longa em compra. Também exige cautela com corpo quase zero: a razão sombra/corpo pode explodir. Uma definição de pesquisa precisa lidar explicitamente com dojis e amplitudes nulas.

**Engolfo.** A segunda vela envolve o **corpo** anterior; envolver também as sombras não é obrigatório. O contexto deve conter movimento prévio. O texto admite exceção à regra de cores opostas quando o primeiro corpo é quase um doji. Tamanho relativo, extensão prévia e volume aparecem como qualificadores, sem uma tabela quantitativa de probabilidades (PDF 51–53).

**Dark-cloud cover e piercing.** A descrição clássica inclui gaps de abertura e penetração no corpo anterior. Nison diferencia a recuperação que ultrapassa a metade do corpo daquela que permanece abaixo desse limiar e pode pertencer a padrões de continuação. Relaxar a exigência de gap para BTC contínuo produz uma variante diferente; ela deve receber outro identificador (PDF 56–58, 61–62).

## Capítulos 5–8: famílias, confirmações e ambiguidades

**Estrelas.** A estrela é um corpo pequeno separado do corpo anterior; o abandono do bebê exige separação também entre sombras. Morning/evening star usam a terceira barra como confirmação. Detectar a estrutura parcial na segunda barra e avaliá-la como se a terceira já estivesse disponível é vazamento. A ausência de gap em candles contíguos não deve ser ocultada por um nome clássico (PDF 67–68, 77, 292, 295, 298).

**Harami.** Corpo pequeno dentro do corpo anterior maior. Não é inside bar: esta usa a amplitude máxima–mínima. A cor do segundo corpo não precisa ser oposta. Harami cross substitui o segundo corpo por doji. O texto descreve situações em que a consequência foi uma faixa lateral, não uma alta imediata (PDF 90–92, 96–97). A diferença geométrica foi conferida visualmente no PDF 91.

**Janelas.** Window significa gap entre os extremos de sessões, não apenas diferença entre abertura e fechamento anteriores. O livro associa janelas a continuação e a zonas de suporte/resistência, mas considera também o comportamento depois do preenchimento. Preencher o gap não determina isoladamente reversão (PDF 130–131).

**Rising/falling three methods.** Um impulso longo é seguido por pequenas barras de correção dentro de sua amplitude e por retomada. O número três é um ideal, não uma exigência invariável: o capítulo aceita duas ou mais de três barras. O glossário oferece a figura ideal de cinco linhas. A implementação deve distinguir a versão estrita da versão variável e registrar ambas como tentativas, se ambas forem testadas (PDF 146–148, 301).

**Doji.** Igualdade exata de abertura e fechamento é um caso ideal; o livro admite proximidade e insiste na frequência habitual do evento. Se muitos candles já são dojis, mais um doji traz menos novidade. Nison recomenda cautela abaixo de 30 minutos, com exceções para mercados muito ativos. Essa observação, confirmada visualmente no PDF 161, é contextual e histórica: não prova que BTC 1m funcione ou não funcione (PDF 160–162).

O autor atribui assimetria a dojis em topos e fundos. Na pesquisa, isso deve gerar uma hipótese a comparar, não uma simetria forçada nem uma verdade aceita. Também não é adequado transformar “indecisão” em causa observada: um mesmo OHLC pode resultar de diversas trajetórias intrabar.

## Taxonomia complementar do glossário

O glossário A foi lido nas páginas PDF 292–304. As descrições abaixo são resumos, não um detector completo dos padrões.

| Família | Estrutura distintiva | Principal cuidado na adaptação |
|---|---|---|
| Shooting star / inverted hammer | Sombra superior longa, corpo pequeno perto da mínima; contexto anterior muda a interpretação | O invertido exige confirmação; a forma isolada não decide direção |
| Belt hold | Corpo longo que abre numa extremidade | Definir tolerância em ticks e normalização de tamanho |
| Tweezers | Testes de máximas/mínimas próximas | “Próximas” exige tolerância prévia; o nível não pode nascer do futuro |
| Counterattack | Abertura afastada e fechamento próximo do anterior | Depende de gap e equivalência de preço |
| Three white soldiers / three crows | Sequência de corpos direcionais e fechamentos próximos dos extremos | Contexto e possível extensão excessiva importam |
| Advance block / stalled | A sequência perde força por corpos menores ou sombras | Desaceleração não implica queda imediata |
| Mat hold / tasuki / side-by-side | Continuação que combina gaps e pequenas correções | Raridade e sessões; não remover condições sem declarar variante |
| On-neck / in-neck / thrusting | Recuperações com diferentes penetrações após vela de queda | Não confundir pequena recuperação com piercing confirmado |
| Tower / dumpling / fry pan | Estruturas amplas de mudança, algumas confirmadas por janela | Duração flexível amplia liberdade de seleção |
| Three mountains / rivers / Buddha | Múltiplos testes de extremos, com variantes semelhantes a ombro–cabeça–ombro | Pivôs devem respeitar atraso de confirmação |
| Tri-star / abandoned baby | Padrões raros com dojis e separações específicas | Amostra pequena pode impedir inferência útil |

A descrição resumida de tasuki no glossário não é suficiente para resolver todas as relações entre a correção e o preenchimento do gap. Antes de codificar esse padrão, é necessária revisão dedicada da passagem principal correspondente. O estudo não preenche essa lacuna inventando uma fórmula.

## Capítulos 9–14: combinar sinais sem contar a mesma informação várias vezes

O capítulo 9 reúne exemplos (início no PDF 176); não foi feita inspeção individual de todos os seus gráficos. Na abertura da segunda parte, a “regra de múltiplas técnicas” propõe confluência; o capítulo 10 mostra padrões próximos à mesma região (PDF 183, 188).

Para um modelo, três indicadores derivados dos mesmos preços não são três testemunhas independentes. Corpo direcional, momentum curto e inclinação de uma média podem refletir o mesmo movimento. A avaliação deve comparar contexto sozinho, candle sozinho e combinação, medindo o incremento fora da amostra. Exigir mais confirmações também reduz o número de eventos; melhora aparente pode ser seleção de uma amostra minúscula.

**Linhas, springs/upthrusts e polaridade.** O capítulo 11 discute linhas e mudança de papel de antigos níveis. É compatível com investigar rejeições e retestes, mas precisa ser confrontado com o alerta de Grimes sobre linhas aleatórias. “Muitas vezes respeitado” requer denominador e critério estável de toque (PDF 195–196, 203, 211).

**Retrações.** O capítulo 12 apresenta níveis usuais como 38%, 50% e 62% (PDF 219). O estudo não atribui eficácia especial a essas proporções. Comparar apenas níveis famosos, sem níveis de controle e sem contar alternativas, favorece confirmação. A questão útil é se a posição relativa da correção contém informação, e se um nível específico acrescenta algo além disso.

**Médias.** O capítulo 13 reconhece atraso e dependência de tendência (PDF 225). **Osciladores.** O capítulo 14 distingue divergência, extremos e momentum. Alerta que um oscilador pode permanecer sobrecomprado quando começa uma tendência forte; um sinal contrário também pode orientar saída, não necessariamente uma posição inversa (PDF 236–238). Isso converge com Grimes e evita tratar RSI alto como venda automática.

## Capítulos 15–20: dados adicionais e finalidade da operação

**Volume e open interest.** O volume aparece como confirmação, com limitações de reporte e estrutura dos contratos da época. Open interest é estoque de contratos em aberto; volume é fluxo de negócios. Não podem ser substituídos um pelo outro. O autor interpreta preço mais OI como evidência sobre entrada/saída de participantes; nossa base de candles não identifica sua intenção individual (PDF 249–250, 256). OI exigiria uma fonte própria com horário de disponibilidade.

**Elliott.** O capítulo 16 combina candles e contagem de ondas. A passagem consultada reconhece subjetividade da contagem (PDF 261). Não cabe produzir ondas retrospectivas e chamá-las de features disponíveis. A parte introdutória e todos os exemplos não foram revisados integralmente.

**Market Profile.** O capítulo 17 usa períodos, distribuição de preços e área de valor (PDF 265–266). Um histograma de preços de fechamento ponderado pelo volume do candle não reconstrói o volume realmente negociado em cada preço. Com OHLCV, essa aproximação precisa ser rotulada como aproximação, sem chamar volume profile exato de algo que não foi observado. Também não se assume normalidade a partir da convenção de área de valor.

**Opções.** O capítulo 18 lembra que volatilidade e prazo influenciam o preço da opção, além da direção do ativo (PDF 272–273). Portanto, acertar a direção de BTC não basta para avaliar uma estratégia de opções. Não foram propostas operações com opções neste estudo.

**Hedge.** O capítulo 19 distingue reduzir a exposição de uma posição econômica existente e buscar ganho especulativo (PDF 279–280). Avaliar hedge apenas por seu P&L separado pode inverter o objetivo: interessa o resultado da exposição combinada.

**Casos do autor.** O capítulo 20 apresenta exemplos de recomendações e explicitamente não oferece um conjunto universal de regras. O caso do petróleo termina com stop no breakeven após fracasso no reteste e posterior queda: uma leitura útil inclui esse resultado menos espetacular (PDF 284, 289). A conclusão mantém contexto, flexibilidade e diferenças entre mercados como elementos essenciais (PDF 290–291).

## Tradução para uma pesquisa causal

Descritores básicos propostos, disponíveis após o fechamento de `t`:

```text
amplitude = H - L
corpo = abs(C - O)
sombra_inferior = min(O, C) - L
sombra_superior = H - max(O, C)
posição_fechamento = (C - L) / amplitude, quando amplitude > 0
```

Corpo e sombras podem ser divididos pela amplitude; tamanhos absolutos podem ser normalizados por volatilidade calculada previamente. Candles de amplitude zero devem receber tratamento explícito e indicador de degeneração; não se deve atribuir-lhes automaticamente significado de doji com rejeição.

Uma hipótese de martelo deve separar a forma geométrica, a queda anterior e a confirmação posterior. Se a confirmação é usada, o instante do sinal avança até ela. Uma variante sem gap não pode ser apresentada como reprodução fiel de morning star clássico. Uma comparação por horizonte deve manter “candle de 5m” e “prever cinco minutos à frente” como conceitos distintos.

Ainda faltam revisões detalhadas de diversos exemplos e de padrões menos prioritários. O material já estudado sustenta a taxonomia e as distinções acima; não sustenta leitura integral, taxa de acerto, retorno esperado ou autorização de operar.
