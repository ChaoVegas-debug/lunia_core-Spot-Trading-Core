export type PlanTier = 'BEGINNER' | 'STD_RETAIL' | 'ADV_RETAIL' | 'INST_LITE';
export type RiskProfile = 'LOW' | 'MODERATE' | 'AGGRESSIVE' | 'ROCKET';
export type StrategyClass = 'CLASS_A' | 'CLASS_B' | 'CLASS_C';

export interface SubscriptionPlan {
    id: PlanTier;
    name: string;
    max_active_capital_usd: number;
    max_exchanges: number;
    max_portfolios: number;
    auto_allowed: boolean;
    leverage_cap: number;
    allowed_risk_profiles: RiskProfile[];
    allowed_strategy_classes: StrategyClass[];
    trust_ceiling: number; // 0-3
}

export const PLANS: Record<PlanTier, SubscriptionPlan> = {
    BEGINNER: {
        id: 'BEGINNER',
        name: 'Starter',
        max_active_capital_usd: 1000,
        max_exchanges: 1,
        max_portfolios: 1,
        auto_allowed: false,
        leverage_cap: 1,
        allowed_risk_profiles: ['LOW'],
        allowed_strategy_classes: ['CLASS_A'],
        trust_ceiling: 0
    },
    STD_RETAIL: {
        id: 'STD_RETAIL',
        name: 'Standard',
        max_active_capital_usd: 10000,
        max_exchanges: 2,
        max_portfolios: 3,
        auto_allowed: false, // Beta override applies
        leverage_cap: 3,
        allowed_risk_profiles: ['LOW', 'MODERATE'],
        allowed_strategy_classes: ['CLASS_A'],
        trust_ceiling: 1
    },
    ADV_RETAIL: {
        id: 'ADV_RETAIL',
        name: 'Pro',
        max_active_capital_usd: 50000,
        max_exchanges: 5,
        max_portfolios: 10,
        auto_allowed: true, // Limited
        leverage_cap: 10,
        allowed_risk_profiles: ['LOW', 'MODERATE', 'AGGRESSIVE'],
        allowed_strategy_classes: ['CLASS_A', 'CLASS_B'],
        trust_ceiling: 2
    },
    INST_LITE: {
        id: 'INST_LITE',
        name: 'Institutional',
        max_active_capital_usd: 1000000,
        max_exchanges: 20,
        max_portfolios: 50,
        auto_allowed: true,
        leverage_cap: 20,
        allowed_risk_profiles: ['LOW', 'MODERATE', 'AGGRESSIVE', 'ROCKET'],
        allowed_strategy_classes: ['CLASS_A', 'CLASS_B', 'CLASS_C'],
        trust_ceiling: 3
    }
};

// Plan Logic Handlers

export function getPlan(tier: string | undefined): SubscriptionPlan {
    // Fallback logic
    if (!tier || !PLANS[tier as PlanTier]) return PLANS.BEGINNER;
    return PLANS[tier as PlanTier];
}

export function isAutoAllowed(plan: SubscriptionPlan): boolean {
    // Check global beta override first if needed, but strict plan logic here
    return plan.auto_allowed;
}

export function isRiskProfileAllowed(plan: SubscriptionPlan, profile: string): boolean {
    return plan.allowed_risk_profiles.includes(profile as RiskProfile);
}

export function isStrategyClassAllowed(plan: SubscriptionPlan, stratClass: string): boolean {
    // Default Unknown to most restrictive if not strictly 'CLASS_A'
    const safeClass = stratClass === 'CLASS_A' ? 'CLASS_A' : stratClass as StrategyClass;
    return plan.allowed_strategy_classes.includes(safeClass);
}

export type UIRiskProfile = 'SHIELD' | 'BALANCED' | 'ROCKET';

export function mapUiRiskToDomain(ui: UIRiskProfile): RiskProfile {
    switch (ui) {
        case 'SHIELD': return 'LOW';
        case 'BALANCED': return 'MODERATE';
        case 'ROCKET': return 'AGGRESSIVE'; // Or 'ROCKET' if exists in backend enum, sticking to conservative mapping
        // Logic: SHIELD=LOW, BALANCED=MODERATE, ROCKET=AGGRESSIVE (or ROCKET if supported)
        // Backend types say: 'LOW' | 'MODERATE' | 'AGGRESSIVE' | 'ROCKET'
        // Let's assume ROCKET maps to ROCKET if allowed, else aggressive.
        default: return 'ROCKET';
    }
}

export function checkExchangeLimit(plan: SubscriptionPlan, currentCount: number): boolean {
    return currentCount < plan.max_exchanges;
}

export function isUiRiskAllowed(plan: SubscriptionPlan, ui: UIRiskProfile): boolean {
    // Override: ROCKET UI maps to ROCKET domain.
    // If Backend has ROCKET, we map to it.
    let domain: RiskProfile;
    if (ui === 'SHIELD') domain = 'LOW';
    else if (ui === 'BALANCED') domain = 'MODERATE';
    else domain = 'ROCKET';

    return plan.allowed_risk_profiles.includes(domain);
}

export function normalizeStrategyClass(input?: string): StrategyClass | 'UNVERIFIED' {
    if (input === 'CLASS_C') return 'CLASS_C';
    return 'UNVERIFIED';
}

export interface LockReason {
    isLocked: boolean;
    title: string;
    reason: string;
    requiredTier?: PlanTier;
}

export function getLockReason(
    type: 'AUTO_MODE' | 'EXCHANGE_LIMIT' | 'PORTFOLIO_LIMIT' | 'RISK_PROFILE',
    plan: SubscriptionPlan,
    currentUsage?: number,
    targetProfile?: string
): LockReason {
    switch (type) {
        case 'AUTO_MODE':
            // Note: Caller must handle Beta Flag logic. This is STRICT plan logic.
            if (!plan.auto_allowed) {
                return {
                    isLocked: true,
                    title: "Algorithmic Trading Locked",
                    reason: "Your current plan does not support autonomous execution modes.",
                    requiredTier: 'ADV_RETAIL'
                };
            }
            break;
        case 'EXCHANGE_LIMIT':
            if (currentUsage !== undefined && currentUsage >= plan.max_exchanges) {
                return {
                    isLocked: true,
                    title: "Exchange Limit Reached",
                    reason: `You have reached the limit of ${plan.max_exchanges} connected exchanges on the ${plan.name} plan.`,
                    requiredTier: plan.id === 'INST_LITE' ? undefined : 'ADV_RETAIL' // Simplification
                };
            }
            break;
        case 'PORTFOLIO_LIMIT':
            if (currentUsage !== undefined && currentUsage >= plan.max_portfolios) {
                return {
                    isLocked: true,
                    title: "Portfolio Limit Reached",
                    reason: `You have reached the maximum of ${plan.max_portfolios} active portfolios allowed on the ${plan.name} plan.`,
                    requiredTier: plan.id === 'BEGINNER' ? 'STD_RETAIL' : 'ADV_RETAIL'
                };
            }
            break;
        case 'RISK_PROFILE':
            if (targetProfile && !plan.allowed_risk_profiles.includes(mapUiRiskToDomain(targetProfile as UIRiskProfile))) {
                return {
                    isLocked: true,
                    title: `Risk Profile Restricted`,
                    reason: `The '${targetProfile}' risk engine profile is not available on the ${plan.name} plan due to volatility governance.`,
                    requiredTier: 'INST_LITE'
                };
            }
            break;
    }
    return { isLocked: false, title: '', reason: '' };
}

