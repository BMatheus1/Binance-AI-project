# Licenças dos modelos NLP

| Modelo | Revisão verificada | Licença dos pesos | Uso na Fase 6.1 |
|---|---|---|---|
| Qwen/Qwen3-0.6B | c1899de289a04d12100db370d81485cdf75e47ca | Apache-2.0 | Primário, instalado localmente |
| ProsusAI/finbert | 0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031 | CC-BY-NC-SA-4.0 | Experimental, desabilitado, não instalado |
| cardiffnlp/twitter-roberta-base-sentiment-latest | 3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7 | CC-BY-4.0 | Baseline opcional, desabilitado, não instalado |

O Qwen3 foi conferido no cartão oficial e no arquivo LICENSE do snapshot. Apache
2.0 permite uso, modificação e distribuição comercial, com preservação da licença,
avisos de atribuição e indicação de alterações quando aplicável. O projeto não
redistribui os pesos.

O FinBERT não é dependência operacional porque seus pesos restringem uso comercial.
A licença Apache 2.0 do repositório de código não substitui a licença dos pesos e dos
datasets. O Cardiff permite uso comercial sob CC BY 4.0, exige atribuição e foi
treinado em tweets; sua adequação a notícias financeiras ainda não foi validada.

Fontes oficiais consultadas:

- https://huggingface.co/Qwen/Qwen3-0.6B
- https://huggingface.co/Qwen/Qwen3-0.6B/blob/main/LICENSE
- https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest
- https://huggingface.co/ProsusAI/finbert

