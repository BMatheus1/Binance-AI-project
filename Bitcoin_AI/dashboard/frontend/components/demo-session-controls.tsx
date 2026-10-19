"use client";
import { useState } from "react";
import { prepareDemoSession, controlDemoSession, type PreparedDemoSession } from "@/lib/api";
import { ErrorState } from "@/components/ui";

export function DemoSessionControls() {
  const [busy,setBusy]=useState(false);
  const [prepared,setPrepared]=useState<PreparedDemoSession|null>(null);
  const [probes,setProbes]=useState(false);
  const [confirmation,setConfirmation]=useState("");
  const [message,setMessage]=useState<string|null>(null);
  const [error,setError]=useState<string|null>(null);
  async function act(action:()=>Promise<void>) {
    setBusy(true);setError(null);
    try {await action();} catch(cause) {setError(cause instanceof Error?cause.message:"Falha na sessão");} finally {setBusy(false);}
  }
  const prepare=()=>act(async()=>{
    setPrepared(await prepareDemoSession("DEMO_ACTIVE_EXPERIMENTAL",probes));
    setConfirmation("");setMessage("Preparada. Nenhuma ordem está autorizada.");
  });
  const authorize=()=>act(async()=>{
    if(!prepared||confirmation!==prepared.confirmation)return;
    if(!window.confirm("Iniciar compras e vendas automáticas exclusivamente na Binance Demo por até 60 minutos, com os limites exibidos?"))return;
    await controlDemoSession("authorize-session",{session_id:prepared.session_id,confirmation});
    setPrepared(null);setConfirmation("");setMessage("Sessão autorizada. O motor avalia os filtros antes de cada compra virtual.");
  });
  const stop=()=>act(async()=>{
    await controlDemoSession("stop-session",{confirmation:"ENCERRAR SESSAO DEMO"});
    setPrepared(null);setConfirmation("");setMessage("Novas compras bloqueadas. A saída de eventual posição aberta continua sob gestão do motor.");
  });
  return <section className="panel"><div className="panel-title"><h2>Modo experimental ativo · somente Demo</h2><button disabled={busy} onClick={stop}>Encerrar sessão</button></div>
    <p>BTCUSDT · alvo máximo de 10 USDT virtuais · uma posição · até seis entradas · 60 minutos. Saídas por stop, lucro líquido estimado, trailing ou prazo de cinco minutos; limite absoluto de oito minutos.</p>
    <p>Perda planejada: até 0,10 USDT por operação e 0,50 USDT acumulado por sessão. Stops e estimativas não garantem esses limites em falhas ou oscilações. Não há rentabilidade comprovada.</p>
    <label><input type="checkbox" checked={probes} disabled={busy||!!prepared} onChange={event=>setProbes(event.target.checked)}/> Permitir até duas explorações controladas após três minutos sem entrada. Elas não comprovam eficácia da IA.</label>
    <p><button className="primary-button" disabled={busy} onClick={prepare}>{busy?"Verificando…":"Preparar sessão Demo"}</button></p>
    <p className="muted">Exige kill switch ativo e reconciliação saudável. Abrir esta página nunca inicia ordens. A autorização usa as mesmas regras da CLI.</p>
    {error&&<ErrorState message={error}/>}{message&&<p role="status">{message}</p>}
    {prepared&&<div><p>Sessão: {prepared.session_id}. Exploração: {prepared.allow_probes?"permitida":"bloqueada"}. Digite a confirmação abaixo:</p><pre>{prepared.confirmation}</pre>
      <input aria-label="Confirmação da sessão Demo" autoComplete="off" value={confirmation} onChange={event=>setConfirmation(event.target.value)}/>
      <button className="primary-button" disabled={busy||confirmation!==prepared.confirmation} onClick={authorize}>Autorizar e iniciar na Demo</button>
      <details><summary>Alternativa pelo PowerShell</summary><pre>{`python .\\scripts\\run_phase6_4.py authorize-session --session-id ${prepared.session_id} --confirm ${prepared.confirmation}`}</pre></details>
    </div>}
  </section>;
}
