export type MaybeNumber = number | null;

export interface Balance {
  asset: string;
  free: string;
  locked: string;
  reference_price_usdt: MaybeNumber;
  quote_value_usdt: MaybeNumber;
  reference_source: string | null;
  category: "cash" | "residual_dust" | "asset_balance";
}

export interface StrategyPerformance {
  trade_count: number;
  completed_with_net_result: number;
  net_result: MaybeNumber;
  win_rate: MaybeNumber;
  profit_factor: MaybeNumber;
  expectancy: MaybeNumber;
  max_drawdown: MaybeNumber;
  equity_curve: Array<{ time: string; value: number }>;
}

export interface OverviewData {
  system_state: string;
  environment: string;
  mode: string;
  kill_switch: { engaged: boolean; reason: string; updated_at: string | null };
  autonomous: { ready: boolean; policy: string; checks: Record<string, boolean> };
  account: {
    available: boolean;
    balances: Balance[];
    equity_usdt: MaybeNumber;
    equity_complete: boolean;
    unvalued_assets: string[];
    open_order_count: number;
    received_at: string | null;
  };
  strategy_performance: StrategyPerformance;
  diagnostic_operation_count: number;
  positions: unknown[];
  connectors: Record<string, unknown>;
  last_update: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closed: boolean;
}

export interface MarketData {
  symbol: string;
  price: MaybeNumber;
  bid: MaybeNumber;
  ask: MaybeNumber;
  spread_bps: MaybeNumber;
  change_percent_1m: MaybeNumber;
  last_update: string | null;
  stale_seconds: MaybeNumber;
  stream_state: string;
  candles: Candle[];
  markers: Array<{ time: string; price: number; type: string; operation_id: string }>;
}

export interface DashboardSnapshot {
  overview: OverviewData;
  markets: Record<string, MarketData>;
  health: Record<string, unknown>;
}

export interface ApiEnvelope<T> {
  generated_at: string;
  data: T;
}
