# Paper trading

O paper broker local reutilizado calcula taxas, registra abertura e fechamento e
mantém o resultado separado de qualquer diagnóstico demo. As regras permitem prazo
planejado de 1 a 20 minutos e extensão máxima de 3 minutos, somente em posição com
resultado líquido positivo e demais condições satisfeitas.

O contrafactual do fechamento original é registrado para medir o efeito incremental
da extensão. Os testes cobrem duração máxima absoluta de 23 minutos e rejeitam
configurações inválidas. Nesta conclusão não foram abertas novas operações paper;
portanto não existem métricas econômicas a relatar.

