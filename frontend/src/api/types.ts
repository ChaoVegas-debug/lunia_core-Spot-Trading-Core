
export type Role = 'USER' | 'TRADER' | 'FUND' | 'ADMIN';

// --- PORTFOLIO SYSTEM TYPES (PHASE 3) ---

export type PortfolioType = 'LONG_TERM' | 'TACTICAL';
export type RiskProfile = 'CONSERVATIVE' | 'BALANCED' | 'AGGRESSIVE';
export type PortfolioStatus = 'ACTIVE' | 'PAUSED' | 'DE_RISKING' | 'STOPPED' | 'FLATTENED';

export interface AssetCard {
  symbol: string;
  weight: number;
  confidence: number;
  reason: string[];
  sector: string;
  risk_note: string;
}

export interface PortfolioRule {
  entry_mode: string;
  rebalance_interval_days: number;
  profit_take_pct: number;
  stop_loss_pct: number;
}

export interface PortfolioDefinition {
  id: string;
  type: PortfolioType;
  risk_profile: RiskProfile;
  horizon: string;
  assets: AssetCard[];
  rules: PortfolioRule;
  status: PortfolioStatus;
  base_currency: string;
  total_capital_allocation: number;
}


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

  // Governance & Integrity (P1)
  drift_status?: 'NONE' | 'SOFT' | 'HARD'; // NONE = OK, SOFT = Price Drift, HARD = Manual Interference
  veto_reason?: string | null; // If global_stop is true, this reasoning is required
  last_drift_check?: string; // ISO Timestamp

  // Preview / Simulation Fields
  last_governance_event?: {
    id: string;
    message: string;
    timestamp: string;
    severity: 'INFO' | 'WARNING' | 'CRITICAL';
  } | null;
  airlock_status?: 'NOT_READY' | 'ARMED' | 'BLOCKED';
  active_strategies?: number;
  risk_score?: number;
  pnl_today?: number;


  // P2.0: Undo Capability
  undo_token?: string;
  undo_ttl?: number;
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

export interface OpsCapital {
  cap_pct: number;
  equity: number;
  equity_total_usd?: number;
  allocation?: Record<string, number>;
  tradable_equity_usd?: number;
  state?: OpsState;

  // Hardened Logic Fields
  global_cap_pct?: number;
  hard_cap_pct?: number;
  portfolio_reserve_pct?: number;
  arbitrage_reserve_pct?: number;
  locked_reserve_pct?: number;
  usable_cap_pct?: number;
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
  tier?: 'BEGINNER' | 'STD_RETAIL' | 'ADV_RETAIL' | 'INST_LITE' | 'INST_PRO';
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
  latency_ms?: number;
  uptime?: number;
}

export interface HealthcheckResponse {
  status: string;
  uptime_min: number;
  latency_ms: number;
  service: string;
  version: string;
  timestamp: string;
}

export type SystemMode = 'MANUAL' | 'SEMI' | 'AUTO' | 'STOP';


export interface ErrorEnvelope {
  error: string | Record<string, unknown> | Array<unknown>;
}

export interface SpotState {
  enabled: boolean;
  weights: Record<string, number>;
  max_positions: number;
  max_trade_pct: number;
  risk_per_trade_pct: number;
  max_symbol_exposure_pct: number;
  tp_pct_default: number;
  sl_pct_default: number;
}

export interface ExchangeConfig {
  id: string;
  name: string;
  enabled: boolean;
  allocation: number;
  connected: boolean;
  risk_label?: string;
  permissions: {
    read: boolean;
    trade: boolean;
  };
}

export interface ExchangeKey {
  exchange_id: string;
  api_key: string;
  api_secret: string; // masked
  passphrase?: string;
  status: 'CONNECTED' | 'FAILED' | 'Not Configured' | 'ERROR';
  updated_at: string;
  is_testnet: boolean;
  last_latency_ms?: number;
  permissions?: {
    read: boolean;
    trade: boolean;
    withdraw: boolean;
  };
}


export interface StrategyConfig {
  id: string;
  name: string;
  core: string;
  enabled: boolean;
  weight: number;
  horizon: string;
  risk_label: string;
  mode_override: string;
  performance_pct?: number;
  confidence?: number;
  // Metrics (Phase 4.1)
  metric_roi?: number;
  metric_sharpe?: number;
  metric_drawdown?: number;
  metric_win_rate?: number;
}

export interface FundOverview {
  total_aum: number;
  active_accounts: number;
  capital_in_use_pct: number;
  capital_reserved_pct: number;
  capital_free_pct: number;
  active_strategies: number;
  active_exchanges: number;
  health_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  last_updated: string;
}

export interface FundPortfolio {
  asset_allocation: { asset: string; pct: number }[];
  venue_allocation: { venue: string; pct: number }[];
  strategy_allocation: { strategy: string; pct: number }[];
}

export interface FundStrategy {
  id: string;
  name: string;
  deployments: number;
  aum_deployed: number;
  performance_24h: number;
}

export interface FundRisk {
  global_drawdown: number;
  value_at_risk: number;
  compliance_breaches: number;
}

export interface FundAccount {
  id: number;
  email: string;
  tier: string;
  aum: number;
  status: 'ACTIVE' | 'LOCKED' | 'FLAGGED';
}

export interface Tenant {
  id: string;
  name: string;
  users: number;
  status: 'ACTIVE' | 'SUSPENDED';
}

export interface AdminOverview {
  total_tenants: number;
  total_users: number;
  active_sessions: number;
  system_aum_usd: number;
  system_health: Record<string, string>;
  alerts: string[];
}


// Manual Trade Governance
export interface ManualTradeProposal {
  exchange_id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  amount_usd: number;
  strategy_id?: string;
  risk_notes?: string;
  client_ref?: string;
}

export interface ManualTradePreviewResponse {
  allowed: boolean;
  blocking_reason?: string;
  capital_delta_usd?: number;
  projected_usage_pct?: number;
  risk_flags?: string[];
  risk_notes?: string;
  proposal?: ManualTradeProposal;
}


export interface AIProposal {
  id: string;
  type: 'STRATEGY_ADJUSTMENT' | 'CAPITAL_ADJUSTMENT' | 'MANUAL_TRADE';
  payload: Record<string, any>;
  reasoning: string;
  confidence: number;
  risk_notes: string[];
  created_at: string;
}


export interface UndoToken {
  undo_token: string;
  undo_ttl: number;
}

export interface SystemEvent {
  id: string;
  timestamp: string;
  type: string;
  message: string;
  payload: Record<string, any>;
}

export interface ApiResponse<T> {
  data?: T;
  error?: ErrorEnvelope;
}

// --- PHASE 6: INSTITUTIONAL SURFACES EXTRAS ---

export interface StrategyAllocationRow extends StrategyConfig {
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  control_mode: 'MANUAL' | 'AI' | 'HYBRID';
  target_alloc_pct: number; // Slider value 0-1
  current_alloc_pct: number;
}

export interface ExchangeAllocationRow extends ExchangeConfig {
  risk_limit_pct: number;
  usage_pct: number;
  control_source: 'AI' | 'MANUAL';
  total_balance_usd: number;
}

export interface PortfolioDraft {
  id: string;
  risk_profile: 'CONSERVATIVE' | 'BALANCED' | 'AGGRESSIVE';
  timeframe: string;
  selected_assets: string[];
  capital_deployment: number;
  status: 'DRAFT' | 'DEPLOYED';
}

export interface ResearchCard {
  symbol: string;
  icon?: string;
  score: number;
  thesis_short: string;
  thesis_long?: string;
  zones: { entry: string; exit: string; invalidation: string };
  probability: number;
  expected_return: number;
}

export interface ActiveSymbol {
  symbol: string;
  venue: string;
  strategy_id: string;
  side: 'LONG' | 'SHORT';
  pnl_24h: number;
  qty: number;
  entry_price: number;
  mark_price: number;
}

export interface HedgingConfig {
  enabled: boolean;
  strategy_type: 'PUT_LADDER' | 'COLLAR' | 'DELTA_NEUTRAL';
  coverage_pct: number; // 0-1
  cost_basis_bps: number;
  recommended_action?: string;
}

export interface FeatureFlagGroup {
  category: string;
  flags: FeatureFlag[];
}
