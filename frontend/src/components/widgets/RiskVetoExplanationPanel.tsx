import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getOpsState } from '../../api/adapter';
import type { OpsState } from '../../api/types';

export const RiskVetoExplanationPanel: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };
    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'ops_RiskVetoExplanationPanel',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 3000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

    const isGlobalStop = ops.data?.global_stop;
    const vetoReason = ops.data?.veto_reason;
    const driftStatus = ops.data?.drift_status;

    if (!isGlobalStop && (!driftStatus || driftStatus === 'NONE')) return null;

    return (
        <div className="card" style={{ borderColor: 'var(--expert-color)', backgroundColor: 'rgba(255, 68, 68, 0.05)' }}>
            <div className="card-header" style={{ color: 'var(--expert-color)' }}>
                <h3>⚠️ Governance Intervention Active</h3>
            </div>
            <div className="card-body">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>

                    {isGlobalStop && (
                        <div className="alert error icon-alert">
                            <div>
                                <strong>Global Kill Switch Engaged</strong>
                                <p>{vetoReason || "Manual Emergency Stop"}</p>
                            </div>
                        </div>
                    )}

                    {driftStatus === 'HARD' && (
                        <div className="alert warn icon-alert">
                            <div>
                                <strong>Portfolio Drift Violation</strong>
                                <p>Holdings have deviated significantly from the Model. Trading is suspended until reconciled.</p>
                            </div>
                        </div>
                    )}

                    <div className="remediation-steps small muted">
                        <strong>Remediation Steps:</strong>
                        <ul style={{ paddingLeft: '20px', marginTop: '4px' }}>
                            {isGlobalStop && <li>Admin must manually resume trading via Governance Console.</li>}
                            {driftStatus === 'HARD' && <li>Execute rebalancing trade or update Strategy Weights to match reality.</li>}
                            <li>Check System Logs for root cause.</li>
                        </ul>
                    </div>

                </div>
            </div>
        </div>
    );
};
