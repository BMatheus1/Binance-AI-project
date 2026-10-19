# Publicação independente da política A

Em 19/10/2026, a sessão Demo estava autorizada, mas o último forecast BTC de 5 minutos era antigo. O heartbeat mostrou o worker em `analyzing`, Qwen em CPU e fila de candles acumulando. O método `FourPolicyEngine.evaluate()` aguardava `_neural_scores()` antes de publicar inclusive a política A, que não utiliza notícias.

Foi criado um caminho independente para a mesma política A: outro consumidor dos eventos públicos Demo, com fila, candles fechados, warmup e executor próprios. Ele carrega os mesmos artefatos congelados, calcula as mesmas probabilidades e utiliza o mesmo `AssetSelector`. O Qwen continua disponível no worker das políticas B/C/D.

A política A é gravada no SQLite de avaliações existente e em `quantitative_ledger.jsonl`, separado do ledger do worker de notícias para evitar escrita concorrente no hash chain. O ID do ciclo permanece comum por candle, mantendo a associação entre observações. O worker lento não publica outra previsão A atrasada e não registra outcomes retrospectivos para esse caminho. Novas outcomes são criadas pelo worker quantitativo no instante em que ele publica a previsão.

Heartbeat: `decision_worker` identifica o caminho quantitativo e `news_decision_worker` identifica o caminho das notícias. O status do Qwen continua vindo da instância que efetivamente o utiliza. Diferenças de disponibilidade entre esses componentes ficam explícitas.

Nenhum modelo, feature, limiar, custo, regra financeira ou horizonte foi ajustado. BTCUSDT, probabilidade mínima de alta de 60%, janela de 5 minutos, teto de 10 USDT e limites de risco permanecem congelados. Esse ajuste elimina uma dependência de agendamento; não cria uma garantia de lucro nem um sinal de entrada.

Testes verificam igualdade entre a política A publicada no caminho completo e no caminho independente, ausência de acesso a notícias/Qwen na avaliação A e gravação no SQLite com o caminho de notícias indisponível. O protocolo prospectivo e os registros históricos permanecem preservados.
