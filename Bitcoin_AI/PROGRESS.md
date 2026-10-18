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
