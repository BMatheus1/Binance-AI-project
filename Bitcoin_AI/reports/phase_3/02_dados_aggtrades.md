# 02 — Dados oficiais de AggTrades

Foram ingeridos 11,539,776 AggTrades oficiais em 14 arquivos diários, de 01 a 14/10/2026, totalizando 20,160 minutos observados. Cada ZIP e `.CHECKSUM` foi preservado, e cada SHA-256 foi conferido antes da ingestão.

O processamento é incremental em partes Parquet. IDs duplicados, regressões, gaps de aggregate ID, gaps de IDs subjacentes e lacunas de minutos são contabilizados por dia e nas fronteiras diárias em `data/phase_3/manifests/ingestion.json`. Não há preenchimento sintético de lacunas.

O processamento do piloto foi tecnicamente viável. A expansão para 30–90 dias não foi executada nesta data porque ainda não existem 30 dias completos posteriores a setembro/2026; recuar o início reutilizaria o teste final já consumido. A ampliação deve ocorrer prospectivamente quando o período existir.
