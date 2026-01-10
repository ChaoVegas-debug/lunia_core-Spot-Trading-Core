import {
    HealthcheckResponse,
    OpsState,
    SystemMode,
    PortfolioDefinition,
    ExchangeConfig,
    StrategyConfig,
    UserProfile,
    ManualTradePreviewResponse,
    AIProposal,
    SystemEvent,
    AuditEvent,
    PortfolioAggregate,
    AdminOverview,
    FundOverview,
    FundPortfolio,
    FundStrategy,
    FundRisk,
    FundAccount,
    FeatureFlag,
    ExchangeKey,
    SpotRiskConfig,
    ActiveSymbol,
    HedgingConfig,
    StrategyAllocationRow,
    ExchangeAllocationRow,
    ActivityItem
} from '../api/types';

// Default Simulated States
const DEFAULT_SIM_HEALTH: HealthcheckResponse = {
    status: 'ok',
    uptime_min: 123.4,
    latency_ms: 42,
    service: 'lunia_core_simulated',
    version: '0.0.0-sim',
    timestamp: new Date().toISOString()
};

// Safe Unlock for Preview Mode
const isPreviewUnlocks = import.meta.env.VITE_PREVIEW_MODE === '1';

const DEFAULT_SIM_OPS: OpsState = {
    auto_mode: isPreviewUnlocks ? true : false, // Show active state
    exec_mode: isPreviewUnlocks ? 'SEMIAUTO' : 'MANUAL',
    global_stop: false,
    drift_status: 'NONE',
    veto_reason: null,
    last_governance_event: null,
    airlock_status: isPreviewUnlocks ? 'ARMED' : 'NOT_READY', // Prevent Airlock Block
    active_strategies: isPreviewUnlocks ? 3 : 0,
    risk_score: 12,
    pnl_today: 1250.50
};

// State Store (in-memory for session)
let currentSimOps: OpsState = { ...DEFAULT_SIM_OPS };
let currentSimHealth: HealthcheckResponse = { ...DEFAULT_SIM_HEALTH };
let exchangeKeys: ExchangeKey[] = [
    { exchange_id: 'binance', api_key: 'A1B2...99X', api_secret: '***', status: 'CONNECTED', updated_at: new Date().toISOString(), is_testnet: false, permissions: { read: true, trade: true, withdraw: false }, last_latency_ms: 45 },
    { exchange_id: 'okx', api_key: '77F3...22Q', api_secret: '***', status: 'FAILED', updated_at: new Date(Date.now() - 86400000).toISOString(), is_testnet: true, permissions: { read: true, trade: true, withdraw: false } }
];

// Phase 5 State
let arb_enabled = false;
let user_language: 'EN' | 'PL' | 'RU' = 'EN';

const mock_balances = [
    { asset: 'USDT', free: 25420.50, locked: 5000.00 },
    { asset: 'USDC', free: 12000.00, locked: 0.00 },
    { asset: 'BTC', free: 1.245, locked: 0.1 },
    { asset: 'ETH', free: 15.4, locked: 2.5 },
    { asset: 'SOL', free: 450.0, locked: 0.0 }
];

const isProofMode = import.meta.env.VITE_PROOF_MODE === '1';

const generateMockOrders = () => {
    if (isProofMode) {
        return [{ id: 'ord-1', time: new Date().toISOString(), symbol: 'BTC/USDT', side: 'BUY' as const, qty: 0.1, price: 64200, status: 'FILLED', strategy: 'SCALP', venue: 'BINANCE' }];
    }
    return [
        { id: 'ord-1', time: new Date(Date.now() - 1000 * 60 * 5).toISOString(), symbol: 'BTC/USDT', side: 'BUY' as const, qty: 0.1, price: 64200, status: 'FILLED', strategy: 'SCALP', venue: 'BINANCE' },
        { id: 'ord-2', time: new Date(Date.now() - 1000 * 60 * 30).toISOString(), symbol: 'ETH/USDT', side: 'SELL' as const, qty: 2.5, price: 3450, status: 'FILLED', strategy: 'TREND', venue: 'KRAKEN' },
        { id: 'ord-3', time: new Date(Date.now() - 1000 * 60 * 120).toISOString(), symbol: 'SOL/USDT', side: 'BUY' as const, qty: 50, price: 145.2, status: 'OPEN', strategy: 'ARB', venue: 'BINANCE' },
    ];
};

const generateMockResearch = () => {
    if (isProofMode) {
        return [{ symbol: 'BTC', thesis: 'Proof Mode Thesis', zone_buy: '60k', zone_sell: '70k', confidence: 99, risk: 'LOW' }];
    }
    return [
        { symbol: 'BTC', thesis: 'Institutional Accumulation', zone_buy: '62k-64k', zone_sell: '72k+', confidence: 88, risk: 'LOW' },
        { symbol: 'ETH', thesis: 'L2 Activity Spike', zone_buy: '3200', zone_sell: '3800', confidence: 75, risk: 'MED' },
        { symbol: 'SOL', thesis: 'Network Congestion Risk', zone_buy: '130', zone_sell: '160', confidence: 60, risk: 'HIGH' }
    ];
};

// --- DATA STORE ---
let strategyAllocations: StrategyAllocationRow[] = [
    { id: 's1', name: 'Spot Carry', core: 'ARBITRAGE', horizon: 'SHORT', risk_label: 'LOW', enabled: true, weight: 0.4, mode_override: 'AUTO', priority: 'HIGH', control_mode: 'AI', target_alloc_pct: 0.4, current_alloc_pct: 0.38 },
    { id: 's2', name: 'Trend Following', core: 'TREND', horizon: 'LONG', risk_label: 'MEDIUM', enabled: true, weight: 0.3, mode_override: 'AUTO', priority: 'MEDIUM', control_mode: 'HYBRID', target_alloc_pct: 0.3, current_alloc_pct: 0.31 },
    { id: 's3', name: 'Market Making', core: 'MM', horizon: 'ULTRA_SHORT', risk_label: 'HIGH', enabled: false, weight: 0.1, mode_override: 'MANUAL', priority: 'LOW', control_mode: 'MANUAL', target_alloc_pct: 0.1, current_alloc_pct: 0.0 }
];

let exchangeAllocations: ExchangeAllocationRow[] = [
    { id: 'binance', name: 'Binance', enabled: true, connected: true, allocation: 0.5, permissions: { read: true, trade: true }, risk_limit_pct: 0.25, usage_pct: 0.15, control_source: 'AI', total_balance_usd: 540000 },
    { id: 'coinbase', name: 'Coinbase', enabled: true, connected: true, allocation: 0.3, permissions: { read: true, trade: true }, risk_limit_pct: 0.15, usage_pct: 0.10, control_source: 'AI', total_balance_usd: 320000 },
    { id: 'okx', name: 'OKX', enabled: true, connected: true, allocation: 0.2, permissions: { read: true, trade: true }, risk_limit_pct: 0.10, usage_pct: 0.02, control_source: 'MANUAL', total_balance_usd: 140000 }
];

export const simulatedBackend = {
    // --- APP BOOT ---
    getHealth: (): HealthcheckResponse => {
        return { ...currentSimHealth, timestamp: new Date().toISOString() };
    },

    getStatus: () => ({ status: 'ok', components: { db: 'ok', redis: 'ok' } }),

    // --- PHASE 4/5 EXPANSION ---
    // User Prefs
    // Arbitrage State
    // Mock Data Store
    // --- ACTIONS ---

    toggleArbitrage: (enabled: boolean) => {
        arb_enabled = enabled;
        // For now, we'll just update currentSimOps.last_governance_event for a mock event
        currentSimOps.last_governance_event = {
            id: 'sim-arb-toggle-' + Date.now(),
            message: `Arbitrage Core ${enabled ? 'ENABLED' : 'DISABLED'}`,
            timestamp: new Date().toISOString(),
            severity: 'INFO'
        };
        return { success: true, enabled };
    },

    setUserLanguage: (lang: 'EN' | 'PL' | 'RU') => {
        user_language = lang;
        return { success: true, lang };
    },

    getBalances: () => ({ balances: mock_balances }),
    getOrders: () => ({ orders: generateMockOrders(), fills: generateMockOrders().filter(o => o.status === 'FILLED') }),
    getResearch: () => ({ items: generateMockResearch() }),

    getOpsState: (): OpsState => {
        return {
            ...currentSimOps,
            arb_on: arb_enabled, // Reflect new arb_enabled state
            last_drift_check: new Date().toISOString(), // Add a mock last_drift_check
            undo_token: 'sim-undo-123', // Mock undo token
            undo_ttl: 300 // Mock undo TTL
        };
    },

    getCurrentUser: (): UserProfile => {
        return {
            id: 1,
            email: 'simulated@lunia.dev',
            role: 'ADMIN',
            tier: 'INST_LITE',
            is_active: true,
            onboarding_completed: true, // Force Completed
            kyc_status: 'VERIFIED',
            created_at: new Date().toISOString(),
            preferences: {
                language: user_language // Reflect user language
            }
        } as any;
    },

    getOpsCapital: () => ({ cap_pct: 1.0, equity: 1000000, global_cap_pct: 1.0 }),

    // --- PHASE 6: INSTITUTIONAL SURFACES ---

    getActiveSymbols: (): ActiveSymbol[] => {
        if (isProofMode) return [{ symbol: 'BTC/USDT', venue: 'Binance', strategy_id: 's1', side: 'LONG', pnl_24h: 1.2, qty: 0.5, entry_price: 61000, mark_price: 61730 }];
        return [
            { symbol: 'BTC/USDT', venue: 'Binance', strategy_id: 's1', side: 'LONG', pnl_24h: 1.2, qty: 0.5, entry_price: 61000, mark_price: 61730 },
            { symbol: 'ETH/USDT', venue: 'OKX', strategy_id: 's2', side: 'SHORT', pnl_24h: -0.5, qty: 5.0, entry_price: 3200, mark_price: 3216 },
            { symbol: 'SOL/USDT', venue: 'Coinbase', strategy_id: 's1', side: 'LONG', pnl_24h: 3.5, qty: 150, entry_price: 130, mark_price: 134.5 }
        ];
    },

    getActionFeed: (): ActivityItem[] => {
        if (isProofMode) return [{ ts: new Date().toISOString(), actor: 'Strategy: Spot Carry', action: 'PLACED_ORDER', ok: true, details: 'Proof Mode Action' }];
        return [
            { ts: new Date().toISOString(), actor: 'Strategy: Spot Carry', action: 'PLACED_ORDER', ok: true, details: 'Buy 0.1 BTC @ 61500' },
            { ts: new Date(Date.now() - 5000).toISOString(), actor: 'Risk Engine', action: 'CHECK_LIMIT', ok: true, details: 'Exposure within limits' },
            { ts: new Date(Date.now() - 15000).toISOString(), actor: 'Strategy: Trend', action: 'CANCEL_ORDER', ok: true, details: 'Order expired' }
        ];
    },

    getHedgingConfig: (): HedgingConfig => ({
        enabled: true,
        strategy_type: 'COLLAR',
        coverage_pct: 0.8,
        cost_basis_bps: 45,
        recommended_action: 'Buy ETH-2900-PUT (7d)'
    }),

    setHedgingConfig: (config: Partial<HedgingConfig>) => {
        return { success: true, updated: config };
    },

    getStrategyAllocations: (): StrategyAllocationRow[] => strategyAllocations,

    getExchangeAllocations: (): ExchangeAllocationRow[] => exchangeAllocations,

    // --- ACTIONS (INSTITUTIONAL) ---

    setStrategyAllocation: (id: string, pct: number) => {
        const s = strategyAllocations.find(x => x.id === id);
        if (s) {
            s.target_alloc_pct = pct;
            // Simulate immediate effect on active capital
            s.current_alloc_pct = pct * (0.9 + Math.random() * 0.2);
            return { success: true };
        }
        return { success: false };
    },

    setExchangeRiskLimit: (id: string, limit: number) => {
        const e = exchangeAllocations.find(x => x.id === id);
        if (e) {

            e.risk_limit_pct = limit;
            return { success: true };
        }
        return { success: false };
    },

    setExchangeEnabled: (id: string, enabled: boolean) => {
        const e = exchangeAllocations.find(x => x.id === id);
        if (e) {
            e.enabled = enabled;
            return { success: true };
        }
        return { success: false };
    },

    getExchanges: (): ExchangeConfig[] => [
        { id: 'binance', name: 'Binance', enabled: true, connected: true, allocation: 0.4, permissions: { read: true, trade: true } },
        { id: 'coinbase', name: 'Coinbase', enabled: true, connected: true, allocation: 0.6, permissions: { read: true, trade: true } }
    ],

    getExchangeKeys: (): ExchangeKey[] => {
        return [...exchangeKeys];
    },

    updateExchangeKeys: (payload: { exchange_id: string; api_key: string; api_secret: string; passphrase?: string; is_testnet: boolean; permissions?: any }) => {
        const existingIdx = exchangeKeys.findIndex(k => k.exchange_id === payload.exchange_id);
        const newKey: ExchangeKey = {
            exchange_id: payload.exchange_id,
            api_key: payload.api_key.substring(0, 4) + '...' + payload.api_key.substring(payload.api_key.length - 4),
            api_secret: '***', // Always mask immediately
            status: 'Not Configured', // Reset status on update until tested
            updated_at: new Date().toISOString(),
            is_testnet: payload.is_testnet,
            permissions: payload.permissions || { read: true, trade: true, withdraw: false }
        };

        if (existingIdx >= 0) {
            exchangeKeys[existingIdx] = { ...exchangeKeys[existingIdx], ...newKey };
        } else {
            exchangeKeys.push(newKey);
        }

        currentSimOps.last_governance_event = {
            id: 'sim-key-update-' + Date.now(),
            message: `Exchange Key Updated: ${payload.exchange_id} (${payload.is_testnet ? 'TESTNET' : 'LIVE'})`,
            timestamp: new Date().toISOString(),
            severity: 'WARNING' // Ops warning
        };

        return { status: 'updated' };
    },

    deleteExchangeKey: (exchangeId: string) => {
        exchangeKeys = exchangeKeys.filter(k => k.exchange_id !== exchangeId);
        currentSimOps.last_governance_event = {
            id: 'sim-key-del-' + Date.now(),
            message: `Exchange Key Revoked: ${exchangeId}`,
            timestamp: new Date().toISOString(),
            severity: 'WARNING'
        };
        return { status: 'deleted' };
    },

    testExchangeConnection: (exchangeId: string) => {
        const key = exchangeKeys.find(k => k.exchange_id === exchangeId);
        if (!key) throw new Error("Key not found");

        // Deterministic simulation
        const isSuccess = exchangeId !== 'broken_exchange';
        const latency = Math.floor(Math.random() * 50) + 20;

        if (isSuccess) {
            key.status = 'CONNECTED';
            key.last_latency_ms = latency;
        } else {
            key.status = 'FAILED';
        }

        return {
            status: isSuccess ? 'ok' : 'error',
            latency_ms: latency,
            message: isSuccess ? 'Connected' : 'Authentication Failed'
        };
    },

    setExecMode: (mode: SystemMode) => {
        currentSimOps.exec_mode = mode;
        if (mode === 'AUTO') currentSimOps.airlock_status = 'ARMED';
        else currentSimOps.airlock_status = 'NOT_READY';
        return { ...currentSimOps, undo_token: 'sim-undo-123' }; // Return full OpsState
    },

    setGlobalStop: (stop: boolean) => {
        currentSimOps.global_stop = stop;
        if (stop) {
            currentSimOps.exec_mode = 'STOP';
            currentSimOps.veto_reason = 'OPERATOR_OVERRIDE';
            currentSimOps.last_governance_event = {
                id: 'sim-stop-' + Date.now(),
                message: 'Simulated Manual Stop',
                timestamp: new Date().toISOString(),
                severity: 'CRITICAL'
            };
        } else {
            currentSimOps.veto_reason = null;
        }
        return { cap_pct: 0, equity: 0, global_cap_pct: 0 }; // Approx OpsCapital
    },

    // --- PORTFOLIO ---
    getPortfolioStructure: (): PortfolioDefinition[] => {
        // Dynamic status from state if we tracked it per ID, for now using simple toggle
        return [
            {
                id: 'p1',
                type: 'TACTICAL',
                risk_profile: 'BALANCED',
                horizon: '30d',
                assets: [
                    { symbol: 'BTC', weight: 0.4, confidence: 0.9, reason: ['Trend'], sector: 'L1', risk_note: 'High Liq' },
                    { symbol: 'ETH', weight: 0.3, confidence: 0.85, reason: ['Yield'], sector: 'L1', risk_note: 'Med Liq' },
                    { symbol: 'SOL', weight: 0.3, confidence: 0.7, reason: ['Momentum'], sector: 'L1', risk_note: 'High Vol' }
                ],
                rules: { entry_mode: 'MAKER', rebalance_interval_days: 7, profit_take_pct: 0.1, stop_loss_pct: 0.05 },
                status: currentSimOps.global_stop ? 'STOPPED' : (currentSimOps.exec_mode === 'MANUAL' ? 'PAUSED' : 'ACTIVE'), // Heuristic binding
                base_currency: 'USDT',
                total_capital_allocation: 1250000
            }
        ];
    },

    getPortfolioAggregate: (): PortfolioAggregate => {
        // Return rich "Active" mock data
        return {
            equity_total_usd: 1258450.25,
            tradable_equity_usd: 450200.50,
            cap_pct: 0.85, // 85% deployed
            realized_pnl: 12450.00,
            unrealized_pnl: 8450.25,
            reserves: { 'USDT': 150000 },
            positions: [
                { symbol: 'BTC', quantity: 8.54, average_price: 62000.00, unrealized_pnl: 5400.00 },
                { symbol: 'ETH', quantity: 145.2, average_price: 3100.00, unrealized_pnl: 2200.50 },
                { symbol: 'SOL', quantity: 1250.0, average_price: 135.00, unrealized_pnl: 849.75 }
            ],
            balances: [
                { asset: 'USDT', free: 250000, locked: 50000 },
                { asset: 'BTC', free: 0.1, locked: 8.44 }
            ],
            timestamp: new Date().toISOString()
        };
    },

    // Action Helper
    runPortfolioAction: (id: string, action: string) => {
        if (action === 'PAUSE') {
            currentSimOps.exec_mode = 'MANUAL';
        } else if (action === 'RESUME') {
            currentSimOps.exec_mode = 'AUTO';
            currentSimOps.global_stop = false;
        } else if (action === 'DERISK') {
            currentSimOps.global_stop = false;
        }
        return { status: 'ok', action, id };
    },

    setPortfolioDraftConfig: (config: any) => ({ status: 'ok', config }),
    setPortfolioDraftAssets: (assets: string[]) => ({ status: 'ok', assets }),
    analyzePortfolioDraft: () => ({ status: 'ok', analysis: { risk_score: 45, expected_return: 0.12 } }),
    createPortfolio: () => ({ id: 'pf-' + Date.now(), status: 'created' }),

    // --- STRATEGIES ---
    getStrategies: (): StrategyConfig[] => [
        { id: 's1', name: 'Spot Carry', enabled: true, weight: 0.4, core: 'ARBITRAGE', horizon: 'SHORT', risk_label: 'LOW', mode_override: 'AUTO' },
        { id: 's2', name: 'Trend Following', enabled: true, weight: 0.6, core: 'TREND', horizon: 'LONG', risk_label: 'MEDIUM', mode_override: 'AUTO' }
    ],

    // --- SYSTEM / ADMIN ---
    getSystemEvents: () => ({
        items: [
            { id: 'evt-1', type: 'INFO', message: 'Simulated System Started', timestamp: new Date().toISOString(), payload: {} }
        ]
    }),

    getAdminFlags: (): FeatureFlag[] => [
        { key: 'new_ui', value: '1', updated_at: new Date().toISOString() },
        { key: 'beta_features', value: '0', updated_at: new Date().toISOString() }
    ],

    // --- ACTIONS ---
    triggerDrift: (type: 'SOFT' | 'HARD' | 'NONE') => {
        currentSimOps.drift_status = type;
        if (type !== 'NONE') {
            if (type === 'HARD') {
                currentSimOps.exec_mode = 'MANUAL'; // Downgrade from AUTO
            }
            currentSimOps.last_governance_event = {
                id: 'sim-drift-' + Date.now(),
                message: `Simulated ${type} drift detected${type === 'HARD' ? ' (Downgrading to MANUAL)' : ''}`,
                timestamp: new Date().toISOString(),
                severity: type === 'HARD' ? 'CRITICAL' : 'WARNING'
            };
        }
    },

    reset: () => {
        currentSimOps = { ...DEFAULT_SIM_OPS };
        currentSimHealth = { ...DEFAULT_SIM_HEALTH };
    },

    deployStrategy: (name: string) => {
        currentSimOps.last_governance_event = {
            id: 'sim-deploy-' + Date.now(),
            message: `Deployed Strategy: ${name}`,
            timestamp: new Date().toISOString(),
            severity: 'INFO'
        };
        // Return Mock StrategyConfig
        return {
            profile: 'BALANCED', // Mock 
            // In a real scenario we'd return a full config or just success. 
            // Adapter expects { profile: string } from setStrategyProfile or similar. 
            // This function deployStrategy is a helper in sim backend, 
            // Adapter calls it for updateStrategies/setStrategyProfile fallback.
        };
    },

    // --- DATA FEEDS ---
    getLogs: () => ({
        items: [
            { ts: new Date().toISOString(), level: 'INFO', message: 'Simulated Log Stream Connected' },
            { ts: new Date(Date.now() - 60000).toISOString(), level: 'WARN', message: 'Market Volatility High (Sim)' }
        ]
    }),

    getActivity: () => ({
        components: {
            'risk_engine': { status: 'ok', last_tick: Date.now() },
            'strategy_engine': { status: 'ok', last_tick: Date.now() }
        },
        last_actions: [
            { ts: new Date().toISOString(), actor: 'SYSTEM', action: 'DRIFT_CHECK', ok: true, details: 'All systems nominal' }
        ],
        warnings: []
    }),

    getAiProposals: (): AIProposal[] => [
        {
            id: 'sim-ai-1',
            type: 'STRATEGY_ADJUSTMENT',
            payload: { action: 'reduce_risk' },
            reasoning: 'Market volatility index exceeded threshold (Simulated). Recommend reducing exposure.',
            confidence: 0.85,
            risk_notes: ['Low Impact'],
            created_at: new Date().toISOString()
        }
    ],

    getRisk: (): SpotRiskConfig => ({
        max_positions: 5,
        max_trade_pct: 0.1,
        risk_per_trade_pct: 0.02,
        max_symbol_exposure_pct: 0.25,
        tp_pct_default: 0.05,
        sl_pct_default: 0.03
    }),

    // --- GAP CLOSURE PHASE 3 (RISK) ---
    getRiskDashboard: () => ({
        utilization_pct: 0.45,
        current_drawdown_pct: 0.012,
        effective_leverage: 1.2,
        top_exposures: [
            { asset: 'BTC', pct: 0.40, value_usd: 500000 },
            { asset: 'ETH', pct: 0.30, value_usd: 375000 },
            { asset: 'SOL', pct: 0.15, value_usd: 187500 }
        ],
        capital_usage: {
            used: 1062500,
            total: 2500000,
            currency: 'USD'
        }
    }),

    getRiskRules: () => [
        { id: 'rule-01', name: 'Max Allocation', severity: 'CRITICAL', status: 'ACTIVE', description: 'No single asset > 25% of total equity', last_triggered: null },
        { id: 'rule-02', name: 'Min Liquidity', severity: 'WARNING', status: 'ACTIVE', description: 'Only trade assets with > $1M 24h Vol', last_triggered: null },
        { id: 'rule-03', name: 'Privacy Coins', severity: 'CRITICAL', status: 'ACTIVE', description: 'Blocking XMR, ZEC, DASH', last_triggered: '2023-10-25T10:00:00Z' },
        { id: 'rule-04', name: 'Stop Loss Mandate', severity: 'CRITICAL', status: 'MONITOR', description: 'All tactical trades must have SL', last_triggered: null }
    ],

    getRiskMandates: () => [
        { id: 'man-01', label: 'Max Global Drawdown', limit: '5.0%', current: '1.2%', status: 'OK' },
        { id: 'man-02', label: 'Max Leverage', limit: '3.0x', current: '1.2x', status: 'OK' },
        { id: 'man-03', label: 'Capital Ceiling', limit: '$5.0M', current: '$1.06M', status: 'OK' },
        { id: 'man-04', label: 'Auto-Trading', limit: 'Allowed', current: 'Enabled', status: 'OK' }
    ],

    // --- PHASE 4: ACCOUNT & SUBSCRIPTION ---
    getUserProfile: (): UserProfile => ({
        id: 101,
        email: 'trader@hedgefund.com',
        role: 'TRADER',
        tier: 'STD_RETAIL', // Default starting tier for demo
        is_active: true,
        created_at: '2023-01-15T00:00:00Z',
        last_login_at: new Date().toISOString()
    }),

    simulateUpgrade: (newTier: string) => {
        // In a real app this would call an endpoint.
        // Here we just log an audit event.
        return {
            success: true,
            message: `Upgrade request to ${newTier} submitted to compliance.`
        };
    },

    flattenPortfolio: () => {
        currentSimOps.global_stop = true;
        currentSimOps.exec_mode = 'STOP';
        currentSimOps.last_governance_event = {
            id: 'sim-flatten-' + Date.now(),
            message: 'Portfolio FLATTENED by Operator',
            timestamp: new Date().toISOString(),
            severity: 'CRITICAL'
        };
        // Return Mock PortfolioDefinition or similar? 
        return { success: true };
    },

    // --- PHASE 6: ADMIN & SYSTEM ---
    getAdminStats: (): AdminOverview => ({
        total_tenants: 12,
        total_users: 42,
        active_sessions: 35,
        system_aum_usd: 15400000,
        system_health: { db: 'ok', redis: 'ok', engine: 'ok' },
        alerts: []
    }),

    getUsers: (): UserProfile[] => [
        { id: 101, email: 'trader@hedgefund.com', role: 'TRADER', tier: 'STD_RETAIL', is_active: true, created_at: '2023-01-15' },
        { id: 102, email: 'risk@hedgefund.com', role: 'ADMIN', tier: 'INST_LITE', is_active: true, created_at: '2023-02-10' },
        { id: 103, email: 'audit@external.com', role: 'USER', tier: 'BEGINNER', is_active: true, created_at: '2023-03-05' },
        { id: 104, email: 'bot@algo.com', role: 'FUND', tier: 'ADV_RETAIL', is_active: false, created_at: '2023-06-20' }
    ] as UserProfile[],

    updateUserRole: (userId: number, role: string, tier: string) => {
        currentSimOps.last_governance_event = {
            id: 'sim-user-upd-' + Date.now(),
            message: `User ${userId} updated to Role: ${role}, Tier: ${tier}`,
            timestamp: new Date().toISOString(),
            severity: 'WARNING'
        };
        return { success: true };
    },

    setGlobalCapitalCap: (amount: number) => {
        currentSimOps.last_governance_event = {
            id: 'sim-cap-upd-' + Date.now(),
            message: `Global Capital Cap Set to $${amount.toLocaleString()}`,
            timestamp: new Date().toISOString(),
            severity: 'CRITICAL'
        };
        return { success: true };
    },

    // --- MANUAL TRADE SIMULATION ---
    previewManualTrade: (proposal: any): ManualTradePreviewResponse => {
        // Simple logic: Allow everything unless amount > 100k
        const allowed = proposal.amount_usd < 100000;
        return {
            allowed,
            blocking_reason: allowed ? undefined : 'SIMULATED LIMIT: Amount exceeds $100k',
            capital_delta_usd: -proposal.amount_usd,
            projected_usage_pct: 0.45,
            risk_flags: allowed ? [] : ['CAPITAL_LIMIT'],
            risk_notes: allowed ? 'Safe to execute (Simulation)' : 'Blocked by Sim Risk Engine',
            proposal
        };
    },

    executeManualTrade: (proposal: any) => {
        // Log event
        currentSimOps.last_governance_event = {
            id: 'sim-trade-' + Date.now(),
            message: `Manual Trade Executed: ${proposal.side} ${proposal.symbol} ($${proposal.amount_usd})`,
            timestamp: new Date().toISOString(),
            severity: 'INFO'
        };
        return { status: 'executed', result: { id: 'sim-tx-' + Date.now() } };
    },
    // --- PHASE 7: FUND ---
    getFundOverview: (): FundOverview => ({
        total_aum: 15400000,
        active_accounts: 12,
        capital_in_use_pct: 0.85,
        capital_reserved_pct: 0.10,
        capital_free_pct: 0.05,
        active_strategies: 8,
        active_exchanges: 4,
        health_score: 98,
        risk_level: 'LOW',
        last_updated: new Date().toISOString()
    }),

    getFundPortfolio: (): FundPortfolio => ({
        asset_allocation: [
            { asset: 'BTC', pct: 0.45 },
            { asset: 'ETH', pct: 0.35 },
            { asset: 'USDT', pct: 0.15 },
            { asset: 'SOL', pct: 0.05 }
        ],
        venue_allocation: [
            { venue: 'Binance', pct: 0.60 },
            { venue: 'Coinbase', pct: 0.30 },
            { venue: 'Kraken', pct: 0.10 }
        ],
        strategy_allocation: [
            { strategy: 'Spot Carry', pct: 0.4 },
            { strategy: 'Trend Following', pct: 0.5 },
            { strategy: 'Discretionary', pct: 0.1 }
        ]
    }),

    getFundStrategies: (): FundStrategy[] => [
        { id: 's1', name: 'Spot Carry', deployments: 4, aum_deployed: 6000000, performance_24h: 0.05 },
        { id: 's2', name: 'Trend Following', deployments: 8, aum_deployed: 8500000, performance_24h: 1.2 },
        { id: 's3', name: 'Mean Reversion', deployments: 2, aum_deployed: 900000, performance_24h: -0.3 }
    ],

    getFundRisk: (): FundRisk => ({
        global_drawdown: 0.015,
        value_at_risk: 450000,
        compliance_breaches: 0
    }),

    getFundAccounts: (): FundAccount[] => [
        { id: 101, email: 'alpha@fund.com', tier: 'INST_PRO', aum: 5000000, status: 'ACTIVE' },
        { id: 102, email: 'beta@fund.com', tier: 'INST_LITE', aum: 2500000, status: 'ACTIVE' },
        { id: 103, email: 'gamma@fund.com', tier: 'INST_LITE', aum: 1200000, status: 'FLAGGED' }
    ]
};
