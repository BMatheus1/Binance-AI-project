# Experimento A/B com e sem notícias

Política A recebe somente estado de mercado e modelos quantitativos congelados. Política B recebe o mesmo estado e os eventos que já estavam disponíveis. Na versão inicial, notícias podem impor veto de risco; o ajuste direcional está desligado para evitar probabilidades arbitrárias.

Cada linha pareada registra as duas decisões no mesmo instante. Abstenção é contabilizada como retorno zero e permanece visível. As métricas incluem trades, abstention rate, retorno líquido, expectativa, taxa de acerto, ganho/perda média, profit factor e drawdown. A métrica primária é `retorno_B − retorno_A`, com custos idênticos.

Não há resultado econômico nesta entrega: a coleta prospectiva ainda não foi iniciada. O avaliador sempre retorna `prospective_claim_allowed=false` até existir protocolo estatístico completo sobre dados futuros.
