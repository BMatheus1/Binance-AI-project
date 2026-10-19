# Execução, risco e integração

## Decisão e execução

1. Candle fechado e sincronizado dos três ativos; somente dados disponíveis entram nas features.
2. Pesos congelados verificados; ausência/corrupção bloqueia previsões e permite que o acompanhamento de posições continue iniciando.
3. `UnifiedTradingIntelligenceEngine` produz ID, vínculo com avaliação, timestamps UTC, disponibilidade, versões, validade, incerteza, custos estimados, risco e motivos.
4. A proposta é registrada no ledger antes de tornar-se visível na tabela operacional.
5. O executor aceita apenas a tabela central e exige configuração com o mesmo hash. Revalida as condições da política e os limites antes do envio.
6. Sessão temporária vinculada ao boot, kill switch, reconciliação, mercado conectado, saldo, filtros, exposição, frequência, perdas e cooldown continuam obrigatórios. O RiskManager é consultado separadamente.
7. Posição, avaliação, decisão central, IDs das ordens e fills permanecem vinculados. Intenções são persistidas antes do envio; timeout não autoriza repetição.

Uma proposta `COMPRAR` não representa ordem enviada: `execution_state` diz que sessão e risco ainda são necessários. Em OBSERVE não há autorização implícita. O dashboard diferencia proposta, sinal de pesquisa, operação diagnóstica e operação experimental.

## Posições e finanças

O gerenciamento continua em executor exclusivo, sem dependência do frontend ou Qwen3. A consulta de stop e dimensionamento agora usa bid/ask executável de `ticker/bookTicker` no adaptador existente, em lugar de uma média móvel de preço. A consulta é estritamente no host Demo. Entradas são recalculadas pelo ask, mantendo o limite de valor e filtros; saídas respeitam o lote e persistem eventual resíduo.

A política mantém stop inicial, invalidação e prazo congelado de cinco minutos, limite absoluto e kill switch. Um alvo líquido/trailing novo exige outro experimento; não é promovido porque há uma implementação de pesquisa. O stop pode realizar prejuízo e o plano não garante preço de execução.

O resultado de caixa é receita de venda menos desembolso de compra e taxas em USDT conhecidas. Taxa de entrada em BTC reduz a quantidade vendável; não deve ser descontada duas vezes. Ativos de taxa sem conversão confiável deixam o resultado desconhecido. Resíduo BTC não vendido é registrado separadamente, sem convertê-lo em lucro realizado. A marcação bruta aberta usa bid recente; se a cotação estiver antiga, fica indisponível. O líquido aberto continua desconhecido sem estimativa confiável dos custos de saída.

## Isolamento e recuperação

Nenhum cliente de produção é criado. Allowlist de host e operações permanece no transporte; redirects são rejeitados. A nova leitura de bookTicker não habilita nenhum host adicional. Credenciais não são retornadas no dashboard ou relatórios.

Preservados: classificação de falhas transitórias de leitura, bloqueio permanente de autenticação/ordens desconhecidas/divergência de saldo, invalidação de autorização, reconciliação periódica, idempotência, lock de processo e persistência após reinício. Autorizações antigas não sobrevivem ao boot novo.

A documentação oficial foi conferida em 19/10/2026: [Binance Spot Demo](https://developers.binance.com/en/docs/products/spot/demo-mode/general-info). REST, WS API e streams utilizados correspondem aos hosts Demo publicados. A semântica das ordens segue a [API Spot](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/trade), usando exclusivamente o host Demo. Não foi acessado um endpoint de negociação real.

## Dashboard e eventos

Visão geral, Inteligência e menu lateral usam o mesmo resumo de estado real da Fase 6.4. Uma falha de atualização ou heartbeat antigo não produz estado saudável. O saldo em cache deixa de aparecer como leitura atual após falha. Saúde do mercado usa timestamps atuais.

Inteligência apresenta propostas centrais primeiro; políticas antigas e registros técnicos ficam em áreas expansíveis. Custos são identificados como estimados e expectativa desconhecida é explícita. A API de eventos e o snapshot WebSocket expõem IDs persistentes (`decision:<hash>` e `engine:<activity_id>`) e timestamps, permitindo deduplicação sem produzir novas decisões. São janelas recentes, não substitutos do histórico SQLite/ledger.

O navegador pode preparar uma sessão usando a mesma função da CLI, com sessão local, Origin e CSRF. Esse botão não libera kill switch, não autoriza ordens e não inicia negociação. Ativação permanece na CLI local. O controle existente de interrupção é preservado.

## Limitação do computador pessoal

O agente local não protege posições com o computador desligado, suspenso, sem rede ou processo encerrado. A recuperação supervisionada do serviço não garante disponibilidade do Windows. Não há novo stop hospedado na corretora implementado nesta fase; stops locais dependem do processo e da execução REST. Não encerrar os serviços com posição não reconciliada; o script de encerramento verifica isso.
