# Plano e registro de execução

## Auditoria anterior ao treinamento

Recebidos 42 arquivos (195.985.098 bytes): 36 ZIPs BTCUSDT 1m de 2023-10 a 2026-09, 4 PDFs, README e .gitignore. Nenhum código ou configuração preexistente. Livros estão em `data/knowledge/books`; serão mantidos lá. Dependências Python já instaladas. PDFs Nison sem texto inicial, Brooks suplemento de audiobook e Aronson tradução automática exigem limitações explícitas.

## Fases e critérios

- A: inventário, SHA256 dos originais, inspeção de arquivos e dependências antes do treinamento.
- B: classificação determinística, referências por página PDF e hipóteses sem alegações de rentabilidade.
- C: CRC/checksum quando disponível, esquema 12 colunas, UTC ms/us, OHLC/volumes, duplicatas, lacunas; falhas críticas impedem treino. Parquet mensal incremental.
- D: features causais com reset em lacunas, escalas fechadas 5/15/30/60 minutos e catálogo; targets em arquivos separados.
- E: piloto cronológico; baselines, regressão logística, Random Forest, XGBoost e CatBoost; normalização e seleção só no treino, calibração separada, escolha só em validação. Teste final 2026-07 a 2026-09, congelado antes de abri-lo.
- F: walk-forward, ablação, permutation importance, métricas por regime, intervalos por blocos temporais, decisão com abstenção; payout e Spot separados, sem martingale.
- G: testes adversariais, documentação e relatórios A–J com resultados reais e pendências.

## Arquitetura

`src/btc_research`: audit, knowledge, ingestion, features, labeling, validation, models, training, decision, backtesting, inference, external e CLI. Catálogo acompanha fórmulas e fontes. Saídas em data/{processed,features,targets}, knowledge/, models/ e reports/. Configuração em configs/research.json. Sem API de execução, autenticação ou interface web.

## Estado

Execução inicial concluída em 17/10/2026, com limitações explícitas; não se declara cumprimento integral de itens ainda pendentes.

- A: concluída. Inventário em reports/A_audit.json e relatório legível. SHA256 final confirma 36 ZIPs e 4 PDFs intactos; README original copiado para docs/README_original.md.
- B: classificação determinística, catálogo de 37 variáveis e indexação dos quatro PDFs. Estudo posterior concluiu OCR de Brooks/Nison e ampliou leitura temática: `knowledge/study/README.md`. Revisão interpretativa integral ainda pendente; materiais Brooks/Aronson não contêm os livros integrais.
- C: concluída. 1.578.240 candles, sem lacunas, duplicatas ou erros críticos. Parquet mensal; hashes, CRC e validações registrados. Checksums oficiais ausentes.
- D: concluída. Features causais e targets separados em 36 partições. Testes de modificação futura, agregações fechadas, lacunas e equivalência entre partições passaram.
- E: concluída para a amostragem configurada. Piloto de outubro/novembro de 2023 e execução ampla com 14 candidatos por horizonte. Até 6.000 amostras por mês no treino; blocos completos de calibração, validação e teste. Dois folds walk-forward adicionais para logística/frequência. XGBoost escolhido em ambos os horizontes exclusivamente na validação.
- F: concluída na extensão documentada. Regimes, ablações, importância por deslocamentos, ICs diários, drift PSI e cenários separados. Política selecionada: abstenção integral em ambos os horizontes. Não há evidência suficiente para autorizar sinais pela regra pré-definida.
- G: concluída. 43 testes passaram; relatórios A–J e metadados gerados. Teste final consumido uma única vez. Sem ordens reais ou integração autenticada.

## Evidências e resultados

Execução final: `20261017T174250393322Z-research`. Teste julho–setembro/2026: 132.469 previsões de 1 minuto, accuracy 50,6549%; 132.465 de 5 minutos, accuracy 51,6876%. Log loss do modelo inferior à frequência histórica em ambos; isso não equivale a rentabilidade. Política congelada gerou zero operações hipotéticas.

Um primeiro piloto parou ao serializar o parâmetro NaN do XGBoost. A representação desse parâmetro foi corrigida antes de repetir o piloto com sucesso e antes do treinamento final. Não houve exposição do teste final nessa correção.

## Pendências e próximas etapas

Consulte reports/J_conclusions.md: completar revisão interpretativa dos livros e tratar material ausente, autenticação externa dos ZIPs, correção por múltiplas hipóteses, walk-forward dos demais algoritmos, treino sem amostragem se viável, dados de execução realista e avaliação de deterioração em novos períodos. Notícias e streaming estão preparados por contratos, sem coleta. Nenhuma hipótese foi promovida a validada apenas por melhoria isolada.

## Estudo aprofundado — continuação em 17/10/2026

Quatro dossiês, síntese comparativa, protocolo proposto e 16 hipóteses não testadas em `knowledge/study/`. Extração em 1.308 páginas; OCR local concluído em 528; registro de passagens analisadas em 324 páginas e inspeções visuais em 20 páginas (contagens podem se sobrepor). Isso não é leitura integral. `coverage.json` separa processamento, passagens e visualização e lista páginas ainda sem revisão registrada. `preservation.json` confirma novamente os 40 originais inalterados. Nenhum retreinamento ou avaliação do teste final ocorreu nesta etapa.

## Fase 2 — diagnóstico e otimização controlada

Concluída em 17/10/2026 como validação interna exploratória. Foram adicionadas 17 features contextuais em módulo separado, três folds walk-forward para sete candidatos, análise de erros, permutação das 37 features, ablação por categoria, calibração, Holm e cenários econômicos. Até 3.000 observações por mês controlaram CPU/memória; julho–setembro/2026 não foi carregado.

O XGBoost contextual teve mudança de log loss de -0,000056 em 1m contra o XGBoost original e +0,000785 em 5m, nos mesmos folds. Nenhum limiar econômico satisfez os critérios predefinidos. A política permanece em abstenção integral. Consulte `reports/phase_2/README.md`.

## Fase 3 — microestrutura e validação prospectiva

Concluída em 17/10/2026 com plano congelado antes da aquisição. Foram autenticados pelos checksums oficiais e processados incrementalmente 11.539.776 AggTrades BTCUSDT Spot de 01–14/10/2026, gerando 20.160 minutos completos e 20 features causais. Não houve duplicatas nem gaps de IDs ou minutos.

A–D usaram o mesmo XGBoost, treino, calibração, validação e purga. Em 1m, a variante selecionada apenas para observação reduziu a log loss de 0,768756 para 0,767187, sem ganho de accuracy. Em 5m, o XGBoost original venceu; acrescentar microestrutura piorou a log loss em 0,000865. Todos os cenários Spot foram negativos e os resultados positivos isolados de payout não têm intervalo diário confiável. A política permanece em abstenção integral.

O coletor público foi validado por 15 segundos com 430 mensagens e livro sincronizado. Ledger imutável, observador prospectivo, paper trading com bid/ask, custos, drawdown e parada, filtro macro e testes foram implementados. Nenhum serviço fica ativo e nenhuma ordem real é possível por esses módulos. Consulte `reports/phase_3/README.md`.

## Fase 4 — horizontes e validação prospectiva

Concluída em 18/10/2026. A definição do alvo, classes, log loss, baselines, calibração, distribuição das probabilidades e barreiras contra leakage foi reauditada. O teste final consumido de julho–setembro/2026 permaneceu bloqueado. O treino, calibração e validação usaram somente períodos anteriores a julho, com purga de 30 minutos e as mesmas linhas para todos os candidatos de cada horizonte.

Execução congelada: `20261018T013856021255Z-phase4`. XGBoost foi selecionado apenas para shadow em 1/5/15m e CatBoost em 30m. A diferença média de log loss contra a frequência foi -0,022185, -0,001886, -0,001852 e -0,001705, respectivamente; os IC95% diários ficaram abaixo de zero. Isso representa ganho probabilístico pequeno, não prova econômica.

Nenhum cenário Spot apresentou expectativa com limite inferior positivo após custos. Alguns cenários de payout fixo em 5/15/30m passaram o filtro dentro da própria validação, portanto permanecem exploratórios e não foram promovidos. A política congelada continua em abstenção integral.

O observador público foi corrigido para gravação em lote e alinhamento de relógio. No ensaio final de 130 segundos recebeu 6.244 mensagens, sem reconexões, gaps de AggTrade ou invalidações do book. Dois candles produziram oito previsões válidas e zero abstenções técnicas novas; todas foram abstidas pela política. O atraso interno mediano foi 0,227 ms e p95 0,744 ms. O ledger acumulou 28 previsões e quatro resultados, insuficientes para conclusão prospectiva. Foram executados 63 testes com sucesso. Consulte `reports/phase_4/README.md`.

## Fase 5 — Kronos no Google Colab

Preparação concluída em 18/10/2026. A implementação oficial foi fixada por commit, assim como Kronos-mini e Kronos-Tokenizer-2k por revisão. O artigo informa pré-treinamento Binance até junho/2024; por isso o treino local começa em julho/2024, sem alegar independência zero-shot para o trecho histórico potencialmente sobreposto.

O exportador produziu candles OHLCVA de treino, calibração e validação, mais 128 decisões de calibração e 256 decisões compartilhadas com XGBoost/CatBoost. Julho–setembro/2026 não foi exportado. O notebook exige GPU, executa primeiro inferência pré-treinada, faz smoke de um passo e deixa o experimento completo atrás de uma opção explícita. O importador verifica hashes, revisões, instantes, alvos, retornos e preços antes de calcular métricas e cenários econômicos.

O smoke local real carregou tokenizer e pesos, gerou duas barras futuras e realizou um passo AdamW finito com alteração dos parâmetros. O smoke também foi executado no Colab com Tesla T4 e importado pelo pipeline local, confirmando a ida e volta de hashes, previsões e checkpoint. Isso validou o caminho técnico sem medir capacidade preditiva. Após corrigir a compatibilidade de timestamps entre Parquets do Colab e locais, foram executados 71 testes com sucesso.

O experimento completo foi posteriormente importado com 4.096 previsões, quatro variantes e 256 decisões comuns por horizonte. O Kronos pré-treinado calibrado foi a melhor variante, porém sua log loss foi superior à Fase 4 em 1/5/15/30m. O fine-tuning de 500 passos piorou ligeiramente a variante calibrada em todos os horizontes. Todos os cenários Spot foram negativos após custos. Um resultado positivo de payout fixo em 15m apareceu em três limiares equivalentes da mesma política raw, no bloco exploratório já consumido e sem correção por múltiplas comparações; não foi promovido. A abstenção integral permanece.

## Fase 6 — multiactivos e inteligência de notícias

Base de engenharia implementada em 18/10/2026. O universo foi congelado em BTCUSDT, ETHUSDT e SOLUSDT. O coletor público da Fase 3 foi composto em três instâncias independentes. Foram adicionados RSS oficiais do Federal Reserve, SEC e BLS, scheduler de 120 segundos, rate limiting, retries, deduplicação, revisões e event store causal.

O classificador conservador produz eventos estruturados, marca prompt injection como conteúdo não confiável e não possui acesso a execução. As políticas A sem notícias e B com notícias recebem os mesmos instantes; inicialmente, notícias só podem acrescentar contexto e veto de risco, pois o ajuste direcional não foi calibrado. Seleção de ativos usa expectativa líquida após spread, taxas e slippage.

Gerenciamento de risco independente cobre exposição, posições, perda diária, drawdown, correlação, spread, liquidez, falha de dados, kill switch e duração. A extensão é limitada a três minutos, apenas com lucro líquido positivo, e o limite absoluto é 23 minutos. Paper broker e ledger encadeado foram implementados.

O adapter Binance Spot Demo aceita somente `demo-api.binance.com`, permanece desabilitado e distingue ordem pendente, parcial, executada e rejeitada. Nenhuma credencial, autenticação ou ordem foi usada nesta entrega. Endpoints reais são rejeitados sem fallback.

Um ciclo público persistiu 45 eventos do Federal Reserve e SEC. O BLS respondeu HTTP 403 e permaneceu sem dados; a falha foi isolada. Um smoke multiactivos de 15 segundos recebeu 1.116 mensagens com os três livros sincronizados, sem reconexões, gaps ou invalidações. Nenhum processo ficou ativo. Não existe resultado econômico da Fase 6. O protocolo requer dados futuros e mantém abstenção integral. Consulte `reports/phase_6/README.md`.

## Fase 6.1 — Deep Learning financeiro e execução persistente

Concluída tecnicamente em 18/10/2026 para observação local. Qwen3-0.6B foi fixado
na revisão c1899de289a04d12100db370d81485cdf75e47ca, baixado e verificado sob
Apache 2.0. O smoke real carregou 2.384.199.680 bytes de parâmetros em CPU e
produziu resposta estruturada válida em 70,1 segundos. O resultado permaneceu
insuficiente e não gerou ordem.

FinBERT foi isolado e desabilitado por incompatibilidade com uso comercial. Cardiff
foi registrado como baseline opcional CC BY 4.0, com atribuição obrigatória e
limitação de domínio. Nenhum dos dois foi instalado.

As políticas A, B, C e D foram implementadas nas mesmas observações. C usa Qwen3
somente como veto; D também exige confirmação quantitativa posterior ao recebimento.
Falha, timeout, injeção ou informação insuficiente causa abstenção.

O supervisor completou dois ciclos de notícias com intervalo de 120 segundos,
seis fontes configuradas, 75 eventos no SQLite, heartbeat, logs rotativos e nenhuma
falha. A suíte completa passou com 123 testes e compileall. Nenhuma ordem real,
demo ou paper nova foi enviada. Validação econômica continua pendente por pelo
menos 30 dias e 200 operações resolvidas por política. Consulte
reports/phase_6_1/README.md.

## Fase 6.4 — trading autônomo supervisionado Demo

Implementação técnica preparada em 19/10/2026. O supervisor agora reinicia workers
que terminem inesperadamente; o worker de decisões tolera falha de recomposição REST
e tenta novo warmup sem descartar o candle recebido. O protocolo de 24 horas começou
em `2026-10-19T13:48:18Z` e permanece em andamento. A Binance Demo estava
indisponível no início da janela, fato preservado nas amostras, sem fallback para
produção e sem envio de ordens.

Foi criada uma política BTC quantitativa experimental de 10 USDT, com parâmetros
congelados, autorização por sessão e por `boot_id`, reconciliação, diário de ordens,
posição persistente e saídas por prazo, stop, invalidação e kill switch. A categoria
economicamente validada continua bloqueada; nenhuma expectativa desconhecida foi
preenchida. A suíte completa passou com 162 testes e o frontend compilou a rota
`/autonomous`. Nenhuma operação autônoma Demo foi autorizada ou enviada.
