# 00 — Plano congelado da Fase 5

O Kronos é avaliado como challenger opcional. Nenhum resultado altera automaticamente XGBoost, CatBoost ou a política de abstenção integral.

- Implementação oficial fixada no commit `67b630e67f6a18c9e9be918d9b4337c960db1e9a`.
- Modelo: `NeoQuasar/Kronos-mini` na revisão `f4e68697d9d5aed55cef5c96aabc3376bcad9f81`.
- Tokenizer compatível: `NeoQuasar/Kronos-Tokenizer-2k` na revisão `26966d0035065a0cae0ebad7af8ece35bc1fb51c`.
- Fine-tuning: somente predictor, tokenizer congelado, uma configuração predefinida e nenhuma busca de hiperparâmetros.
- Treino local: 01/07/2024–31/12/2025; calibração: 01/01–31/03/2026; comparação: 01/04–30/06/2026.
- Julho–setembro/2026 permanece proibido porque já foi consumido na Fase 1.
- 128 decisões igualmente espaçadas para calibração e 256 para comparação, compartilhadas entre os quatro horizontes.
- Inferência: contexto 512, horizonte 30, temperatura 0,6, top-p 0,9 e 16 caminhos; suavização Dirichlet 0,5.
- Custos, payouts, limiares, alvos e convenção `next_open` permanecem os da Fase 4.

Os números obtidos no smoke validam somente instalação, inferência e gradiente. Métricas preditivas só existem depois que o notebook exportar previsões reais e o importador local aceitar o pacote.
