"use client";

import { useState } from "react";
import { useDashboard } from "@/components/dashboard-provider";
import { MarketChart } from "@/components/market-chart";
import { EmptyState, MetricCard, StatusBadge, formatDate, formatNumber } from "@/components/ui";

export default function MarketsPage() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const { snapshot } = useDashboard();
  const market = snapshot?.markets[symbol];
  return <div className="page-stack">
    <section className="page-heading"><div><span className="eyebrow">DADOS ARMAZENADOS · BINANCE DEMO</span><h1>Mercados</h1><p>Candles, volume e microestrutura recebidos pelo coletor existente.</p></div><div className="market-tabs">{["BTCUSDT","ETHUSDT","SOLUSDT"].map((item) => <button className={symbol === item ? "active" : ""} key={item} onClick={() => setSymbol(item)}>{item.replace("USDT", "/USDT")}</button>)}</div></section>
    {market ? <><section className="panel"><div className="market-header"><div><span className="eyebrow">{market.symbol}</span><div className="market-price">{formatNumber(market.price, 8)}</div><span className={market.change_percent_1m != null && market.change_percent_1m >= 0 ? "positive" : "negative"}>{market.change_percent_1m == null ? "Variação sem dados" : `${market.change_percent_1m >= 0 ? "+" : ""}${formatNumber(market.change_percent_1m, 4)}% · último candle fechado`}</span></div><StatusBadge state={market.stream_state === "connected" ? "good" : "warn"} label={market.stream_state === "connected" ? "Stream recente" : "Dados armazenados / desatualizados"} /></div><MarketChart market={market} /></section>
      <section className="metrics-grid"><MetricCard label="Bid" value={formatNumber(market.bid, 8)} /><MetricCard label="Ask" value={formatNumber(market.ask, 8)} /><MetricCard label="Spread" value={market.spread_bps == null ? "Sem dados" : `${formatNumber(market.spread_bps, 4)} bps`} /><MetricCard label="Candles reais" value={market.candles.length} /><MetricCard label="Última atualização" value={formatDate(market.last_update)} /><MetricCard label="Marcadores de operação" value={market.markers.length} hint="Diagnóstico identificado separadamente" /></section></> : <EmptyState title="Mercado sem dados" detail="Inicie o observador para preencher os arquivos de mercado." />}
  </div>;
}
