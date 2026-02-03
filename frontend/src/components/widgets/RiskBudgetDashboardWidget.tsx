import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getOpsState, getOpsCapital, getRisk } from '../../api/adapter';
import type { OpsState, OpsCapital, SpotRiskConfig } from '../../api/types';

const Gauge = ({ value, max, label, color = 'var(--primary-color)' }: { value: number, max: number, label: string, color?: string }) => {
    const pct = Math.min(100, Math.max(0, (value / max) * 100));
    return (
        <div style={{ textAlign: 'center', flex: 1 }}>
            <div className="small muted uppercase mb-1">{label}</div>
            <div style={{
                height: '8px',
                background: 'var(--bg-deep)',
                borderRadius: '4px',
                overflow: 'hidden',
                position: 'relative',
                marginBottom: '4px'
            }}>
                <div style={{
                    width: `${pct}%`,
                    background: pct > 90 ? 'var(--expert-color)' : color,
                    height: '100%',
                    transition: 'width 0.5s ease'
                }} />
            </div>
            <div className="tiny text-mono">
                {value.toFixed(1)} / {max}
            </div>
        </div>
    );
};

export const RiskBudgetDashboardWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };

    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'ops_RiskBudgetDashboardWidget',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 3000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };
    const { data: capitalData, error: capitalError, refresh: capitalRefresh } = usePoller<OpsCapital>({
        key: 'capital_RiskBudgetDashboardWidget',
        endpoint: '/api/capital',
        fetcher: () => getOpsCapital(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const capital = { data: capitalData, error: capitalError, loading: false, refresh: capitalRefresh };
    const { data: riskData, error: riskError, refresh: riskRefresh } = usePoller<SpotRiskConfig>({
        key: 'risk_RiskBudgetDashboardWidget',
        endpoint: '/api/risk',
        fetcher: () => getRisk(new AbortController().signal, client),
        interval_ms: 10000,
        critical: false
    });
    const risk = { data: riskData, error: riskError, loading: false, refresh: riskRefresh };

    // Derived Metrics
    const capPct = capital.data?.cap_pct || 100;
    const globalCap = 100; // Hard max

    // Leverage (Mock or from OpsState if available)
    // Assuming simple placeholder for now as backend might not return live leverage often
    const currentLeverage = 1.0;
    const maxLeverage = 3.0; // Institutional standard

    // Position Count
    const currentPositions = Object.keys(ops.data?.spot?.weights || {}).length;
    const maxPositions = risk.data?.max_positions || 5;

    return (
        <div className="card">
            <div className="card-header">
                <h3>Risk Budget</h3>
                <span className="tiny muted">CAPITAL & CONSTRAINTS</span>
            </div>
            <div className="card-body">
                <div style={{ display: 'flex', gap: '16px', justifyContent: 'space-between' }}>
                    <Gauge
                        value={capPct}
                        max={globalCap}
                        label="Capital Deployment"
                        color="var(--cyan)"
                    />
                    <div style={{ width: '1px', background: 'var(--border-color)' }}></div>
                    <Gauge
                        value={currentLeverage}
                        max={maxLeverage}
                        label="Effective Leverage"
                        color="var(--purple)"
                    />
                    <div style={{ width: '1px', background: 'var(--border-color)' }}></div>
                    <Gauge
                        value={currentPositions}
                        max={maxPositions}
                        label="Active Positions"
                        color={currentPositions >= maxPositions ? 'var(--warn-color)' : 'var(--ok-color)'}
                    />
                </div>
            </div>
        </div>
    );
};
