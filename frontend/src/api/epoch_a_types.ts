// Data Freshness Types for EPOCH A
export type DataFreshnessState = 'FRESH' | 'STALE' | 'DEGRADED' | 'OFFLINE';

export interface DataFreshnessMetrics {
    state: DataFreshnessState;
    opsAge: number;
    healthAge: number;
    lastUpdate: string;
    reasons: string[];
}

// Proposal Types for EPOCH A
export type ProposalStatus =
    | 'DRAFT'
    | 'PENDING_USER'
    | 'APPROVED'
    | 'EXECUTING'
    | 'MONITORING'
    | 'CLOSED'
    | 'AUTOPSY'
    | 'ARCHIVED'
    | 'REJECTED'
    | 'EXPIRED'
    | 'CANCELLED'
    | 'SUPERSEDED'
    | 'REQUEST_CHANGES';

export type ProposalAction = 'BUY' | 'SELL' | 'HEDGE' | 'REBALANCE';
export type ProposalPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
export type ProposalRiskLabel = 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK' | 'EXTREME_RISK';
export type ProposalHorizon = 'INTRADAY' | 'SWING' | 'POSITION' | 'LONG_TERM';

export interface ProposalFactorAttribution {
    factor: string;
    weight: number; // 0-100, should sum to 100
    confidence: number; // 0-100
}

export interface Proposal {
    id: string;
    asset: string;
    action: ProposalAction;
    status: ProposalStatus;
    confidence: number; // 0-100
    priority: ProposalPriority;
    riskLabel: ProposalRiskLabel;
    riskRewardRatio: number;
    horizon: ProposalHorizon;
    thesisSummary: string;
    factorAttribution: ProposalFactorAttribution[];
    expiresAt?: string;
    createdAt: string;
    updatedAt: string;
    approvedAt?: string;
    rejectedAt?: string;
    rejectionReason?: string;
}

export interface ProposalApprovalGates {
    global_stop: boolean;
    system_mode: SystemMode;
    run_mode: 'dry' | 'real';
    airlock_status: string;
    freshness: DataFreshnessState;
    live_allowed: boolean;
    veto_reason: string | null;
    drift_status: string | null;
    canApprove: boolean;
    blockReasons: string[];
}
