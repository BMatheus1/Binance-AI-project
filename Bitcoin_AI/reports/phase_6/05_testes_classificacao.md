# Testes de classificação e segurança

O baseline é determinístico e conservador. Ele reconhece BTC, ETH e SOL, identifica temas macro/regulatórios/incidentes e produz saída validada. Não estima probabilidade de sucesso da operação.

Testes cobrem timestamps, item futuro, deduplicação, revisão, sentimento, associação de ativo e texto com prompt injection. Frases como “ignore as regras” ou “execute uma ordem” são marcadas como conteúdo não confiável; não há referência do classificador para qualquer método de broker.

Este baseline serve para coleta prospectiva e rotulagem. Um classificador aprendido só poderá substituí-lo após corpus, validação temporal, calibração e congelamento próprios.
