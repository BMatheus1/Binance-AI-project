# 04 — Smoke local real

O ambiente local carregou os pesos públicos fixados de Kronos-mini e Kronos-Tokenizer-2k com PyTorch 2.10.0 CPU. Uma inferência com 64 candles produziu duas barras futuras finitas. Em seguida, um passo AdamW do predictor sobre uma janela de dezembro/2025 produziu loss `2,93847393989563`, finita, e alterou os parâmetros.

Esse ensaio confirma compatibilidade de código, pesos, tokenizer, inferência e retropropagação. Ele não é uma avaliação de accuracy, log loss ou rentabilidade, e nenhum checkpoint local do smoke é candidato a modelo.
