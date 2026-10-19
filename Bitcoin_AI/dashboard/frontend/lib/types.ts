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
  latest_decision?:UnifiedDecision|null;
  next_nominal_candle_close?:string;
  system_state: string;
  environment: string;
  mode: string;
  kill_switch: { engaged: boolean; reason: string; updated_at: string | null };
  autonomous: { ready: boolean; policy: string; checks: Record<string, boolean>;
    state: string; status_label: string; status_tone: "good" | "warn" | "bad" | "neutral" };
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

export interface UnifiedDecision {
  schema_version:string; decision_id:string; evaluation_id:string; evaluated_at:string;
  data_available_at:string|null; symbol:string; policy_version:string;
  horizon_minutes:number; features_valid:boolean; valid_until:string;
  model_versions:Record<string,string>;
  prediction:{horizons?:Record<string,{probabilities:{down:number;tie:number;up:number};signal:string}>};
  costs:{estimated_round_trip_bps:number|null;expected_net_bps:number|null;economically_validated:boolean};
  planned_risk:{quote_amount:number;stop_loss_bps:number;planned_holding_minutes:number;planned_loss_quote_including_estimated_costs:number|null};
  context:{patterns?:{patterns:{name:string;detected:boolean|null}[]};fusion:{method:string}};
  decision:"COMPRAR"|"NAO_COMPRAR"|"AGUARDAR_DADOS"|"INDISPONIVEL_SEGURANCA";
  reasons:string[]; execution_state:string;
}
