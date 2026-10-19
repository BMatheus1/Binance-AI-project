import type { Metadata } from "next";
import { DashboardProvider } from "@/components/dashboard-provider";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import "./globals.css";

export const metadata: Metadata = { title: "Bitcoin AI Trader", description: "Monitoramento local e seguro da Binance Demo" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body><DashboardProvider><div className="app-shell"><Sidebar /><div className="main-shell"><Topbar /><main>{children}</main></div></div></DashboardProvider></body></html>;
}
