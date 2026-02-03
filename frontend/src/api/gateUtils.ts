import { OpsState } from './types';
import { DataFreshnessState, DataFreshnessMetrics, ProposalApprovalGates, Proposal } from './epoch_a_types';

/**
 * Computes proposal approval gates based on current governance state
 * FAIL-CLOSED: Missing data = blocked
 */
export function computeProposalGates(
    ops: OpsState | null,
    healthStatus?: string
): ProposalApprovalGates {
    // Compute freshness
    const freshness = computeFreshness(ops, healthStatus);

    // Extract governance states (FAIL-CLOSED defaults)
    const global_stop = ops?.global_stop ?? true;
    const system_mode = ops?.system_mode || 'STOP';
    const run_mode = ops?.run_state?.run_mode || 'dry';
    const airlock_status = ops?.airlock_status || 'NOT_READY';
    const live_allowed = ops?.live_allowed ?? false;
    const veto_reason = ops?.veto_reason || null;
    const drift_status = ops?.drift_status || null;

    // Determine if approval is allowed
    const blockReasons: string[] = [];

    if (global_stop) {
        blockReasons.push('Global emergency stop active');
    }

    if (system_mode === 'STOP') {
        blockReasons.push('System in STOP mode');
    }

    if (airlock_status !== 'ARMED') {
        blockReasons.push(`Airlock ${airlock_status}`);
    }

    if (!live_allowed && run_mode === 'real') {
        blockReasons.push('Server not armed for live trading');
    }

    if (freshness.state !== 'FRESH' && run_mode === 'real') {
        blockReasons.push(`Data ${freshness.state} - real approvals require FRESH data`);
    }

    if (drift_status && drift_status !== 'NONE') {
        blockReasons.push(`Drift detected: ${drift_status}`);
    }

    const canApprove = blockReasons.length === 0;

    return {
        global_stop,
        system_mode,
        run_mode,
        airlock_status,
        freshness: freshness.state,
        live_allowed,
        veto_reason,
        drift_status,
        canApprove,
        blockReasons
    };
}

/**
 * Computes data freshness from ops state and health status
 * FAIL-CLOSED: No data = OFFLINE
 */
function computeFreshness(ops: OpsState | null, healthStatus?: string): DataFreshnessMetrics {
    const now = Date.now();
    const reasons: string[] = [];

    if (!ops) {
        return {
            state: 'OFFLINE',
            opsAge: Infinity,
            healthAge: Infinity,
            lastUpdate: 'never',
            reasons: ['No ops state available']
        };
    }

    // Try to extract timestamp
    const opsUpdated = (ops as any).last_updated || (ops as any).updated_at;
    const opsAge = opsUpdated ? now - new Date(opsUpdated).getTime() : Infinity;
    const healthAge = healthStatus === 'ok' ? 0 : Infinity;

    // Thresholds
    const FRESH_THRESHOLD = 10000; // 10s
    const STALE_THRESHOLD = 30000; // 30s

    let state: DataFreshnessState = 'FRESH';

    if (opsAge === Infinity) {
        state = 'OFFLINE';
        reasons.push('No timestamp available');
    } else if (opsAge > STALE_THRESHOLD) {
        state = 'DEGRADED';
        reasons.push(`Ops state ${Math.round(opsAge / 1000)}s old`);
    } else if (opsAge > FRESH_THRESHOLD) {
        state = 'STALE';
        reasons.push(`Ops state ${Math.round(opsAge / 1000)}s old`);
    }

    if (healthStatus !== 'ok') {
        if (state === 'FRESH') state = 'STALE';
        reasons.push('Health check degraded');
    }

    return {
        state,
        opsAge,
        healthAge,
        lastUpdate: opsUpdated || 'unknown',
        reasons
    };
}

/**
 * Filter proposals by search/filter criteria
 */
export function filterProposals(
    proposals: Proposal[],
    searchTerm: string
): Proposal[] {
    if (!searchTerm.trim()) return proposals;

    const term = searchTerm.toLowerCase();
    return proposals.filter(p =>
        p.asset.toLowerCase().includes(term) ||
        p.thesisSummary.toLowerCase().includes(term) ||
        p.status.toLowerCase().includes(term)
    );
}
