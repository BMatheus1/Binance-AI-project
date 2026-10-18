# J — Conclusões e pendências

- 1m: xgboost, accuracy 50.6549%, log loss 0.809687; baseline frequência 0.861573. IC95% da diferença pareada de log loss: [-0.072525, -0.033281]. Valor negativo favorece modelo. Decisão congelada: abstenção integral.
- 5m: xgboost, accuracy 51.6876%, log loss 0.717344; baseline frequência 0.729788. IC95% da diferença pareada de log loss: [-0.024622, -0.003589]. Valor negativo favorece modelo. Decisão congelada: abstenção integral.

Validação técnica: 43 testes passaram, sem falhas ou pulos (`tests.xml`). Os 40 originais de dados/livros têm hashes inalterados (`originals_preserved.json`). Os resultados medem previsão direcional neste histórico, não rentabilidade real. Os intervalos reamostram dias; dependência entre dias e múltiplas comparações limitam a interpretação. O teste final de julho–setembro/2026 foi consumido; mudanças de estratégia precisam de outro período futuro para nova avaliação independente.

## Entregue

Pipeline local auditável, originais preservados, processamento mensal com cache,37 features catalogadas, alvos separados, 14 candidatos por horizonte (4 baselines,7 grupos de logística,RF,XGBoost,CatBoost), calibração, seleção cronológica, dois folds adicionais, artefatos versionados, inferência auditável, simulações separadas e testes adversariais. Nenhuma execução financeira integrada.

## Pendências explícitas

- Interpretação integral ainda pendente. O estudo posterior concluiu o OCR de Brooks/Nison e produziu quatro dossiês, síntese, protocolo e 16 hipóteses não testadas: [estudo e cobertura](../knowledge/study/README.md). O arquivo Aronson termina no capítulo 6; Brooks é suplemento de audiobook. Revisão da tradução e da edição/conteúdo de Nison permanece necessária.
- Autenticar ZIPs com checksums oficiais, ausentes no material recebido.
- Ampliar walk-forward para todos os algoritmos e corrigir múltiplas hipóteses antes de classificar alguma como validada.
- Treinar com todos os minutos do treino se houver recursos; esta execução usa amostragem temporal determinística.
- Obter dados de execução para investigar liquidez, latência e restrições reais de Spot.
- Monitorar deterioração com novos rótulos e revisar drift; PSI é diagnóstico, não troca automática de modelo.
- Testar novas mudanças em dados posteriores ao período final já observado.

Notícias, streaming e promoção de modelos permanecem interfaces/etapas futuras; não foram ativados.
