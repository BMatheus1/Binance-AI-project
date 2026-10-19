import { AlertTriangle, Minus } from "lucide-react";

export function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null || Number.isNaN(value)
    ? "Sem dados"
    : new Intl.NumberFormat("pt-BR", { maximumFractionDigits: digits }).format(value);
}

export function formatMoney(value: number | null | undefined) {
  return value == null || Number.isNaN(value)
    ? "Não calculado"
    : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" }).format(value);
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Sem dados";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value));
}

export function StatusBadge({ state, label }: { state: "good" | "warn" | "bad" | "neutral"; label: string }) {
  return <span className={`status status-${state}`}><span className="status-dot" />{label}</span>;
}

export function MetricCard({ label, value, hint, tone = "neutral" }: {
  label: string; value: React.ReactNode; hint?: string; tone?: "positive" | "negative" | "neutral";
}) {
  return <article className="metric-card">
    <span className="metric-label">{label}</span>
    <strong className={`metric-value metric-${tone}`}>{value}</strong>
    {hint && <small>{hint}</small>}
  </article>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><Minus size={22} /><strong>{title}</strong><p>{detail}</p></div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="error-state"><AlertTriangle size={20} /><span>{message}</span></div>;
}
