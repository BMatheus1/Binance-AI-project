"use client";
import type { UnifiedDecision } from "@/lib/types";
import { EmptyState, StatusBadge, formatDate, formatNumber } from "@/components/ui";
import { reasonLabel, decisionLabel } from "@/lib/labels";
import { useState } from "react";

export function UnifiedDecisions({rows}:{rows:UnifiedDecision[]}) {
  const [history,setHistory]=useState(false);
  const displayed=history?rows:rows.slice(0,3);
  return <section className="panel"><div className="panel-title"><div><span className="eyebrow">FONTE OPERACIONAL ÚNICA</span><h2>Decisões centrais e oportunidades</h2></div><span className="tag">Experimental · vantagem econômica não comprovada</span></div>
    <button className="panel-link" onClick={()=>setHistory(!history)}>{history?"Mostrar somente a última avaliação":"Mostrar histórico de avaliações"}</button>
    {rows.length ? <div className="table-wrap"><table><thead><tr><th>Horário / ativo</th><th>Previsão 5 min</th><th>Custo estimado</th><th>Decisão</th><th>Motivos</th></tr></thead><tbody>{displayed.map(row=><tr key={row.decision_id}><td>{formatDate(row.evaluated_at)}<br/>{row.symbol}</td><td>{row.prediction.horizons?.[String(row.horizon_minutes)] ? `${formatNumber(row.prediction.horizons[String(row.horizon_minutes)].probabilities.up*100,2)}% de alta` : "Modelo indisponível"}</td><td>{formatNumber(row.costs.estimated_round_trip_bps,2)} bps<br/><small>Expectativa líquida: desconhecida</small></td><td><StatusBadge state={row.decision==="COMPRAR"?"good":"warn"} label={decisionLabel(row.decision)}/>{Date.now()>Date.parse(row.valid_until)&&<small>Avaliação histórica · validade encerrada</small>}{row.decision==="COMPRAR"&&<small>Sujeita à autorização e ao risco</small>}</td><td>{row.reasons.map(reasonLabel).join("; ")}<details><summary>Evidências e plano</summary><p>Valor: {row.planned_risk.quote_amount} USDT · Stop: {row.planned_risk.stop_loss_bps} bps · Prazo: {row.planned_risk.planned_holding_minutes} min</p><p>Validade: {formatDate(row.valid_until)}</p><p>Identificador: {row.decision_id}</p><p>Modelos: {Object.values(row.model_versions).join(" · ")}</p><p>Padrões em pesquisa: {row.context.patterns?.patterns.filter(p=>p.detected).map(p=>reasonLabel(p.name)).join(", ")||"Nenhum identificado"}. Sem influência na política congelada.</p></details></td></tr>)}</tbody></table></div> : <EmptyState title="Aguardando decisão central" detail="O pipeline publica uma proposta por ativo após receber um candle fechado com integridade temporal."/>}
  </section>;
}
