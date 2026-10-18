# 00 — Plano congelado da Fase 4

Data de congelamento: 17/10/2026. Nenhum dado posterior foi consultado para definir este plano.

## Fronteiras temporais

- Treino: início disponível até 31/12/2025, amostrado em no máximo 3.000 observações por mês.
- Calibração: 01/01–31/03/2026, completa.
- Validação e seleção exploratória: 01/04–30/06/2026, completa.
- Julho–setembro/2026: teste final já consumido na Fase 1; proibido nesta fase.
- Observação prospectiva: inicia somente depois do congelamento dos modelos da Fase 4 e não será reutilizada para seleção.

## Experimentos

Horizontes de 1, 5, 15 e 30 minutos, todos com a convenção `next_open`: após o candle encerrado em `t`, entrada aproximada no `open[t+1]` e saída no `close[t+h]`. Classes: baixa, empate e alta, com tolerância zero. Modelos: frequência, uniforme, regressão logística, XGBoost e CatBoost. Os hiperparâmetros permanecem nos construtores já testados; não haverá busca extensa.

## Critério econômico

Limiar, payout e custos são os valores pré-declarados em `configs/phase_4.json`. Cenários Spot e payout são separados. Um resultado positivo na validação continua exploratório porque o mesmo bloco participa da comparação dos modelos. A política só poderia sair da abstenção após avaliação prospectiva independente com quantidade de sinais, dias e regimes suficientes.

## Recursos e riscos

- CPU limitada a quatro threads; alvos novos são particionados por mês e os treinos antigos são amostrados.
- Retornos maiores podem ter mais amplitude, mas também maior sobreposição serial entre rótulos.
- O bootstrap diário não elimina dependência entre dias nem corrige a multiplicidade dos modelos, horizontes, limiares e custos.
- Coleta ao vivo curta valida operação, não rentabilidade. Falta de warmup, mensagens, livro válido ou candle completo gera abstenção técnica.
- Nenhuma chave, conta financeira, ordem ou martingale faz parte da implementação.
