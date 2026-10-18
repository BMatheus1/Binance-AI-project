# Arquitetura implementada

`phase6_news.py` contém os contratos de fonte e evento, parser RSS/Atom limitado, classificador conservador, detecção de instruções maliciosas, SQLite com deduplicação/revisões, rate limiting, retries e scheduler sem sobreposição.

`phase6_trading.py` contém snapshots tipados, filtro de elegibilidade, cálculo explícito de custos, ranking de ativos, risco independente, duração, prorrogação, paper broker, adapter Binance Demo, ledger geral e avaliação pareada.

`phase6.py` compõe três coletores públicos reutilizados, o serviço de notícias e os componentes operacionais. Importar o módulo não inicia rede nem ordens. `scripts/run_phase6.py` fornece comandos explícitos.

`Phase6DecisionEngine` avalia A e B no mesmo snapshot, registra todas as oportunidades e abstenções em um único registro encadeado e, somente quando construído explicitamente com `mode="paper"`, encaminha a melhor oportunidade B aprovada pelo risco ao broker local. A Binance Demo não faz parte dessa rota automática.

Fluxo:

```mermaid
flowchart LR
  M[Mercado público BTC/ETH/SOL] --> Q[Qualidade e microestrutura]
  N[RSS oficiais / 120 s] --> C[Classificador estruturado]
  C --> E[(Event Store)]
  Q --> A[Política A sem notícias]
  Q --> B[Política B com notícias]
  E --> B
  A --> S[Seletor de ativos]
  B --> S
  S --> R[Risk Manager]
  R --> O[Observação]
  R --> P[Paper local]
  R -. habilitação explícita .-> D[Binance Demo]
  O --> L[(Ledger imutável)]
  P --> L
  D --> L
```
