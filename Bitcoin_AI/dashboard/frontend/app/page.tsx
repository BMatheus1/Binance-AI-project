"use client";

import { AlertOctagon, ArrowRight, Database, ShieldCheck, WalletCards } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useDashboard } from "@/components/dashboard-provider";
import { EmptyState, ErrorState, MetricCard, StatusBadge, formatMoney, formatNumber } from "@/components/ui";
import { engageKillSwitch } from "@/lib/api";

export default function OverviewPage() {
  const { snapshot, loading, error, refresh } = useDashboard();
  const [arming, setArming] = useState(false);
  const overview = snapshot?.overview;
  const stop = async () => {
    if (!window.confirm("Acionar o kill switch e bloquear novas entradas?")) return;
    setArming(true);
    try { await engageKillSwitch("parada_manual_interface"); await refresh(); } finally { setArming(false); }
  };
  if (loading && !overview) return <section className="loading-panel">Conectando ao backend local…</section>;
  return <div className="page-stack">
    <section className="page-heading"><div><span className="eyebrow">CENTRO DE CONTROLE</span><h1>Visão geral</h1><p>Estado operacional, conta virtual e controles de segurança.</p></div><button className="danger-button" onClick={stop} disabled={arming || overview?.kill_switch.engaged}><AlertOctagon size={17} />{overview?.kill_switch.engaged ? "Kill switch ativo" : "Parar novas entradas"}</button></section>
    {error && <ErrorState message={error} />}
    <section className="status-strip">
      <div><span>Ambiente</span><StatusBadge state="good" label="Binance Demo" /></div>
      <div><span>Modo</span><StatusBadge state="neutral" label={overview?.mode ?? "Sem dados"} /></div>
      <div><span>Kill switch</span><StatusBadge state={overview?.kill_switch.engaged ? "bad" : "warn"} label={overview?.kill_switch.engaged ? "Ativo" : "Liberado"} /></div>
      <div><span>Autônomo</span><StatusBadge state="bad" label={overview?.autonomous.ready ? "Pronto, não iniciado" : "Bloqueado"} /></div>
    </section>
    <section className="metrics-grid">
      <MetricCard label="Patrimônio virtual" value={formatMoney(overview?.account.equity_usdt)} hint={overview?.account.equity_complete ? "Preços de referência identificados" : `Parcial · sem cotação: ${overview?.account.unvalued_assets?.join(", ") || "Sem dados"}`} />
      <MetricCard label="Resultado líquido da estratégia" value={formatMoney(overview?.strategy_performance.net_result)} hint="Diagnósticos excluídos" />
      <MetricCard label="Taxa de acerto" value={overview?.strategy_performance.win_rate == null ? "Não calculado" : `${formatNumber(overview.strategy_performance.win_rate * 100)}%`} />
      <MetricCard label="Drawdown máximo" value={formatMoney(overview?.strategy_performance.max_drawdown)} />
      <MetricCard label="Operações de estratégia" value={overview?.strategy_performance.trade_count ?? "Sem dados"} />
      <MetricCard label="Diagnósticos" value={overview?.diagnostic_operation_count ?? "Sem dados"} hint="Não entram no P&L da estratégia" />
    </section>
    <section className="two-column">
      <article className="panel"><div className="panel-title"><div><span className="eyebrow">CONTA DEMO</span><h2>Saldos virtuais</h2></div><WalletCards size={20} /></div>
        {overview?.account.balances?.length ? <div className="balance-list">{overview.account.balances.map((balance) => <div key={balance.asset}><div className="asset-symbol">{balance.asset}</div><div><strong>{formatNumber(Number(balance.free), 8)}</strong><small>{balance.category === "residual_dust" ? "Resíduo / dust, não é posição intencional" : formatMoney(balance.quote_value_usdt)}</small></div></div>)}</div> : <EmptyState title="Sem saldos disponíveis" detail="A conta Demo não respondeu ou não há valores diferentes de zero." />}
      </article>
      <article className="panel"><div className="panel-title"><div><span className="eyebrow">SEGURANÇA</span><h2>Estado de execução</h2></div><ShieldCheck size={20} /></div>
        <div className="facts"><div><span>Ordens abertas</span><strong>{overview?.account.open_order_count ?? "Sem dados"}</strong></div><div><span>Posições intencionais</span><strong>{overview?.positions.length ?? "Sem dados"}</strong></div><div><span>Política congelada</span><strong>{overview?.autonomous.policy ?? "Sem dados"}</strong></div><div><span>Origem</span><strong>localhost</strong></div></div>
        <Link href="/health" className="panel-link">Abrir diagnóstico completo <ArrowRight size={15} /></Link>
      </article>
    </section>
    <section className="panel notice-panel"><Database size={20} /><div><strong>Dados reais, estados desconhecidos explícitos</strong><p>O dashboard lê SQLite, ledgers e streams armazenados. Ausência de registro aparece como “Sem dados” ou “Não calculado”.</p></div></section>
  </div>;
}
