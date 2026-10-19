# Mercados e tempo real

A página de mercados usa candles e microestrutura armazenados pelo coletor existente para BTCUSDT, ETHUSDT e SOLUSDT. A idade do último dado é apresentada e dados antigos recebem estado `stale`.

O WebSocket do dashboard transmite snapshots locais. Ele não envia ordens e não substitui os WebSockets de coleta de mercado.
