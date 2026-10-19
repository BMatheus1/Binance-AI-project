"use client";

import { useApiData } from "@/components/dashboard-provider";
import { EmptyState, StatusBadge, formatDate, formatNumber } from "@/components/ui";

interface Forecast {
  state?: string;
  reason?: string;
  primary_signal?: string;
}
interface Decision {
  evaluation_id:string; evaluated_at:string; market_time:string; symbol:string; policy:string;
  worker_state:string; prediction:Forecast; estimated_cost_bps:number|null;
  expected_gross_bps:number|null; expected_net_bps:number|null; decision:string;
  reasons:string[]; orders_sent:boolean;
}
interface Worker {
  state:string; last_evaluation_at?:string|null; last_error?:string|null;
  cycles_completed?:number; evaluations_recorded?:number;
  symbols?:Record<string,{warmup_candles:number;last_closed_open_time:string|null;quote_available:boolean;depth_available:boolean}>;
  qwen3?:{state:string;last_error?:string|null};
}
interface Intelligence {
  policies:Record<string,{description:string;latest:Decision|null}>;
  recent_decisions:Decision[]; decision_data_available:boolean; active_demo_policy:string;
  autonomous:{ready:boolean;checks:Record<string,boolean>}; worker:Worker; ledger_records:number;
}

const policyLetter:Record<string,string> = {
  A_quantitative:"A", B_conservative_news:"B",
  C_qwen3_structured_news:"C", D_event_market_reaction:"D",
};
const workerLabel:Record<string,string> = {
  analyzing:"Analisando", waiting_for_closed_candles:"Aguardando candle fechado",
  abstaining:"Em abstenção", signal_ready:"Sinal registrado", warming_up:"Carregando dados",
  unavailable:"Indisponível", not_running:"Serviço parado", not_configured:"Não configurado",
};

export default function IntelligencePage() {
  const { data } = useApiData<Intelligence>("/api/intelligence", 5000);
  const worker = data?.worker;
  const state = worker?.state ?? "not_running";
  const workerTone = state === "signal_ready" ? "good" : state === "unavailable" || state === "not_running" ? "bad" : "warn";
  return <div className="page-stack">
    <section className="page-heading">
      <div><span className="eyebrow">AVALIAÇÃO CAUSAL CONTÍNUA</span><h1>Inteligência artificial</h1><p>Candles fechados, previsões congeladas, custos observados e motivos registrados sem envio de ordens.</p></div>
      <div className="status-cluster"><StatusBadge state={workerTone} label={workerLabel[state] ?? state}/><StatusBadge state="bad" label="Execução autônoma bloqueada"/></div>
    </section>

    <section className="metrics-grid">
      <article className="metric-card"><span className="metric-label">Ciclos concluídos</span><strong className="metric-value">{worker?.cycles_completed ?? 0}</strong><small>mesmo instante para os três ativos</small></article>
      <article className="metric-card"><span className="metric-label">Avaliações persistidas</span><strong className="metric-value">{worker?.evaluations_recorded ?? 0}</strong><small>ativo × política</small></article>
      <article className="metric-card"><span className="metric-label">Última análise</span><strong className="metric-value metric-small">{formatDate(worker?.last_evaluation_at)}</strong><small>{worker?.last_error ?? "sem erro ativo"}</small></article>
      <article className="metric-card"><span className="metric-label">Qwen3</span><strong className="metric-value metric-small">{worker?.qwen3?.state ?? "sem telemetria"}</strong><small>falhas afetam somente C e D</small></article>
    </section>

    <section className="policy-grid">{Object.entries(data?.policies ?? {}).map(([name,policy]) => {
      const latest=policy.latest;
      return <article className="policy-card" key={name}><span className="policy-letter">POLÍTICA {policyLetter[name]}</span><h3>{name}</h3><p>{policy.description}</p>
        <StatusBadge state={latest ? (latest.decision === "abstain" ? "warn":"good") : "neutral"} label={latest ? (latest.decision === "abstain" ? "Abstenção registrada":"Sinal registrado") : "Sem avaliação"}/>
        {latest && <div className="policy-detail"><span>{latest.symbol} · {formatDate(latest.evaluated_at)}</span><span>Custo: {formatNumber(latest.estimated_cost_bps,2)} bps</span><span>{latest.reasons.join(", ")}</span></div>}
      </article>;
    })}</section>

    <section className="panel"><div className="panel-title"><div><span className="eyebrow">COBERTURA DE MERCADO</span><h2>Estado por ativo</h2></div></div>
      <div className="facts">{Object.entries(worker?.symbols ?? {}).map(([symbol,item]) => <div key={symbol}><span>{symbol} · {item.warmup_candles} candles · {formatDate(item.last_closed_open_time)}</span><StatusBadge state={item.quote_available && item.depth_available ? "good":"warn"} label={item.quote_available && item.depth_available ? "Dados atuais":"Aguardando dados"}/></div>)}</div>
    </section>

    <section className="panel"><div className="panel-title"><div><span className="eyebrow">DECISÕES RECENTES</span><h2>SQLite + ledger operacional</h2></div><span className="tag">{data?.ledger_records ?? 0} ciclos no ledger</span></div>
      {data?.decision_data_available ? <div className="table-wrap"><table><thead><tr><th>Instante</th><th>Ativo</th><th>Política</th><th>Previsão 1m</th><th>Custo</th><th>Decisão</th><th>Motivo</th></tr></thead><tbody>{data.recent_decisions.map(row => <tr key={row.evaluation_id}><td>{formatDate(row.evaluated_at)}</td><td>{row.symbol}</td><td>{policyLetter[row.policy] ?? row.policy}</td><td>{row.prediction.primary_signal ?? row.prediction.reason ?? row.prediction.state ?? "indisponível"}</td><td>{formatNumber(row.estimated_cost_bps,2)} bps</td><td><StatusBadge state={row.decision === "abstain" ? "warn":"good"} label={row.decision}/></td><td>{row.reasons.join(", ")}</td></tr>)}</tbody></table></div> : <EmptyState title="Aguardando a primeira avaliação" detail="O worker precisa receber o próximo candle de um minuto fechado dos três ativos."/>}
    </section>
  </div>;
}
