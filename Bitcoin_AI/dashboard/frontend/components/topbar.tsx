"use client";

import { RefreshCw, Wifi, WifiOff } from "lucide-react";
import { useDashboard } from "./dashboard-provider";
import { formatDate } from "./ui";
import { stateLabel } from "@/lib/labels";

export function Topbar() {
  const { snapshot, connected, refresh } = useDashboard();
  return <header className="topbar">
    <div><span className="eyebrow">MONITORAMENTO LOCAL</span><strong>{stateLabel(snapshot?.overview.mode ?? "unknown")} · Demo</strong></div>
    <div className="topbar-actions">
      <span className={connected ? "live-indicator" : "live-indicator offline"}>{connected ? <Wifi size={15} /> : <WifiOff size={15} />}{connected ? "Tempo real" : "Reconectando"}</span>
      <span className="desktop-only">{formatDate(snapshot?.overview.last_update)}</span>
      <button className="icon-button" onClick={refresh} aria-label="Atualizar"><RefreshCw size={17} /></button>
    </div>
  </header>;
}
