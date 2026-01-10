import { OpsState, HealthcheckResponse, SystemMode, StrategyConfig, PortfolioStatus } from '../api/types';

// ------------------------------------------------------------------
// TYPES FOR PREVIEW STORE
// ------------------------------------------------------------------

export interface PreviewUser {
    id: string;
    email: string;
    role: 'ADMIN' | 'TRADER' | 'USER' | 'FUND_MANAGER';
    tier: 'TIER_0' | 'TIER_1' | 'TIER_2' | 'TIER_3' | 'BEGINNER' | 'STD_RETAIL' | 'ADV_RETAIL' | 'INST_LITE';
    trust_score: number;
    enabled_2fa: boolean;
}

// Aligning closely with StrategyConfig from types.ts
export interface PreviewStrategy extends StrategyConfig {
    // Extra internal sim fields
    order_count: number;
    last_updated: string;
}

export interface PreviewPortfolio {
    id: string;
    name: string;
    base_currency: string;
    total_value: number;
    pnl_24h: number;
    status: PortfolioStatus;
    strategies: string[]; // IDs
    risk_profile: string;
    created_at: string;
}

export interface SimOrder {
    id: string;
    strategy_id: string;
    symbol: string;
    side: 'BUY' | 'SELL';
    qty: number;
    price: number;
    status: 'OPEN' | 'FILLED' | 'CANCELED' | 'REJECTED';
    created_ts: string;
}

export interface SimIncident {
    id: string;
    ts: string;
    severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    status: 'OPEN' | 'RESOLVED' | 'INVESTIGATING';
    summary: string;
    remediation?: string;
}

export interface SimFeatureFlag {
    key: string;
    value: boolean;
    description: string;
}

export interface GovernanceEvent {
    id: string;
    type: 'VETO' | 'DRIFT' | 'STOP' | 'MODE_CHANGE' | 'DEPLOY' | 'FLATTEN' | 'INFO' | 'WARNING' | 'AIRLOCK' | 'INTERVENTION' | 'ARCHIVE' | 'SIMULATION';
    severity: 'INFO' | 'WARNING' | 'CRITICAL';
    message: string;
    timestamp: string;
    actor: string;
}

export interface PreviewState {
    ops: OpsState;
    health: HealthcheckResponse;
    users: PreviewUser[];
    strategies: PreviewStrategy[];
    portfolios: PreviewPortfolio[];
    active_user_id: string;
    audit_log: GovernanceEvent[];
    sim_orders: SimOrder[];
    risk_mandates: {
        max_leverage: number;
        global_drawdown_limit: number;
        auto_trading_allowed: boolean;
        capital_cap_pct: number;
    };
    // Admin / System Preview Data
    incidents: SimIncident[];
    feature_flags: SimFeatureFlag[];
    // Flags for simulation behavior
    sim_latency_ms: number;
    sim_offline: boolean;
    backend_reachable: boolean;
    force_sim: boolean;
}

// ------------------------------------------------------------------
// DEFAULT MOCK DATA
// ------------------------------------------------------------------

const INITIAL_OPS: OpsState = {
    auto_mode: false,
    exec_mode: 'MANUAL',
    global_stop: false,
    drift_status: 'NONE',
    veto_reason: null,
    last_governance_event: null,
    airlock_status: 'NOT_READY',
    active_strategies: 2,
    risk_score: 15, // Low risk
    pnl_today: 1250.50
};

const INITIAL_USERS: PreviewUser[] = [
    { id: 'u1', email: 'owner@lunia.fi', role: 'ADMIN', tier: 'INST_LITE', trust_score: 100, enabled_2fa: true },
    { id: 'u2', email: 'trader@lunia.fi', role: 'TRADER', tier: 'ADV_RETAIL', trust_score: 85, enabled_2fa: true },
    { id: 'u3', email: 'viewer@lunia.fi', role: 'USER', tier: 'STD_RETAIL', trust_score: 50, enabled_2fa: false },
];

const INITIAL_STRATEGIES: PreviewStrategy[] = [
    {
        id: 's1',
        name: 'Spot Arbitrage Alpha',
        core: 'ARBITRAGE',
        enabled: true,
        weight: 0.4,
        horizon: 'SHORT_TERM',
        risk_label: 'LOW',
        mode_override: 'AUTO',
        performance_pct: 12.5,
        confidence: 0.95,
        order_count: 2,
        last_updated: new Date().toISOString()
    },
    {
        id: 's2',
        name: 'Trend Following BTC',
        core: 'TREND_MOMENTUM',
        enabled: true,
        weight: 0.6,
        horizon: 'MEDIUM_TERM',
        risk_label: 'MEDIUM',
        mode_override: 'SEMI',
        performance_pct: 45.2,
        confidence: 0.78,
        order_count: 0,
        last_updated: new Date().toISOString()
    }
];

const INITIAL_PORTFOLIOS: PreviewPortfolio[] = [
    { id: 'p1', name: 'Main Fund A', base_currency: 'USDT', total_value: 1250000, pnl_24h: 0.85, status: 'ACTIVE', strategies: ['s1', 's2'], risk_profile: 'BALANCED', created_at: new Date(Date.now() - 86400000 * 30).toISOString() }
];

const INITIAL_FLAGS: SimFeatureFlag[] = [
    { key: 'VITE_PREVIEW_MODE', value: true, description: 'Enable Preview/Simulation Mode' },
    { key: 'ENABLE_DARK_POOL', value: false, description: 'Access to L3 Dark Pool Liquidity' },
    { key: 'AUTO_HEDGING', value: true, description: 'Automated Delta Hedging Service' },
];

const INITIAL_INCIDENTS: SimIncident[] = [
    { id: 'inc-01', ts: new Date(Date.now() - 86400000 * 2).toISOString(), severity: 'MEDIUM', status: 'RESOLVED', summary: 'API Latency Spike > 500ms', remediation: 'Auto-scaled ingest nodes' },
    { id: 'inc-02', ts: new Date(Date.now() - 3600000 * 4).toISOString(), severity: 'LOW', status: 'OPEN', summary: 'Data feed gap for SOL-USDT', remediation: 'Investigating provider fallback' }
];

// ------------------------------------------------------------------
// STORE IMPLEMENTATION (Singleton with Subscriptions)
// ------------------------------------------------------------------

class PreviewStoreService {
    private state: PreviewState;
    private listeners: Set<() => void> = new Set();

    constructor() {
        this.state = {
            ops: { ...INITIAL_OPS },
            health: {
                status: 'ok',
                uptime_min: 420,
                latency_ms: 25,
                service: 'lunia_core_sim',
                version: 'PREVIEW-V1',
                timestamp: new Date().toISOString()
            },
            users: [...INITIAL_USERS],
            strategies: [...INITIAL_STRATEGIES],
            portfolios: [...INITIAL_PORTFOLIOS],
            sim_orders: [
                { id: 'sim-o-1', strategy_id: 's1', symbol: 'BTC/USDT', side: 'BUY', qty: 0.5, price: 42000, status: 'OPEN', created_ts: new Date().toISOString() },
                { id: 'sim-o-2', strategy_id: 's1', symbol: 'ETH/USDT', side: 'SELL', qty: 5.0, price: 2300, status: 'FILLED', created_ts: new Date(Date.now() - 3600000).toISOString() }
            ],
            active_user_id: 'u1',
            audit_log: [],
            risk_mandates: { max_leverage: 3.0, global_drawdown_limit: 0.15, auto_trading_allowed: true, capital_cap_pct: 100 },
            incidents: [...INITIAL_INCIDENTS],
            feature_flags: [...INITIAL_FLAGS],
            sim_latency_ms: 200,
            sim_offline: false,
            backend_reachable: true,
            force_sim: false
        };
        this.addLog('INFO', 'System Started', 'INFO', 'SYSTEM');
    }

    // --- GETTERS ---
    getState = () => this.state;

    // --- SUBSCRIPTION ---
    subscribe = (listener: () => void) => {
        this.listeners.add(listener);
        return () => this.listeners.delete(listener);
    };

    private notify = () => {
        this.listeners.forEach(l => l());
    };

    // --- MUTATION ACTIONS ---

    // 1. OPS & MODES
    setExecMode = (mode: SystemMode) => {
        this.state.ops.exec_mode = mode;
        this.state.ops.auto_mode = mode === 'AUTO';
        this.state.ops.airlock_status = mode === 'AUTO' ? 'ARMED' : 'NOT_READY';
        const msg = `Execution Mode changed to ${mode}`;
        this.addLog('MODE_CHANGE', msg);
        this.notify();
    };

    setGlobalStop = (stop: boolean) => {
        this.state.ops.global_stop = stop;
        if (stop) {
            this.state.ops.exec_mode = 'STOP';
            this.state.ops.veto_reason = "Manual Emergency Stop Engaged";
            this.addLog('STOP', 'Global Emergency Stop Triggered', 'CRITICAL');
        } else {
            this.state.ops.veto_reason = null;
            this.addLog('STOP', 'Global Stop Released', 'INFO');
        }
        this.notify();
    };

    triggerDrift = (type: 'SOFT' | 'HARD' | 'NONE') => {
        this.state.ops.drift_status = type;
        if (type !== 'NONE') {
            const severity = type === 'HARD' ? 'CRITICAL' : 'WARNING';
            const msg = `Simulated ${type} Drift Detected on Main Fund A`;
            this.addLog('DRIFT', msg, severity);
            if (type === 'HARD' && this.state.ops.exec_mode === 'AUTO') {
                this.state.ops.exec_mode = 'MANUAL';
                this.state.ops.auto_mode = false;
                this.addLog('VETO', 'Governance downgrade: AUTO -> MANUAL due to HARD Drift', 'CRITICAL');
            }
        } else {
            this.addLog('DRIFT', 'Drift Resolved', 'INFO');
        }
        this.notify();
    };

    // 2. PORTFOLIOS & STRATEGIES
    deployStrategy = (name: string, weight: number) => {
        const newStrat: PreviewStrategy = {
            id: `s-${Date.now()}`,
            name,
            core: 'CUSTOM',
            enabled: true,
            weight,
            horizon: 'MEDIUM_TERM',
            risk_label: 'MEDIUM',
            mode_override: 'SEMI',
            order_count: 0,
            last_updated: new Date().toISOString()
        };
        this.state.strategies.push(newStrat);
        this.updateActiveStrategiesCount();
        this.addLog('DEPLOY', `Strategy Deployed: ${name}`, 'INFO');
        this.notify();
    };

    duplicateStrategy = (originalId: string, overrides: Partial<StrategyConfig>) => {
        const original = this.state.strategies.find(s => s.id === originalId);
        if (!original) return;

        const newStrat: PreviewStrategy = {
            ...original,
            ...overrides,
            id: `s-${Date.now()}`,
            order_count: 0,
            last_updated: new Date().toISOString()
        };
        this.state.strategies.push(newStrat);
        this.addLog('DEPLOY', `Strategy Cloned: ${newStrat.name} from ${originalId}`, 'INFO');
        this.notify();
    }

    archiveStrategy = (id: string) => {
        const idx = this.state.strategies.findIndex(s => s.id === id);
        if (idx > -1) {
            const name = this.state.strategies[idx].name;
            this.state.strategies.splice(idx, 1);
            this.updateActiveStrategiesCount();
            this.addLog('ARCHIVE', `Strategy Archived: ${name}`, 'WARNING');
            this.notify();
        }
    }

    // Toggle Strategy Enabled State
    toggleStrategy = (id: string, enabled: boolean) => {
        const s = this.state.strategies.find(st => st.id === id);
        if (s) {
            s.enabled = enabled;
            this.updateActiveStrategiesCount();
            this.addLog('INFO', `Strategy ${s.name} ${enabled ? 'RESUMED' : 'PAUSED'}`, 'INFO');
            this.notify();
        }
    }

    private updateActiveStrategiesCount() {
        this.state.ops.active_strategies = this.state.strategies.filter(s => s.enabled).length;
    }

    flattenPortfolio = () => {
        this.state.ops.active_strategies = 0;
        this.state.strategies.forEach(s => s.enabled = false);
        this.setGlobalStop(true);
        this.addLog('FLATTEN', 'Portfolio FLATTENED by Operator', 'CRITICAL');
        this.notify();
    };

    // 3. ADMIN / USERS
    setActiveUser = (userId: string) => {
        const user = this.state.users.find(u => u.id === userId);
        if (user) {
            this.state.active_user_id = userId;
            this.notify();
        }
    };

    updateUserTier = (userId: string, tier: PreviewUser['tier']) => {
        const user = this.state.users.find(u => u.id === userId);
        if (user) {
            user.tier = tier;
            this.addLog('INFO', `User ${user.email} tier updated to ${tier.toString()}`);
            this.notify();
        }
    };

    // 4. SIMULATION ORDERS
    getOrders = (strategyId: string) => {
        return this.state.sim_orders.filter(o => o.strategy_id === strategyId);
    }

    cancelSimOrder = (orderId: string) => {
        const order = this.state.sim_orders.find(o => o.id === orderId);
        if (order && order.status === 'OPEN') {
            order.status = 'CANCELED';
            // Update strategy order count?
            const strategy = this.state.strategies.find(s => s.id === order.strategy_id);
            if (strategy) strategy.order_count = Math.max(0, strategy.order_count - 1);

            this.addLog('INTERVENTION', `Order ${orderId} CANCELED by Operator`, 'INFO');
            this.notify();
        }
    }

    simulateStrategyRun = (id: string) => {
        const s = this.state.strategies.find(x => x.id === id);
        if (!s) return;

        // Deterministic simulation
        const isBuy = Math.random() > 0.5;
        const newOrder: SimOrder = {
            id: `sim-o-${Date.now()}`,
            strategy_id: id,
            symbol: 'BTC/USDT',
            side: isBuy ? 'BUY' : 'SELL',
            qty: parseFloat((Math.random() * 2).toFixed(4)),
            price: 65000 + (Math.random() * 1000),
            status: 'OPEN',
            created_ts: new Date().toISOString()
        };
        this.state.sim_orders.push(newOrder);
        s.order_count++;
        s.last_updated = new Date().toISOString();
        this.addLog('SIMULATION', `Strategy ${s.name} executed ${newOrder.side} ${newOrder.qty} BTC`, 'INFO');
        this.notify();
    }

    // 5. SIMULATION CONTROLS
    toggleOffline = () => {
        this.state.sim_offline = !this.state.sim_offline;
        this.state.health.status = this.state.sim_offline ? 'error' : 'ok';
        this.notify();
    };

    setBackendReachable = (reachable: boolean) => {
        if (this.state.backend_reachable === reachable) return;
        this.state.backend_reachable = reachable;
        if (!reachable) {
            this.addLog('WARNING', 'Backend Connection Lost - Switching to SIM', 'WARNING');
        } else {
            this.addLog('INFO', 'Backend Connection Restored', 'INFO');
        }
        this.notify();
    };

    setForceSim = (force: boolean) => {
        this.state.force_sim = force;
        this.notify();
    };

    // 6. ADMIN ACTIONS
    toggleFeatureFlag = (key: string) => {
        const flag = this.state.feature_flags.find(f => f.key === key);
        if (flag) {
            flag.value = !flag.value;
            this.addLog('INFO', `Feature Flag ${key} set to ${flag.value}`, 'WARNING');
            this.notify();
        }
    };

    resolveIncident = (id: string) => {
        const inc = this.state.incidents.find(i => i.id === id);
        if (inc) {
            inc.status = 'RESOLVED';
            this.addLog('INFO', `Incident ${id} marked RESOLVED`, 'INFO');
            this.notify();
        }
    };

    setCapitalCap = (pct: number) => {
        this.state.risk_mandates.capital_cap_pct = Math.min(100, Math.max(0, pct));
        this.addLog('INFO', `Global Capital Cap adjusted to ${pct}%`, 'WARNING');
        this.notify();
    };

    // --- INTERNALS ---
    addLog(type: GovernanceEvent['type'], message: string, severity: GovernanceEvent['severity'] = 'INFO', actor: string = 'SYSTEM') {
        const event: GovernanceEvent = {
            id: `evt-${Date.now()}`,
            type,
            message,
            severity,
            timestamp: new Date().toISOString(),
            actor
        };
        this.state.audit_log.unshift(event);
        if (this.state.audit_log.length > 50) this.state.audit_log.pop();

        this.state.ops.last_governance_event = {
            id: event.id,
            message: event.message,
            timestamp: event.timestamp,
            severity: event.severity
        };
    }

    getCurrentUser() {
        return this.state.users.find(u => u.id === this.state.active_user_id) || this.state.users[0];
    }
}

export const previewStore = new PreviewStoreService();
