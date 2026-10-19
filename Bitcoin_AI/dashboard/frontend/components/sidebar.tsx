"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useDashboard } from "@/components/dashboard-provider";
import { Activity, BarChart3, Bot, Cpu, Gauge, HeartPulse, LayoutDashboard, Newspaper, ScrollText } from "lucide-react";

const links = [
  ["/", "Visão geral", LayoutDashboard],
  ["/markets", "Mercados", Activity],
  ["/operations", "Operações", ScrollText],
  ["/performance", "Resultados", BarChart3],
  ["/intelligence", "Inteligência", Bot],
  ["/autonomous", "Robô Autônomo", Cpu],
  ["/news", "Notícias", Newspaper],
  ["/health", "Saúde", HeartPulse],
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { snapshot, connected } = useDashboard();
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark"><Gauge size={22} /></div><div><strong>Bitcoin AI</strong><span>Trader · Demo</span></div></div>
    <nav>{links.map(([href, label, Icon]) => <Link key={href} href={href} className={pathname === href ? "active" : ""}><Icon size={18} /><span>{label}</span></Link>)}</nav>
    <div className="sidebar-foot"><span className="eyebrow">AMBIENTE</span><strong>Binance Spot Demo</strong><small>{connected ? snapshot?.overview.autonomous.status_label ?? "Aguardando estado" : "Conexão com painel indisponível"}</small></div>
  </aside>;
}
