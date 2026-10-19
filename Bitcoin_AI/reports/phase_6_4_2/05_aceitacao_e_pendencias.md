# Aceitação e limites da entrega

Não declarar a Fase 6.4.2 integralmente concluída ou uma estratégia lucrativa com base na consolidação técnica.

## Implementado

- Interface operacional central tipada, persistida e ligada ao executor existente, sem fallback para decisões antigas.
- Pipeline único de mercado, features e modelos; especialistas de notícias reaproveitam seu snapshot em execução separada.
- Continuidade do acompanhamento de posições quando o modelo quantitativo não puder carregar; bloqueio de novas propostas.
- RiskManager independente, verificação de versão congelada, disponibilidade temporal e revalidação antes de ordens.
- Preço bid/ask para verificações executáveis, registro do plano antes da compra e resíduos explicitados na saída.
- Dashboard integrado, painel central em pt-BR, políticas antigas em área avançada, cache de saldo e indicadores corrigidos.
- Preparação de sessão pelo navegador com as mesmas regras da CLI; autorização continua local.
- Eventos com IDs e timestamps, observação prospectiva preservada, backup de bancos/logs e manifestos de hashes.
- Fórmulas causais de padrões e utilitários de saídas/resultado líquido, isolados de execução até validação.
- Comparação descritiva reproduzível entre Kronos e especialistas em observações alinhadas; teste integrado com execução fictícia em memória.

## Ainda não demonstrado / não promovido

| Critério | Situação e evidência necessária |
|---|---|
| Fusão superior validada temporalmente | Não demonstrada. Fusão não ativada; faltam OOFs alinhadas, blocos separados de calibração/seleção e teste futuro independente |
| Notícias, microestrutura ou regime acrescentam lucro | Não demonstrado. Comparações anteriores e ablações funcionais não substituem previsões OOS pareadas |
| Padrões economicamente úteis | Descrições causais registradas; expectativa, frequência OOS e risco-retorno sem validação suficiente |
| Saídas adaptativas superiores | Funções testadas e não ativas; faltam comparações sobre as mesmas entradas/caminhos executáveis |
| Calibração de magnitude / probabilidade de lucro líquido | Desconhecidas. Não estimadas arbitrariamente a partir de p_up |
| Operação de ETH/SOL | Bloqueada; não há modelo transferível validado |
| Observação contínua de 24h aprovada | Consultar relatório vivo; sem antecipar tempo decorrido ou apagar lacunas |
| Lucro consistente | Não comprovado. A amostra da Demo e os diagnósticos não sustentam essa conclusão |
| Reinício automático do Windows após queda | Não implementado como serviço do sistema; supervisor recupera tarefas no processo enquanto o computador estiver ativo |
| Stop hospedado na corretora | Não adicionado; proteção continua local e depende de processo/rede |

Essas pendências não são transformadas em controles financeiros aprovados. A plataforma permanece apta à observação e a experimentos Demo limitados, após autorização específica e controles saudáveis. A decisão econômica pode continuar usando somente um especialista dentro da arquitetura unificada.
