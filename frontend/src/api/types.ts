export type Role = 'USER' | 'TRADER' | 'FUND' | 'ADMIN';

export interface TradeRequest {
  symbol: string;
  side: 'BUY' | 'SELL';
  qty: number;
}

export interface FuturesTradeRequest extends TradeRequest {
  leverage?: number;
  type?: string;
}

export interface SignalPayload {
  symbol: string;
  side: 'BUY' | 'SELL';
  qty: number;
}

export interface SignalsEnvelope {
  signals: SignalPayload[];
  enable?: Record<string, number>;
}

export interface OpsState {
  auto_mode: boolean;
  global_stop: boolean;
  trading_on?: boolean;
  agent_on?: boolean;
  arb_on?: boolean;
  sched_on?: boolean;
  manual_override?: boolean;
  manual_strategy?: Record<string, unknown> | null;
  exec_mode?: string;
  portfolio_equity?: number;
  scalp?: Record<string, unknown>;
  arb?: {
    interval?: number;
    threshold_pct?: number;
    qty_usd?: number;
    qty_min_usd?: number;
    qty_max_usd?: number;
    auto_mode?: boolean;
    filters?: Record<string, unknown>;
  };
  spot?: {
    enabled?: boolean;
    weights?: Record<string, number>;
    max_positions?: number;
    max_trade_pct?: number;
    risk_per_trade_pct?: number;
    max_symbol_exposure_pct?: number;
    tp_pct_default?: number;
    sl_pct_default?: number;
  };
  reserves?: {
    portfolio?: number;
    arbitrage?: number;
  };
  ops?: {
    capital?: {
      cap_pct?: number;
      hard_max_pct?: number;
    };
  };
}

export interface PortfolioPosition {
  symbol: string;
  quantity: number;
  average_price: number;
  unrealized_pnl: number;
}

export interface PortfolioSnapshot {
  realized_pnl: number;
  unrealized_pnl: number;
  positions: PortfolioPosition[];
  equity_usd: number;
}

export interface BalanceEntry {
  asset: string;
  free: number;
  locked: number;
}

export interface BalancesResponse {
  balances: BalanceEntry[];
}

export interface PortfolioAggregate {
  equity_total_usd: number;
  tradable_equity_usd?: number;
  cap_pct?: number;
  reserves?: Record<string, number>;
  positions: PortfolioPosition[];
  balances: BalanceEntry[];
  realized_pnl?: number;
  unrealized_pnl?: number;
  timestamp: string;
}

export interface ArbitrageOpportunity {
  [key: string]: unknown;
}

export interface ArbitrageOpportunities {
  opportunities: ArbitrageOpportunity[];
}

export interface ActivityComponent {
  status: string;
  last_tick?: number | null;
  notes?: string | null;
}

export interface ActivityItem {
  ts: string;
  actor: string;
  action: string;
  ok: boolean;
  details?: string;
}

export interface ActivityResponse {
  components: Record<string, ActivityComponent>;
  last_actions: ActivityItem[];
  warnings: string[];
}

export interface StatusSnapshot {
  version: string;
  uptime: number;
  active_cores: Record<string, unknown>;
  timestamp: string;
}

export interface SignalFeedItem {
  ts: string;
  symbol: string;
  side: string;
  confidence: number;
  strategy: string;
  rationale?: string;
  source: string;
}

export interface SignalsFeed {
  items: SignalFeedItem[];
  cursor?: string | null;
}

export interface SpotRiskConfig {
  max_positions?: number;
  max_trade_pct?: number;
  risk_per_trade_pct?: number;
  max_symbol_exposure_pct?: number;
  tp_pct_default?: number;
  sl_pct_default?: number;
}

export interface StrategyWeightsRequest {
  weights: Record<string, number>;
  enabled?: boolean;
}

export interface CapitalSnapshot {
  cap_pct: number;
  equity: number;
  allocation: Record<string, number>;
  state: OpsState;
  reserves?: OpsState['reserves'];
}

export interface ResearchResponse {
  results: unknown[];
}

export interface LogEntry {
  ts: string;
  level: string;
  message: string;
}

export interface LogsResponse {
  items: LogEntry[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
  user_id: number;
  expires_at: string;
}

export interface UserProfile {
  id: number;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface FeatureFlag {
  key: string;
  value: unknown;
  updated_at: string;
  updated_by?: number | null;
}

export interface LimitEntry {
  scope: string;
  subject?: string | null;
  key: string;
  value: unknown;
  updated_at: string;
  updated_by?: number | null;
}

export interface AuditEvent {
  id: string;
  ts: string;
  actor_user_id?: number | null;
  actor_role?: string | null;
  action: string;
  target?: string | null;
  result: string;
  ip?: string | null;
  user_agent?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface HealthResponse {
  status: string;
}

export interface ErrorEnvelope {
  error: string | Record<string, unknown> | Array<unknown>;
}

export interface ApiResponse<T> {
  data?: T;
  error?: ErrorEnvelope;
}
