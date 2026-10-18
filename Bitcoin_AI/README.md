# Bitcoin AI Research

Plataforma local de pesquisa quantitativa para **BTC/USDT Spot**, com previsão probabilística em **1 e 5 minutos**. Python, sem interface web, credenciais de corretora ou envio de ordens. Modelos estimam baixa, empate e alta; uma camada separada pode abster-se.

O projeto organiza dados, formaliza hipóteses, treina modelos e avalia previsões e cenários econômicos hipotéticos. Livros são fontes conceituais, nunca prova de lucratividade. Notícias e streaming são extensões futuras, ainda sem coleta ou monitoramento. O README recebido foi preservado em [docs/README_original.md](docs/README_original.md).

## Resultados e documentação

- [Relatórios A–J](reports/INDEX.md) e [conclusões/pendências](reports/J_conclusions.md).
- [Fase 2 — auditoria, walk-forward e diagnóstico econômico](reports/phase_2/README.md).
- [Plano e progresso](PROGRESS.md).
- [Catálogo de variáveis](knowledge/feature_catalog.json).
- [Conceitos e referências verificadas](knowledge/concepts/verified.md).

Métricas efetivas ficam em `reports/final_evaluation.json`. Julho–setembro/2026 é teste final, aberto uma única vez após congelar modelos e regras. A aplicação registra essa exposição e impede reutilizá-lo para validar novas escolhas.

## Executar no Windows / VS Code

Abra a pasta `Bitcoin_AI` no terminal. Python 3.11 ou superior; execução entregue testada em Python 3.14.0. Não é necessária chave de API nem conta de provedor de IA.

Para configurar outra máquina:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[boosting,dev]"
```

Nesta máquina as dependências já estavam instaladas. Para executar diretamente sem instalação editável:

```powershell
$env:PYTHONPATH = 'src'
$env:OMP_NUM_THREADS = '4'
$env:OPENBLAS_NUM_THREADS = '4'
python -m btc_research.cli audit
python -m btc_research.cli knowledge
python -m btc_research.cli ingest
python -m btc_research.cli features
python -m pytest -q --junitxml=reports/tests.xml
python -m btc_research.cli pilot
python -m btc_research.cli train
python -m btc_research.cli evaluate
python -m btc_research.cli reports
```

Use o executável da `.venv` no lugar de `python` se criou o ambiente acima. Após instalação, `btc-research ingest` equivale ao comando de módulo. Cada etapa é independente. Não remova o registro do teste para reavaliar o mesmo período: novos modelos precisam de outro período futuro independente. Relatórios existentes podem ser regenerados sem novo treinamento.

`pilot` usa outubro–novembro/2023 e não acessa o teste final de 2026. `train` seleciona modelos sem abrir o teste; `evaluate` aplica a escolha congelada. Artefatos anteriores permanecem preservados.

Dependências: NumPy, pandas, PyArrow, scikit-learn, joblib, XGBoost, CatBoost, pypdf e pytest. Versões observadas em `requirements-lock.txt` e em cada execução. Nenhuma nova dependência foi instalada durante a implementação.

## Organização

Recebidos 36 ZIPs mensais, 4 PDFs e 2 documentos. Originais preservados. Os livros permanecem no caminho real `data/knowledge/books`, definido na configuração.

```text
configs/research.json            períodos, limites, sementes e caminhos
data/raw/                       ZIPs originais, somente leitura
data/knowledge/books/           PDFs originais, somente leitura
data/processed/                 Parquet mensal e proveniência
data/features/                  37 features e disponibilidade
data/targets/                   rótulos e preços futuros separados
knowledge/references/           índice por páginas físicas dos PDFs
knowledge/concepts/             conceitos verificados e limitações
knowledge/hypotheses/           avaliações exploratórias
src/btc_research/               módulos independentes
models/trained/<run_id>/         modelos, metadados e previsões
reports/                        auditorias, experimentos e relatórios
tests/                          testes adversariais e integração
```

## Dados e esquema

Esquema e mudança para microssegundos desde 2025 conferidos na [documentação oficial Binance Public Data](https://github.com/binance/binance-public-data). O código valida mês, magnitude e datas. Tempos em UTC.

| Campo original | Significado |
|---|---|
| open_time | abertura do candle |
| open, high, low, close | preços USDT/BTC |
| volume | volume BTC |
| close_time | último instante incluído no candle |
| quote_volume | volume USDT |
| trades | quantidade inteira de negociações |
| taker_base, taker_quote | volume comprador agressor BTC/USDT |
| ignore | sem uso, retirado somente do derivado |

Cada linha processada contém `source_file` e `source_sha256`. Verificações: CRC, checksums quando fornecidos, OHLC/volumes, timestamps, duplicidades, sobreposições e lacunas. Conflitos impedem treino; duplicatas idênticas são removidas só do derivado e contabilizadas. Lacunas não são preenchidas. Os checksums oficiais não acompanharam os ZIPs; nomes e esquema não autenticam a origem.

Cache mensal associado a hashes dos arquivos e saídas. Features usam 180 candles anteriores como contexto finito; targets usam até 5 posteriores, em cálculo separado. Alterar um mês invalida partições vizinhas afetadas. Novos arquivos devem passar por ingestão e features antes de outro experimento.

## Features e alvos

Categorias: preço, Price Action, tendência, volatilidade, volume e tempo. Conhecimento/eventos têm contratos próprios. Arquivos desconhecidos seguem para revisão. O catálogo registra fórmulas, janelas, dependências, disponibilidade, origem, versão e hipóteses.

Inclui retornos, proporções dos candles, momentum, médias, RSI, MACD, ATR, volatilidade, Bollinger, intensidade/volume agressor e sazonalidade UTC. RSI usa médias simples (Cutler); ATR usa média simples; EMAs são aproximações finitas normalizadas em 60 candles. Essas variantes não equivalem a todos os indicadores recursivos de outras plataformas.

Agregações UTC de 5/15/30/60 minutos exigem todas as barras e só entram depois de fechadas. Indicadores reiniciam após lacunas. Warmup/NaN exclui a linha do modelo.

No candle `t`, informação disponível em `open_time[t]+1min`. Entrada histórica aproximada: `open[t+1]`; saída: `close[t+h]`. Retorno `r=saída/entrada-1`; classes 0 baixa, 1 empate e 2 alta. Tolerância de empate inicialmente zero, configurável. Fim do evento em `open_time[t]+(h+1)min`. Alvos que cruzam lacunas ou não têm futuro completo ficam ausentes. Preços futuros nunca são features.

O próximo open é aproximação idealizada, sem latência de recebimento/decisão/envio. Mudar essa convenção requer implementar outra variante; configurações desconhecidas são rejeitadas.

## Treinamento e validação

14 candidatos por horizonte: frequência histórica, constante, momentum, reversão; logística em 7 grupos de variáveis; Random Forest, XGBoost e CatBoost. O aprendizado usa features numéricas de dados reais, não os textos dos livros.

| Bloco | Datas nominais |
|---|---|
| Treino | outubro/2023–dezembro/2025 |
| Calibração | janeiro–março/2026 |
| Validação/seleção | abril–junho/2026 |
| Teste final | julho–setembro/2026 |

Treino: até 6.000 posições igualmente espaçadas por mês, sem embaralhamento entre conjuntos. Calibração, validação e teste: todos os minutos elegíveis. Purga pelo fim do rótulo e embargo de 5 minutos. Dois folds walk-forward anteriores a 2026 avaliam logística e frequência.

Variáveis constantes/redundantes (correlação absoluta >0.98), scaler e estimador são ajustados só no treino. Calibração multiclasse ajusta regressão sobre log-probabilidades em bloco posterior independente. Escolha por menor log loss na validação, permitindo que um baseline vença.

Métricas: accuracy, precisão/recall/F1 macro, matriz de confusão, AUC quando cabível, log loss, Brier multiclasse, calibração, métricas mensais/regimes e cobertura seletiva. ICs usam bootstrap de dias inteiros; não corrigem dependência entre dias ou multiplicidade. Importância usa deslocamentos circulares na validação por variável/grupo, sem inferência causal. SHAP não foi necessário.

Semente 42, 4 threads. Parâmetros, hashes, versões, datas e features em `development.json`. Inferência auditável em `inference.predict_closed_candles`. Só carregue joblib de fonte local confiável; arquivos de terceiros podem executar código ao serem desserializados.

## Decisão e backtesting

Limiar entre 0.55/0.58/0.60/0.65 é escolhido somente na validação. Exige probabilidade suficiente, expectativa positiva no payout de referência, pelo menos 200 trades e limite inferior positivo no IC diário. Sem candidato elegível, abstenção integral. Isso não demonstra validade contratual ou financeira.

Payouts 70/80/90% são hipóteses separadas: stake fixo 1, empate reembolsado, perda 1 no erro. Spot apenas compra, sem venda descoberta, com notional fixo de 1 USDT como unidade de cálculo. Custos agregados (taxa/spread/slippage) de 5/10/20 bps por lado. OHLCV não informa execução, fila, liquidez, lote/tick/minNotional; não é uma ordem executável de 1 USDT. Spot reutiliza a política direcional conservadora congelada, não um otimizador de retorno Spot.

Uma posição por vez, limite de perda diária 10 unidades e drawdown 30; sem martingale. Sensibilidades do teste são descritivas e não alteram escolhas. O pipeline fornece ao simulador previsões fora da amostra de treino.

## Evolução e limites

Novos dados passam pela mesma validação e experimento versionado. PSI compara distribuições com referências do treino; não promove modelos. Deterioração supervisionada e gestão operacional champion/challenger ficam para evolução posterior.

`external.py` define fontes futuras de candles e eventos, incluindo publicação e recebimento. Ambas devem anteceder o uso. Nenhum serviço ou monitor é iniciado.

Não publicar datasets, livros ou credenciais. O `.gitignore` cobre os originais e artefatos grandes. A leitura contextual dos livros foi parcial; consulte todas as pendências do relatório J antes de considerar a fase integralmente concluída.
