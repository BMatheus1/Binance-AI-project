"use client";

import { useEffect, useRef } from "react";
import { CandlestickSeries, ColorType, createChart, HistogramSeries } from "lightweight-charts";
import type { MarketData } from "@/lib/types";

export function MarketChart({ market }: { market: MarketData }) {
  const target = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!target.current || !market.candles.length) return;
    const chart = createChart(target.current, {
      autoSize: true,
      height: 440,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8f98a8", fontFamily: "Inter, sans-serif" },
      grid: { vertLines: { color: "rgba(255,255,255,.035)" }, horzLines: { color: "rgba(255,255,255,.035)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,.08)" },
      timeScale: { borderColor: "rgba(255,255,255,.08)", timeVisible: true },
      crosshair: { vertLine: { color: "#d8a93b" }, horzLine: { color: "#d8a93b" } },
    });
    const candles = chart.addSeries(CandlestickSeries, { upColor: "#36c98f", downColor: "#ef5d68", borderVisible: false, wickUpColor: "#36c98f", wickDownColor: "#ef5d68" });
    candles.setData(market.candles.map((row) => ({ time: row.time as never, open: row.open, high: row.high, low: row.low, close: row.close })));
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "", color: "#d8a93b55" });
    volume.priceScale().applyOptions({ scaleMargins: { top: .78, bottom: 0 } });
    volume.setData(market.candles.map((row) => ({ time: row.time as never, value: row.volume, color: row.close >= row.open ? "#36c98f44" : "#ef5d6844" })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [market]);
  return <div ref={target} className="market-chart" />;
}
