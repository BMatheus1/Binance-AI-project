"use client";
import { useState } from "react";
import { prepareDemoSession } from "@/lib/api";
import { ErrorState } from "@/components/ui";

export function DemoSessionControls() {
  const [busy,setBusy]=useState(false);
  const [session,setSession]=useState<string|null>(null);
  const [error,setError]=useState<string|null>(null);
  const prepare=async()=>{
    if(!window.confirm("Preparar uma sessão de 10 USDT exclusivamente Demo? Isso não autoriza ordens."))return;
    setBusy(true);setError(null);
    try {setSession((await prepareDemoSession()).session_id);} catch(cause) {setError(cause instanceof Error?cause.message:"Falha na preparação");} finally {setBusy(false);}
  };
  return <section className="panel"><div className="panel-title"><h2>Preparar uma sessão experimental</h2><button className="primary-button" disabled={busy} onClick={prepare}>{busy?"Verificando…":"Preparar sessão Demo"}</button></div>
    <p className="muted">Exige kill switch ativo, processo atual e reconciliação saudável. A ativação de ordens continua pela CLI local. Abrir esta página não inicia negociação.</p>
    {error&&<ErrorState message={error}/>}{session&&<div><p>Sessão preparada: {session}. Para autorizar no PowerShell:</p><pre><code>{`python .\\scripts\\run_phase6_4.py authorize-session --session-id ${session} --confirm I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL`}</code></pre></div>}
  </section>;
}
