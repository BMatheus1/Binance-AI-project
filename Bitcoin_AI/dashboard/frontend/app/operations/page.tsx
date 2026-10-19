"use client";

import { Download } from "lucide-react";
import { useApiData } from "@/components/dashboard-provider";
import { EmptyState, ErrorState, StatusBadge, formatDate, formatMoney, formatNumber } from "@/components/ui";
import { exportDataset } from "@/lib/api";

interface Operation { operation_id:string; category:string; policy:string|null; symbol:string; entry_time:string|null; exit_time:string|null; entry_price:number|null; exit_price:number|null; quantity:number|null; gross_result_quote:number|null; net_result_quote:number|null; status:string; strategy_evaluation_eligible:boolean; exchange_states:Array<{side:string;state:string}>; }
export default function OperationsPage() {
  const { data, error } = useApiData<{ items: Operation[] }>("/api/operations");
  const rows = data?.items ?? [];
  return <div className="page-stack"><section className="page-heading"><div><span className="eyebrow">EXECUÇÃO E RECONCILIAÇÃO</span><h1>Operações</h1><p>Diagnósticos, paper e estratégias mantidos em categorias distintas.</p></div><button className="secondary-button" type="button" onClick={()=>void exportDataset("operations")}><Download size={16}/>Exportar CSV</button></section>{error && <ErrorState message={error}/>}<section className="panel">{rows.length ? <div className="table-wrap"><table><thead><tr><th>ID</th><th>Categoria</th><th>Ativo</th><th>Entrada</th><th>Saída</th><th>Quantidade</th><th>Bruto</th><th>Líquido</th><th>Status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.operation_id}><td><strong>{row.operation_id}</strong><br/><span className="muted">{row.policy ?? "Sem política"}</span></td><td><span className="tag tag-gold">{row.category}</span></td><td>{row.symbol}</td><td>{formatDate(row.entry_time)}<br/><span className="muted">{formatNumber(row.entry_price,8)}</span></td><td>{formatDate(row.exit_time)}<br/><span className="muted">{formatNumber(row.exit_price,8)}</span></td><td>{formatNumber(row.quantity,8)}</td><td>{formatMoney(row.gross_result_quote)}</td><td>{formatMoney(row.net_result_quote)}<br/>{!row.strategy_evaluation_eligible && <span className="muted">Excluído da estratégia</span>}</td><td><StatusBadge state={row.status === "reconciled" ? "good":"warn"} label={row.status}/></td></tr>)}</tbody></table></div> : <EmptyState title="Nenhuma operação registrada" detail="O dashboard não cria operações para preencher esta tela."/>}</section></div>;
}

