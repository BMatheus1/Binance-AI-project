"use client";

import { useApiData } from "@/components/dashboard-provider";
import { EmptyState, ErrorState, MetricCard, StatusBadge, formatDate, formatMoney, formatNumber } from "@/components/ui";

interface Observation {
  state:string; started_at?:string; completed_at?:string|null; elapsed_seconds?:number;
  remaining_seconds?:number; minimum_24h_completed:boolean; samples?:number;
  worker_availability_fraction?:number|null; valid_evaluations_added?:number; problems?:string[];
}
interface Session { session_id:string; state:string; created_at:string; authorized_at:string|null; expires_at:string|null; entries:number; policy:string; symbol:string; quote_amount:string; stop_reason:string|null; }
interface Position { position_id:string; state:string; symbol:string; policy:string; opened_at:string|null; planned_close_at:string|null; quantity:string|null; entry_price:string|null; net_quote:string|null; close_reason:string|null; }
interface Activity { recorded_at:string; event_type:string; payload:Record<string,unknown>; }
interface AutonomousData {
  state:string; environment:string; authorization:string;
  engine:{state:string;updated_at:string|null;last_error:string|null;orders_enabled:boolean};
  kill_switch:{engaged:boolean;reason:string};
  observation:Observation;
  economic:{economically_validated:boolean;resolved_outcomes:number;pending_outcomes:number;elapsed_prospective_days:number;limitations:string[]};
  limits:Record<string,string|number>;
  session_and_positions:{session:Session|null;open_position:Position|null;recent_activity:Activity[];closed_positions:Position[]};
}

function duration(seconds?:number) {
  if (seconds == null) return "Sem dados";
  const hours=Math.floor(seconds/3600); const minutes=Math.floor((seconds%3600)/60);
  return `${hours}h ${minutes}min`;
}

export default function AutonomousPage() {
  const {data,error}=useApiData<AutonomousData>("/api/autonomous",3000);
  const observation=data?.observation; const session=data?.session_and_positions.session;
  const position=data?.session_and_positions.open_position;
  return <div className="page-stack">
    <section className="page-heading"><div><span className="eyebrow">BINANCE SPOT DEMO · CLI AUTORIZADA</span><h1>Robô Autônomo</h1><p>Motor supervisionado, política BTC congelada e posições reais da conta Demo. Esta página é somente de monitoramento.</p></div><div className="status-cluster"><StatusBadge state={data?.kill_switch.engaged?"bad":"good"} label={data?.kill_switch.engaged?"Novas entradas bloqueadas":"Sessão liberada"}/><StatusBadge state={data?.state==="AUTHORIZED_DEMO"?"good":"warn"} label={data?.state??"Carregando"}/></div></section>
    {error&&<ErrorState message={error}/>} 
    <section className="metrics-grid"><MetricCard label="Modo" value={data?.state??"Sem telemetria"}/><MetricCard label="Valor por operação" value={data?formatMoney(Number(data.limits.quote_amount)):"Sem dados"}/><MetricCard label="Entradas da sessão" value={session?.entries??0}/><MetricCard label="Posição aberta" value={position?position.state:"Nenhuma"}/><MetricCard label="Observação acumulada" value={duration(observation?.elapsed_seconds)}/><MetricCard label="Desfechos resolvidos" value={data?.economic.resolved_outcomes??0}/></section>
    <section className="two-column"><article className="panel"><div className="panel-title"><div><span className="eyebrow">SESSÃO</span><h2>Autorização operacional</h2></div></div><div className="facts"><div><span>ID</span><strong>{session?.session_id??"Não preparada"}</strong></div><div><span>Política</span><strong>{session?.policy??String(data?.limits.policy??"A_quantitative")}</strong></div><div><span>Ativo</span><strong>{session?.symbol??"BTCUSDT"}</strong></div><div><span>Autorizada em</span><strong>{formatDate(session?.authorized_at)}</strong></div><div><span>Expira em</span><strong>{formatDate(session?.expires_at)}</strong></div><div><span>Kill switch</span><strong>{data?.kill_switch.reason??"Sem dados"}</strong></div></div><p className="muted">A preparação e a autorização permanecem exclusivas da CLI local. Abrir o dashboard não envia ordens.</p></article>
    <article className="panel"><div className="panel-title"><div><span className="eyebrow">PROTOCOLO PROSPECTIVO</span><h2>Validação mínima de 24 horas</h2></div><StatusBadge state={observation?.minimum_24h_completed?"good":"warn"} label={observation?.minimum_24h_completed?"Tempo mínimo concluído":"Em andamento"}/></div><div className="facts"><div><span>Início</span><strong>{formatDate(observation?.started_at)}</strong></div><div><span>Tempo restante</span><strong>{duration(observation?.remaining_seconds)}</strong></div><div><span>Amostras</span><strong>{observation?.samples??0}</strong></div><div><span>Novas avaliações</span><strong>{observation?.valid_evaluations_added??0}</strong></div><div><span>Disponibilidade do worker</span><strong>{observation?.worker_availability_fraction==null?"Desconhecida":`${formatNumber(observation.worker_availability_fraction*100,2)}%`}</strong></div></div>{Boolean(observation?.problems?.length)&&<p className="muted">Problemas: {observation?.problems?.join(", ")}</p>}</article></section>
    <section className="two-column"><article className="panel"><div className="panel-title"><div><span className="eyebrow">POSIÇÃO</span><h2>Gerenciamento independente da IA</h2></div></div>{position?<div className="facts"><div><span>ID</span><strong>{position.position_id}</strong></div><div><span>Estado</span><strong>{position.state}</strong></div><div><span>Abertura</span><strong>{formatDate(position.opened_at)}</strong></div><div><span>Prazo</span><strong>{formatDate(position.planned_close_at)}</strong></div><div><span>Quantidade</span><strong>{position.quantity??"Desconhecida"}</strong></div><div><span>Preço médio</span><strong>{position.entry_price??"Desconhecido"}</strong></div></div>:<EmptyState title="Nenhuma posição experimental aberta" detail="O motor não força operações quando os gates ou o sinal congelado não são satisfeitos."/>}</article>
    <article className="panel"><div className="panel-title"><div><span className="eyebrow">VALIDAÇÃO ECONÔMICA</span><h2>Categoria validada</h2></div><StatusBadge state={data?.economic.economically_validated?"good":"bad"} label={data?.economic.economically_validated?"Disponível":"Bloqueada"}/></div><div className="facts"><div><span>Desfechos resolvidos</span><strong>{data?.economic.resolved_outcomes??0}</strong></div><div><span>Pendentes</span><strong>{data?.economic.pending_outcomes??0}</strong></div><div><span>Dias prospectivos</span><strong>{formatNumber(data?.economic.elapsed_prospective_days,3)}</strong></div></div><p className="muted">EXPERIMENTAL_DEMO pode ser autorizada para validar a operação com saldo virtual; isso não comprova lucratividade.</p></article></section>
    <section className="panel"><div className="panel-title"><div><span className="eyebrow">ATIVIDADE REAL</span><h2>Fluxo cronológico do motor</h2></div></div>{data?.session_and_positions.recent_activity.length?<div className="table-wrap"><table><thead><tr><th>Horário</th><th>Evento</th><th>Registro</th></tr></thead><tbody>{data.session_and_positions.recent_activity.map((row,index)=><tr key={`${row.recorded_at}-${index}`}><td>{formatDate(row.recorded_at)}</td><td>{row.event_type}</td><td className="muted">{JSON.stringify(row.payload)}</td></tr>)}</tbody></table></div>:<EmptyState title="Nenhuma atividade autônoma" detail="Eventos aparecerão quando o motor iniciar, reconciliar ou avaliar uma sessão."/>}</section>
  </div>;
}
