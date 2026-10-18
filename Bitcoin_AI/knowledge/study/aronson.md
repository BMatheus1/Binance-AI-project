# David R. Aronson — como transformar padrões em conhecimento testável

Estudo de 17/10/2026 de *Evidence-Based Technical Analysis*, tradução automática fornecida pelo usuário. Referências indicam páginas físicas do PDF. O arquivo tem 300 páginas e **termina no meio do capítulo 6**, na página impressa 302, durante a discussão de outliers positivos. O sumário anuncia capítulos 7–9, apêndice e índice que não estão presentes. A leitura aprofundada abaixo cobre passagens dos capítulos 1–6 disponíveis; não reivindica leitura integral dessas 300 páginas.

A extração normal apresenta trechos fora de ordem. Foi gerada uma segunda extração com preservação de layout. A tradução contém expressões defeituosas; fórmulas e relações causais não devem ser copiadas automaticamente. O texto extraído não é uma edição revista do original inglês.

## Capítulo 1 — definição de regra e comparação justa

Uma regra objetiva precisa produzir a mesma decisão com os mesmos dados e parâmetros. Ser objetiva não garante que seja útil; apenas permite avaliá-la. “Padrão forte”, “nível importante” e “contexto favorável” ainda não são regras enquanto dois implementadores puderem chegar a sinais diferentes (PDF 17–18, 25–34).

O autor distingue série de entrada, sinal e retorno produzido pela posição. A saída binária `+1/-1` representa posição comprada/vendida; **não se refere a opções binárias**. Essa distinção evita transformar uma discussão estatística sobre sinais em aprovação de qualquer produto financeiro.

Um ponto essencial é separar capacidade de previsão e exposição à tendência média do mercado. Uma regra que fica muito mais tempo comprada pode ganhar em um mercado ascendente sem acertar os momentos de entrada. Para uma regra sem associação preditiva, a contribuição média da exposição é proporcional a:

```text
(fração comprada - fração vendida) × retorno médio do mercado
```

Isso motiva o tratamento dos retornos de referência no livro (PDF 30–33). No projeto, comparar retorno líquido com benchmarks de exposição semelhante é mais informativo que comparar somente com zero. Para classificação, a frequência de classes é um baseline distinto: vencer esse baseline não implica superar economicamente a exposição passiva.

**Causalidade.** A série que alimenta os sinais não deve incorporar o ajuste calculado com dados futuros. A discussão de detrending para avaliação não autoriza subtrair uma média do teste inteiro das features de cada instante. Há ainda uma convenção específica de negociação após o sinal no texto; não confundi-la com o target já implementado no projeto (PDF 31–33).

**Informação versus lucro.** O autor pode estudar informação sem despesas para isolar uma hipótese estatística, mas distingue isso da viabilidade econômica. A pesquisa BTC precisa registrar separadamente resultado informacional, resultado bruto e resultado líquido. Não se pode divulgar o primeiro como se fosse o terceiro.

## Capítulo 2 — por que olhar muitos gráficos não basta

O argumento é sobre os limites da avaliação informal, não sobre a impossibilidade lógica de todo padrão ter valor. Se a definição muda conforme o resultado, o método fica protegido contra refutação. Uma versão programável permite contar também os fracassos e as oportunidades ausentes (PDF 34–36).

O viés retrospectivo mistura o que sabíamos antes e depois. Depois de uma queda, a mesma barra que parecia ambígua passa a parecer uma venda óbvia. A consequência prática é guardar o estado da decisão antes do desfecho: features, nível, contexto, previsão e motivo de abstenção (PDF 51–52).

O viés de confirmação aparece quando se procuram apenas ocorrências favoráveis ou se acrescentam exceções para explicar cada perda. Capacidade de argumentar não resolve esse problema: uma explicação sofisticada pode apenas tornar uma crença mais resistente. O protocolo precisa definir previamente o resultado que enfraquecerá a hipótese (PDF 72–73).

Para investigar “martelo antecipa alta”, a tabela necessária inclui padrão presente/ausente e alta presente/ausente, dentro de contextos comparáveis. Colecionar exemplos de martelo seguido de alta não informa quantas vezes a alta também ocorreu sem martelo. Essa é uma adaptação operacional da discussão de correlações ilusórias, não uma regra atribuída literalmente ao autor.

## Capítulo 3 — hipótese, previsão e teste

A distinção mais útil é entre **gerar uma ideia** e **testar uma ideia**. Uma ideia pode surgir de um gráfico, intuição ou leitura. A avaliação deve usar observações cujo resultado ainda não influenciou sua formulação. Dados históricos podem funcionar como teste somente se seu conteúdo permaneceu efetivamente desconhecido ao processo de seleção (PDF 129–133).

A confirmação é provisória. “Observei esse padrão e depois houve alta” não prova que ele causa altas. A mesma evidência pode ser compatível com tendência prévia, seleção de exemplos ou coincidência. A hipótese precisa fazer uma previsão suficientemente precisa para poder falhar.

Há uma ressalva à retórica de prova/refutação usada no livro: uma hipótese **probabilística** não é refutada por uma única operação perdedora. Um teste estatístico rejeita sob um modelo e um nível de erro; não produz certeza lógica. A documentação do projeto deve usar “evidência compatível/incompatível sob as premissas” e preservar a distinção entre ausência de evidência e evidência de ausência.

## Capítulo 4 — população, amostra e futuro limitado

O histórico observado é uma realização de um processo, não todo o universo de resultados possíveis. O autor propõe pensar num futuro prático limitado, reconhecendo que a vantagem pode mudar. Não é legítimo inferir que uma regra continuará funcionando indefinidamente (PDF 164–165, 185–187).

Milhões de candles não equivalem a milhões de observações independentes. Horizontes de cinco minutos calculados a cada minuto se sobrepõem; operações do mesmo episódio compartilham contexto; regimes podem persistir. Assim, o tamanho nominal da base não resolve sozinho a incerteza. Esta é uma implicação para o projeto, não uma estimativa fornecida pelo livro.

A distribuição amostral descreve como uma estatística varia entre amostras. O texto compara aproximações clássicas com procedimentos de reamostragem. Usar computador não elimina premissas: o método precisa representar a dependência e o tipo de hipótese que está sendo testada (PDF 214–215).

## Capítulo 5 — teste, bootstrap e permutação

O texto diferencia teste de uma afirmação e estimativa de magnitude. Para pesquisa, ambos interessam: saber se o efeito é distinguível do ruído e se sua magnitude supera custos e incerteza (PDF 216, 218–224).

**Valor-p.** Interpretação correta para o caso unilateral: probabilidade, **sob a hipótese nula e o procedimento especificado**, de observar uma estatística tão alta quanto a obtida ou maior. Não é a probabilidade de a estratégia ser inútil, nem a chance de o próximo trade perder. Também não incorpora automaticamente as centenas de alternativas que podem ter sido tentadas antes (PDF 219 e 234–240).

**Bootstrap apresentado.** Parte da série de retornos da regra, centraliza-a para a nula de média zero e amostra com reposição para construir uma distribuição da média. A centralização dos retornos da regra é uma etapa diferente de remover a deriva do mercado de referência. Confundir as duas transformações muda a hipótese (PDF 234–237).

**Permutação apresentada.** Mantém a sequência dos sinais e reorganiza os retornos de mercado associados, sem reposição. A nula representa ausência de associação informativa entre sinal e retorno posterior. O objeto reamostrado e a hipótese são diferentes dos do bootstrap. Por isso, os testes não precisam produzir exatamente a mesma resposta (PDF 234, 238–240).

**Adaptação necessária.** Em BTC de alta frequência, permutar individualmente todos os minutos destrói parte da estrutura temporal que pode ser relevante. Um desenho futuro deve justificar intercambiabilidade ou escolher reamostragem em blocos, com unidades e comprimentos declarados. Não basta chamar a função de bootstrap e presumir que a significância ficou correta. A escolha de blocos também deve ser analisada sem escolher depois apenas a que produz significância.

**Intervalos de confiança.** O livro os relaciona à distribuição amostral e descreve cobertura em repetições do procedimento (PDF 247, 252). Não interpretar o intervalo observado como garantia sobre o próximo retorno. A cobertura pode falhar se o processo muda ou as premissas de reamostragem não se sustentam.

**Exemplo e seleção.** O capítulo ilustra a regra TT-4-91 e seu resultado histórico. Isso é um exemplo do método de teste; não é resultado do nosso projeto. O próprio avanço ao capítulo 6 impõe perguntar de quantas regras ela foi escolhida. Não transportar o p-valor de um teste individual para o vencedor de uma busca extensa.

O arquivo menciona a extensão de White para mineração de regras (PDF 235), mas o trecho não é uma especificação completa do teste conjunto. Além disso, afirmações antigas sobre patente e distribuição de software não foram verificadas como atuais e não orientam a implementação.

## Capítulo 6 — seleção do vencedor e mineração de regras

O desempenho observado combina mérito e ruído. Quando se escolhe o maior entre muitas estimativas, também se selecionam erros positivos. A diferença esperada entre o desempenho observado do vencedor e seu desempenho verdadeiro é o viés de mineração. Não é a mesma coisa que dizer que toda pesquisa de regras é inválida (PDF 253–254).

Cinco fatores são enumerados no material disponível (PDF 285–290):

1. Mais regras avaliadas tendem a aumentar o viés de seleção.
2. Mais observações, sob premissas adequadas, reduzem a variabilidade.
3. Menor correlação entre resultados de regras amplia as possibilidades de selecionar um extremo.
4. Outliers positivos podem dominar o ranking.
5. Quando as regras têm mérito verdadeiro parecido, a sorte pesa mais na escolha do vencedor.

“Número de regras” deve incluir tentativas descartadas, janelas, thresholds, famílias de features, regimes e decisões humanas orientadas pelos resultados. Contar apenas os modelos salvos subestima a busca. Da mesma forma, correlação moderada entre estratégias não significa que se testou efetivamente uma única hipótese.

As simulações usam regras artificiais cujo desempenho verdadeiro pode ser controlado. Nesse trecho, **ATR significa artificial trading rule**, e não Average True Range. Confundir a sigla produziria uma interpretação completamente errada das figuras (PDF 288–290). Os percentuais dos experimentos são resultados de simulações específicas, não estimativas de lucro em BTC.

A última página mostra a discussão de correlação e inicia o fator relativo a outliers; a frase final é interrompida. Portanto, não se atribui a este arquivo a leitura dos resultados do estudo de 6.402 regras anunciado na introdução. A parte correspondente do livro está ausente.

## Consequências concretas para Bitcoin_AI

| Problema | Regra de pesquisa derivada | O que seria um erro |
|---|---|---|
| Várias versões de um padrão | Registrar a família inteira e todos os candidatos | Publicar só o melhor threshold |
| Escolha de regime após ver lucro | Tratar a segmentação como nova hipótese exploratória | Chamar o subgrupo escolhido de validação independente |
| Série temporal dependente | Separação cronológica, purga e inferência compatível com dependência | Embaralhar os candles no treino/teste |
| Mesmo teste observado repetidamente | Preservar o teste consumido e reservar dados novos | Apagar o registro ou rebatizar o mesmo período |
| Ganho com viés comprador | Comparar exposição e custos equivalentes | Chamar deriva do mercado de previsão |
| Um ou dois grandes ganhos | Informar concentração e análise de sensibilidade | Remover seletivamente perdas como “anomalias” |
| Resultado nulo | Registrar hipótese inconclusiva ou não sustentada | Inventar um novo filtro e ocultar a tentativa anterior |

Julho–setembro de 2026 já participou da avaliação final do projeto. Este estudo não tornou esse intervalo desconhecido novamente. As propostas novas podem ser exploradas em blocos de desenvolvimento, mas precisam de avaliação prospectiva realmente nova antes de qualquer alegação confirmatória.

## Questões ainda abertas

Faltam as páginas restantes do capítulo 6 e os capítulos 7–9 do livro. Também há passagens disponíveis não revisadas em detalhe, sobretudo exemplos filosóficos e derivações intermediárias. O dossiê não é uma implementação certificada do Reality Check nem uma reprodução empírica do estudo de Aronson; é uma base metodológica para desenhar a próxima pesquisa corretamente.
