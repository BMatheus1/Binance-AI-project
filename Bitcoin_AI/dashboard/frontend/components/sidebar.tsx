"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, Bot, Gauge, HeartPulse, LayoutDashboard, Newspaper, ScrollText } from "lucide-react";

const links = [
  ["/", "Visão geral", LayoutDashboard],
  ["/markets", "Mercados", Activity],
  ["/operations", "Operações", ScrollText],
  ["/performance", "Resultados", BarChart3],
  ["/intelligence", "Inteligência", Bot],
  ["/news", "Notícias", Newspaper],
  ["/health", "Saúde", HeartPulse],
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark"><Gauge size={22} /></div><div><strong>Bitcoin AI</strong><span>Trader · Demo</span></div></div>
    <nav>{links.map(([href, label, Icon]) => <Link key={href} href={href} className={pathname === href ? "active" : ""}><Icon size={18} /><span>{label}</span></Link>)}</nav>
    <div className="sidebar-foot"><span className="eyebrow">AMBIENTE</span><strong>Binance Spot Demo</strong><small>Execução autônoma bloqueada</small></div>
  </aside>;
}
