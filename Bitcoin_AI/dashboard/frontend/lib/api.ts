import type { ApiEnvelope } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
let csrfToken: string | null = null;
let sessionPromise: Promise<string> | null = null;

export async function bootstrapSession(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!sessionPromise) {
    sessionPromise = (async () => {
      const response = await fetch(`${API_BASE}/api/session`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) throw new Error(`Sessão local recusada (${response.status})`);
      const payload = await response.json();
      csrfToken = String(payload.csrf_token);
      return csrfToken;
    })().finally(() => { sessionPromise = null; });
  }
  return sessionPromise;
}

async function apiGetAttempt<T>(path: string, retry: boolean): Promise<T> {
  const token = await bootstrapSession();
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    cache: "no-store",
    headers: { "X-Dashboard-Token": token },
  });
  if (response.status === 401 && retry) {
    csrfToken = null;
    await bootstrapSession();
    return apiGetAttempt<T>(path, false);
  }
  if (!response.ok) throw new Error(`Falha ao consultar ${path} (${response.status})`);
  const payload = (await response.json()) as ApiEnvelope<T>;
  return payload.data;
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiGetAttempt<T>(path, true);
}

export async function engageKillSwitch(reason: string): Promise<void> {
  if (!csrfToken) await bootstrapSession();
  const response = await fetch(`${API_BASE}/api/control/kill-switch`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken ?? "" },
    body: JSON.stringify({ reason, confirmation: "ACIONAR KILL SWITCH" }),
  });
  if (!response.ok) throw new Error(`Kill switch recusado (${response.status})`);
}

export function dashboardSocket(csrf: string): WebSocket {
  const url = new URL(API_BASE);
  const protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(`${protocol}//${url.host}/api/ws?csrf=${encodeURIComponent(csrf)}`);
}

export interface PreparedDemoSession {session_id:string;confirmation:string;mode:string;allow_probes:boolean;limits:Record<string,number|string>;}
export async function prepareDemoSession(mode:string="EXPERIMENTAL_DEMO",allowProbes:boolean=false):Promise<PreparedDemoSession> {
  const token=await bootstrapSession();
  const response=await fetch(`${API_BASE}/api/control/prepare-session`,{
    method:"POST",credentials:"include",
    headers:{"Content-Type":"application/json","X-CSRF-Token":token},
    body:JSON.stringify({confirmation:"PREPARAR SESSAO DEMO",mode,allow_probes:allowProbes}),
  });
  if(!response.ok) throw new Error(`Preparação recusada (${response.status}). Verifique segurança e reconciliação.`);
  return ((await response.json()) as ApiEnvelope<PreparedDemoSession>).data;
}

export async function controlDemoSession(action:"authorize-session"|"stop-session",payload:Record<string,string>):Promise<void> {
  const token=await bootstrapSession();
  const response=await fetch(`${API_BASE}/api/control/${action}`,{method:"POST",credentials:"include",
    headers:{"Content-Type":"application/json","X-CSRF-Token":token},body:JSON.stringify(payload)});
  if(!response.ok)throw new Error(`Ação recusada (${response.status}). Consulte a reconciliação e os limites.`);
}

export async function exportDataset(dataset: "operations" | "news"): Promise<void> {
  const token = await bootstrapSession();
  const response = await fetch(`${API_BASE}/api/export/${dataset}.csv`, {
    credentials: "include",
    headers: { "X-Dashboard-Token": token },
  });
  if (!response.ok) throw new Error(`Falha ao exportar ${dataset} (${response.status})`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `phase6_3_${dataset}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}
