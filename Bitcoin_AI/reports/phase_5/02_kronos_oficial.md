# 02 — Implementação oficial, licença e pré-treinamento

O [repositório oficial do Kronos](https://github.com/shiyu-coder/Kronos) usa licença MIT. A configuração escolhida é Kronos-mini, com 4,1 milhões de parâmetros, contexto máximo 2.048 e tokenizer Kronos-Tokenizer-2k. Os pesos públicos também declaram [licença MIT](https://huggingface.co/NeoQuasar/Kronos-mini).

O [artigo oficial](https://arxiv.org/abs/2508.02739) descreve mais de 12 bilhões de barras, 45 mercados e sete granularidades. A tabela de dados informa Binance com 997 ativos, aproximadamente 1,237 bilhão de observações, barras de um minuto a semanal e início em 31/01/2021. O artigo afirma que o pré-treinamento termina em junho/2024.

Consequência: BTCUSDT e as linhas exatas usadas não são identificados, mas existe risco material de que o trecho local outubro/2023–junho/2024 tenha participado do pré-treinamento. Ele não pode sustentar alegação de zero-shot independente. O fine-tuning exportado começa em julho/2024 e a avaliação ocorre em abril–junho/2026. Mesmo assim, a validação já serviu à Fase 4 e permanece exploratória.

A API oficial produz caminhos estocásticos e retorna sua média. O notebook chama caminhos individuais, converte cada retorno previsto pela mesma regra `open previsto do primeiro passo → close previsto do horizonte` e estima P(baixa, empate, alta) com suavização declarada. Assim a log loss é calculável sem fingir que uma previsão pontual é uma distribuição probabilística.
