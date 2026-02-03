import React from 'react';
import { OpsState } from '../../api/types';
import { DataFreshnessState, DataFreshnessMetrics } from '../../api/epoch_a_types';

interface GovernanceStatusStripProps {
    ops: OpsState | null;
    healthStatus?: string;
    isSimulation?: boolean;
}

/**
 * Computes data freshness state from available timestamps
 * FAIL-CLOSED: Missing data = OFFLINE
 */
function computeFreshness(ops: OpsState | null, healthStatus?: string): DataFreshnessMetrics {
    const now = Date.now();
    const reasons: string[] = [];

    // No data = OFFLINE
    if (!ops) {
        return {
            state: 'OFFLINE',
            opsAge: Infinity,
            healthAge: Infinity,
            lastUpdate: 'never',
            reasons: ['No ops state available']
        };
    }

    // Compute age from last update if available
    const opsUpdated = (ops as any).last_updated || (ops as any).updated_at;
    const opsAge = opsUpdated ? now - new Date(opsUpdated).getTime() : Infinity;

    // Health check age (if health endpoint provides timestamp)
    const healthAge = healthStatus === 'ok' ? 0 : Infinity;

    // Freshness thresholds (from implementation plan)
    const FRESH_THRESHOLD = 10000;    // 10s
    const STALE_THRESHOLD = 30000;    // 30s

    let state: DataFreshnessState = 'FRESH';

    if (opsAge === Infinity) {
        state = 'OFFLINE';
        reasons.push('No timestamp available');
    } else if (opsAge > STALE_THRESHOLD) {
        state = 'DEGRADED';
        reasons.push(`Ops state ${Math.round(opsAge / 1000)}s old (threshold: 30s)`);
    } else if (opsAge > FRESH_THRESHOLD) {
        state = 'STALE';
        reasons.push(`Ops state ${Math.round(opsAge / 1000)}s old (threshold: 10s)`);
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

export const GovernanceStatusStrip: React.FC<GovernanceStatusStripProps> = ({
    ops,
    healthStatus,
    isSimulation
}) => {
    const freshness = computeFreshness(ops, healthStatus);

    // Extract governance states
    const globalStop = ops?.global_stop || false;
    const systemMode = ops?.system_mode || 'MANUAL';
    const runMode = ops?.run_state?.run_mode || 'dry';
    const airlockStatus = ops?.airlock_status || 'NOT_READY';
    const driftStatus = ops?.drift_status || 'NONE';
    const vetoReason = ops?.veto_reason;
    const liveAllowed = ops?.live_allowed || false;

    // Color coding
    const getStatusColor = (isGood: boolean) => isGood ? 'var(--accent-success)' : 'var(--accent-danger)';
    const getFreshnessColor = (state: DataFreshnessState) => {
        switch (state) {
            case 'FRESH': return 'var(--accent-success)';
            case 'STALE': return 'var(--accent-warning)';
            case 'DEGRADED': return 'var(--accent-danger)';
            case 'OFFLINE': return '#666';
            default: return '#999';
        }
    };

    const getModeColor = (mode: string) => {
        switch (mode) {
            case 'STOP': return 'var(--accent-danger)';
            case 'AUTO': return 'var(--accent-info)';
            case 'SEMI': return 'var(--accent-warning)';
            case 'MANUAL': return 'var(--text-primary)';
            default: return '#999';
        }
    };

    return (
        <div
            style={{
                position: 'sticky',
                top: 0,
                zIndex: 100,
                background: 'var(--bg-secondary)',
                borderBottom: '1px solid var(--border-color)',
                padding: '0.75rem 1rem',
                display: 'flex',
                gap: '1rem',
                alignItems: 'center',
                flexWrap: 'wrap',
                fontSize: '0.875rem'
            }}
        >
            {/* SIMULATION MODE INDICATOR */}
            {isSimulation && (
                <div
                    style={{
                        background: 'rgba(245, 158, 11, 0.2)',
                        color: 'var(--accent-warning)',
                        padding: '0.25rem 0.5rem',
                        borderRadius: '4px',
                        fontWeight: 'bold',
                        border: '1px solid var(--accent-warning)'
                    }}
                >
                    🔬 SIMULATION MODE
                </div>
            )}

            {/* GLOBAL STOP */}
            <div
                title={globalStop ? 'Global emergency stop active' : 'System operational'}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: globalStop ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.1)',
                    border: `1px solid ${getStatusColor(!globalStop)}`
                }}
            >
                <span>{globalStop ? '🛑' : '✅'}</span>
                <span style={{ color: getStatusColor(!globalStop), fontWeight: '500' }}>
                    {globalStop ? 'STOP ACTIVE' : 'OPERATIONAL'}
                </span>
            </div>

            {/* SYSTEM MODE */}
            <div
                title={`Governance mode: ${systemMode}`}
                style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: 'var(--bg-darker)',
                    border: `1px solid ${getModeColor(systemMode)}`
                }}
            >
                <span style={{ color: '#999', fontSize: '0.75rem' }}>MODE:</span>{' '}
                <span style={{ color: getModeColor(systemMode), fontWeight: '500' }}>{systemMode}</span>
            </div>

            {/* RUN MODE */}
            <div
                title={runMode === 'real' ? 'LIVE TRADING ACTIVE' : 'Dry run mode'}
                style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: runMode === 'real' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                    border: `1px solid ${runMode === 'real' ? 'var(--accent-danger)' : '#64748b'}`
                }}
            >
                <span>{runMode === 'real' ? '🔴' : '🟡'}</span>{' '}
                <span style={{ fontWeight: '500', color: runMode === 'real' ? 'var(--accent-danger)' : '#94a3b8' }}>
                    {runMode.toUpperCase()}
                </span>
            </div>

            {/* AIRLOCK STATUS */}
            <div
                title={`Airlock: ${airlockStatus}${vetoReason ? ` - ${vetoReason}` : ''}`}
                style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: airlockStatus === 'ARMED' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    border: `1px solid ${airlockStatus === 'ARMED' ? 'var(--accent-success)' : 'var(--accent-danger)'}`
                }}
            >
                <span style={{ fontSize: '0.75rem', color: '#999' }}>AIRLOCK:</span>{' '}
                <span style={{ fontWeight: '500', color: airlockStatus === 'ARMED' ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                    {airlockStatus}
                </span>
            </div>

            {/* DRIFT STATUS */}
            {driftStatus && driftStatus !== 'NONE' && (
                <div
                    title={`Drift detected: ${driftStatus}`}
                    style={{
                        padding: '0.25rem 0.5rem',
                        borderRadius: '4px',
                        background: 'rgba(245, 158, 11, 0.2)',
                        border: '1px solid var(--accent-warning)'
                    }}
                >
                    <span>⚠️</span>{' '}
                    <span style={{ fontWeight: '500', color: 'var(--accent-warning)' }}>DRIFT: {driftStatus}</span>
                </div>
            )}

            {/* DATA FRESHNESS (CRITICAL) */}
            <div
                title={`Data freshness: ${freshness.state}\n${freshness.reasons.join('\n')}`}
                style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: freshness.state === 'FRESH' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    border: `1px solid ${getFreshnessColor(freshness.state)}`,
                    cursor: 'help'
                }}
            >
                <span style={{ fontSize: '0.75rem', color: '#999' }}>DATA:</span>{' '}
                <span style={{ fontWeight: '500', color: getFreshnessColor(freshness.state) }}>
                    {freshness.state}
                </span>
                {freshness.opsAge !== Infinity && (
                    <span style={{ fontSize: '0.75rem', color: '#666', marginLeft: '0.25rem' }}>
                        ({Math.round(freshness.opsAge / 1000)}s)
                    </span>
                )}
            </div>

            {/* SERVER ARM STATUS */}
            <div
                title={liveAllowed ? 'Server armed for live trading' : 'Server not armed (LIVE_ALLOWED=0)'}
                style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: liveAllowed ? 'rgba(34, 197, 94, 0.1)' : 'rgba(100, 116, 139, 0.2)',
                    border: `1px solid ${liveAllowed ? 'var(--accent-success)' : '#64748b'}`
                }}
            >
                <span style={{ fontSize: '0.75rem', color: '#999' }}>SERVER:</span>{' '}
                <span style={{ fontWeight: '500', color: liveAllowed ? 'var(--accent-success)' : '#94a3b8' }}>
                    {liveAllowed ? 'ARMED' : 'SAFE'}
                </span>
            </div>

            {/* VETO REASON (if present) */}
            {vetoReason && (
                <div
                    style={{
                        padding: '0.25rem 0.5rem',
                        borderRadius: '4px',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid var(--accent-danger)',
                        flex: '1 1 auto',
                        minWidth: '200px'
                    }}
                >
                    <span style={{ fontSize: '0.75rem', color: '#999' }}>VETO:</span>{' '}
                    <span style={{ color: 'var(--accent-danger)', fontSize: '0.8125rem' }}>{vetoReason}</span>
                </div>
            )}
        </div>
    );
};
