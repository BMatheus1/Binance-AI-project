# Adam Grimes — estrutura, padrões e gestão

Estudo de 17/10/2026. Fonte: *The Art & Science of Technical Analysis*, arquivo original em `data/knowledge/books`. Todas as referências abaixo indicam **páginas físicas do PDF**, contadas desde 1. Síntese crítica de passagens selecionadas dos 12 capítulos e do apêndice B; não representa leitura integral de cada exemplo, nota e página. O registro verificável de cobertura está em `coverage.json`.

## Tese e limites da evidência

O livro organiza o trading em torno de uma vantagem pequena, contextual e sujeita a desaparecer. Disciplina, psicologia e dimensionamento não substituem expectativa positiva. A expectativa depende conjuntamente da frequência e magnitude de todos os resultados, inclusive perdas extremas, e deve sobreviver às despesas de execução (PDF 20–23, 300–304).

É importante separar três níveis: a geometria efetivamente observada; a interpretação do autor sobre pressão compradora/vendedora; e a existência de poder preditivo mensurável. OHLC permite observar a primeira. A segunda é uma explicação possível, não uma identificação de quem negociou. A terceira exige dados novos. Expressões como “traders presos” não autorizam o sistema a afirmar que detectou posições institucionais.

## Capítulos 1–5: como interpretar a estrutura

**Capítulo 1 — vantagem.** A distribuição importa mais que a operação isolada. Uma sequência de perdas pode coexistir com uma estratégia útil; uma vitória pode ocorrer sem vantagem. A unidade de análise deve ser uma série de decisões reproduzíveis, não o gráfico que mais impressionou. Custos criam uma barreira adicional: expectativa bruta zero produz expectativa líquida negativa (PDF 20–23).

**Capítulo 2 — ciclo e quatro operações.** Continuação, término de tendência, manutenção de suporte/resistência e rompimento de suporte/resistência formam uma taxonomia útil. Não são quatro estados mutuamente exclusivos do mercado: a mesma operação pode ser continuação numa escala e rompimento em outra. Acumulação/distribuição são interpretações que podem ficar claras apenas depois do movimento; usá-las retroativamente como entradas seria vazamento. Término de tendência não implica tendência oposta: também pode produzir lateralização (PDF 56–61).

**Capítulo 3 — tendências.** O bloco impulso–correção–impulso organiza a leitura. A correção pode ser uma tendência contrária na escala inferior. Uma correção proporcional e com menor atividade difere de uma perna contrária forte que rompe a estrutura. A contagem de pernas e a divergência são pistas, não prazos obrigatórios para reversão. Evitar a tautologia de escolher, depois do resultado, “a primeira entrada perfeita” (PDF 65–69, 81–84, 111–112).

**Capítulo 4 — lateralização.** Os níveis são zonas cuja largura precisa ser definida. O experimento de linhas aleatórias é especialmente importante: linhas desenhadas sem observar os preços também parecem respeitadas pelo mercado. Consequentemente, a análise deve comparar níveis propostos com níveis placebo, definidos antes do desfecho e sujeitos às mesmas tolerâncias. Escolher um stop estreito e um alvo distante não cria expectativa por si só. Compressão de amplitude também não identifica necessariamente a direção do próximo rompimento (PDF 113–120, 134–136).

**Capítulo 5 — transições.** O livro distingue rompimentos, término gradual, reversão e tentativas frustradas de mudança. O sistema deve registrar a sequência de eventos conhecida em cada instante. Não deve dar ao início de uma consolidação o nome que somente o resultado permitiria escolher. Uma notícia pode produzir reversão sem aviso gráfico; a ausência de padrão não elimina risco (PDF 137–140, 159–162).

## Capítulo 6: os oito modelos operacionais

Os modelos abaixo preservam a lógica do autor, mas não constituem código nem parâmetros validados para BTC. O capítulo os apresenta como estruturas de decisão, não como oito sinais universais independentes de contexto (PDF 165).

| Modelo | Contexto e gatilho | Invalidação e dificuldade | Referência PDF |
|---|---|---|---|
| Failure test | Excesso/tendência madura ou rompimento frustrado; ultrapassa nível prévio e fecha novamente dentro, na mesma barra ou na seguinte | Novo extremo contra a posição; permanência perto do nível enfraquece a tese de rejeição rápida | 166–169 |
| Pullback entrando no suporte/resistência | Tendência com impulso anterior consistente; posicionamento na correção, eventualmente após falha local | O suporte inclinado pode continuar descendo; comprar na mínima que só depois se revelou mínima é retrospectivo | 170–172, 175–178 |
| Pullback entrando no rompimento menor | Mesmo contexto, mas aguarda rompimento da estrutura da correção em escala inferior | Confirmação costuma piorar o preço; stop minúsculo e reentradas repetidas acumulam despesas | 178–181 |
| Pullback complexo | Duas pernas contrárias separadas por recuperação; pode estar parcialmente oculto na escala principal | Pode ocorrer depois de uma primeira tentativa perdedora; limitar o risco agregado das tentativas | 181–185 |
| Anti | Sinal de desgaste, impulso contrário com mudança de caráter, primeira correção após esse impulso | Não equivale a vender qualquer sobrecompra; a antiga tendência pode se restabelecer | 186–189 |
| Entrada na base anterior ao rompimento | Consolidação estreita próxima à borda de uma faixa maior | O rompimento pode nunca ocorrer; ordem limitada pode não executar; antecipação não é confirmação | 190–193, 196 |
| Primeiro pullback após rompimento | Impulso além do nível seguido de correção controlada | Retestar ou ultrapassar ligeiramente o nível antigo não prova falha; importa a estrutura inteira | 197–198 |
| Rompimento fracassado | Ausência de continuidade e/ou forte reação contrária; estrutura do primeiro pullback se desfaz | A passagem pelo nível, isoladamente, é insuficiente; alternar compra e venda mecanicamente gera perdas nas duas pontas | 199–202 |

O failure test é um bom primeiro candidato para formalização porque tem evento e invalidação relativamente claros. Mesmo nele, “resistência significativa”, “extensão” e “imediatamente” exigem definições anteriores ao teste. O autor espera deslocamento favorável rápido, aproximadamente uma a três barras no exemplo conceitual (PDF 169). Isso oferece uma hipótese de **tempo até resposta**, separada da direção final.

A sequência Anti é mais específica que uma divergência: desgaste → impulso contrário → correção → tentativa de continuidade na nova direção. Colapsar tudo em `RSI > 70` perde o conteúdo do método. Uma implementação deve guardar estado e expirar setups antigos; não procurar a posteriori o encadeamento que funcionou.

## Capítulo 7 e apêndice B: indicadores como medidas

Grimes pede domínio de poucos instrumentos e questiona a utilidade de acumular confirmações redundantes (PDF 205–208). A posição do preço em relação à média e a inclinação da média descrevem uma escala; médias de comprimentos diferentes podem legitimamente apontar tendências diferentes.

Seu MACD modificado tem especificação verificável (PDF 432–436):

```text
linha_rapida[t] = SMA(close, 3)[t] - SMA(close, 10)[t]
linha_sinal[t]  = SMA(linha_rapida, 16)[t]
referencia     = zero
histograma    = não usado nessa versão
```

Não substituir silenciosamente SMA por EMA nem usar 12/26/9 com o mesmo nome. A memória das médias muda a resposta. No experimento com uma série de inclinação constante, a linha rápida se estabiliza após a adaptação das janelas; um recuo da linha não significa necessariamente queda do preço. A expressão do livro sobre “segunda derivada” deve ser lida com cuidado: **o nível** da diferença de médias reflete a inclinação suavizada; **a mudança desse nível** responde a mudanças da inclinação. Não implementar a diferença de médias como se fosse literalmente uma segunda derivada.

A linha rápida pode permanecer extrema durante uma tendência forte. Procurar divergências entre partes do mesmo impulso confunde efeito do filtro com mudança estrutural. O autor propõe comparar movimentos distintos e discute retorno da linha à vizinhança de zero entre eles (PDF 226–229). Seu exemplo de sinais aparentemente perfeitos vem acompanhado da advertência de que as entradas ocorrem no fechamento e de que exemplos escolhidos merecem desconfiança (PDF 228).

## Capítulos 8–10: saída, tamanho e falhas

**Horizonte do sinal.** Uma previsão válida por poucas barras não justifica um alvo muito distante. Inversamente, um sinal lento pode ser inutilizado por stop colocado dentro do ruído de uma barra. Alvo, stop, prazo e entrada fazem parte da mesma hipótese (PDF 247–250).

**Dimensionamento.** O autor prefere limitar o risco por operação e alerta para a agressividade de métodos otimizados quando as probabilidades e perdas futuras são mal estimadas. Dependência entre operações e mudanças de regime enfraquecem as premissas de dimensionamento. Seus percentuais são exemplos da abordagem dele, não recomendações para este projeto (PDF 279–282).

**Assimetria do drawdown.** Para queda fracionária `d`, a alta necessária para recuperar é `d/(1-d)`. Para `n` perdas sucessivas de fração `f`, o patrimônio restante é `(1-f)^n`; a perda acumulada é `1-(1-f)^n`. A página 282 imprime a expressão de patrimônio restante sob uma designação de perda: a documentação não deve copiar essa ambiguidade.

**Risco além do stop.** Slippage, indisponibilidade, liquidez e perdas extremas impedem tratar o stop como garantia de preço. Correlação pode aumentar justamente quando a diversificação é necessária. Para BTC 1m/5m, ambos os horizontes usam o mesmo ativo e não representam duas exposições independentes (PDF 300–306; última frase é adaptação própria).

**Exemplos.** O capítulo 10 explica que parte dos casos foi selecionada por valor pedagógico e não corresponde a trades efetivamente realizados. O método de mostrar primeiro o gráfico até a decisão e depois a continuação é útil para exercícios cegos. As três falhas de rompimento — no ponto de saída, no primeiro pullback e ainda na base — merecem rótulos distintos (PDF 307–309, 356–359). Não é possível estimar a taxa de sucesso do método contando os vencedores desse capítulo.

## Capítulos 11–12: aprendizado e avaliação

O livro trata percepção de padrões, pressão emocional e aprendizado com feedback ruidoso. A ideia operacional aproveitável é separar qualidade da decisão e resultado: uma decisão consistente pode perder, uma decisão arbitrária pode ganhar. A psicologia melhora execução de um processo; não demonstra vantagem estatística (PDF 363–365, 382–384, 391–392).

A comparação entre P&L nominal e P&L dividido pelo risco inicial mostra como sizing pode ocultar a qualidade das entradas. São métricas diferentes; nenhuma substitui automaticamente a outra. O exemplo usa teste t e seleção de subgrupos. Na aplicação ao projeto, é necessário considerar dependência temporal e seleção múltipla; procurar o melhor subgrupo depois de olhar os resultados é uma nova hipótese exploratória (PDF 406–410).

Os gráficos de controle usam médias e dispersões **defasadas**, calculadas até o período anterior. Incluir o resultado extremo de hoje na própria faixa usada para julgá-lo dilui o alerta. As bandas são descritivas; o autor adverte que normalidade não deve ser presumida (PDF 411–413).

## O que levar à pesquisa

Prioridades: failure test com nível fixado antes da barra; pullback após impulso condicionado à escala superior encerrada; comparação de níveis reais com placebos; estudo do prazo de resposta e dos custos. Registrar tentativas frustradas e reentradas como parte da mesma sequência econômica. As definições quantitativas estarão no protocolo de pesquisa, explicitamente marcadas como adaptações nossas.

Não derivar do livro: taxa de acerto garantida, retorno projetado para BTC, leitura de intenção institucional, classificação retrospectiva de regimes ou aprovação de operar. Permanecem fora da revisão detalhada diversos exemplos intermediários, a totalidade do material de relações entre mercados e partes dos capítulos psicológicos e apêndices.
