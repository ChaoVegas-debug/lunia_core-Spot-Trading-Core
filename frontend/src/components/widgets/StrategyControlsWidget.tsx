import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getStrategies, updateStrategies, haltStrategies, setStrategyProfile } from '../../api/adapter';
import type { StrategyConfig } from '../../api/types';
import { DataStatus } from '../common/DataStatus';
import { useSemiAuto } from '../../hooks/useSemiAuto';
import { ProposalPreviewModal } from '../common/ProposalPreviewModal';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { undoAction } from '../../api/adapter';

interface StrategyControlsWidgetProps {
    onDeploy?: () => void;
}

export const StrategyControlsWidget: React.FC<StrategyControlsWidgetProps> = ({ onDeploy }) => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

    const { data, error, refresh } = usePoller<StrategyConfig[]>({
        key: 'data_StrategyControlsWidget',
        endpoint: '/api/strategies',
        fetcher: () => getStrategies(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const loading = false;
    const lastUpdated = undefined;

    const executeUpdate = async (finalData: StrategyConfig[], key?: string) => {
        await updateStrategies(finalData, new AbortController().signal, client, key);
    };

    const flow = useSemiAuto<StrategyConfig[]>(data || [], executeUpdate);

    useEffect(() => {
        if (data && flow.state === 'IDLE') {
            flow.stageChange(data);
        }
    }, [data, flow.state]);

    const toggleStrategy = (id: string) => {
        const newState = flow.stagedData.map(s => s.id === id ? { ...s, enabled: !s.enabled } : s);
        flow.stageChange(newState);
    };

    const updateWeight = (id: string, val: number) => {
        const newState = flow.stagedData.map(s => s.id === id ? { ...s, weight: val } : s);
        flow.stageChange(newState);
    };

    return (
        <div className="card">
            <div className="card-header">
                <h3>Strategy Composition</h3>
            </div>
            <div className="table-container">
                {(!data || data.length === 0) ? (
                    <div className="empty-state" style={{ padding: '2rem', textAlign: 'center', opacity: 0.7 }}>
                        <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>📉</div>
                        <h3>No Active Strategies</h3>
                        <p className="small muted mb-4">Deploy a new strategy to begin automated trading.</p>
                        {onDeploy && (
                            <button className="button primary" onClick={onDeploy}>
                                + DEPLOY STRATEGY
                            </button>
                        )}
                    </div>
                ) : (
                    <table className="table compact">
                        <thead>
                            <tr>
                                <th>Strategy</th>
                                <th>Mode</th>
                                <th>Metrics</th>
                                <th>State</th>
                                <th>Weight</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(flow.stagedData.length > 0 ? flow.stagedData : (data || [])).map(strat => (
                                <tr key={strat.id} style={{ opacity: strat.enabled ? 1 : 0.6 }}>
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                            {strat.risk_label === 'SHIELD' ? '🛡️' : strat.risk_label === 'ROCKET' ? '🚀' : '⚖️'}
                                            <div style={{ fontWeight: 500 }}>{strat.name}</div>
                                        </div>
                                        <div className="flex-row gap-2 mt-1">
                                            <span className="tiny muted">{strat.horizon}</span>
                                            <span className={`tiny badge ${strat.risk_label === 'SHIELD' ? 'success' : 'warn'}`}>{strat.risk_label} RISK</span>
                                        </div>
                                    </td>
                                    <td>
                                        <select
                                            className="input small"
                                            value={strat.mode_override || 'AI'}
                                            disabled={!strat.enabled}
                                            onChange={() => { }}
                                        >
                                            <option value="AI">AI</option>
                                            <option value="MANUAL">MANUAL</option>
                                            <option value="HYBRID">HYBRID</option>
                                        </select>
                                    </td>
                                    <td>
                                        <div className={`tiny ${strat.performance_pct && strat.performance_pct > 0 ? 'ok' : 'warn'}`}>
                                            {strat.performance_pct ? `+${strat.performance_pct}%` : '0.0%'}
                                        </div>
                                        <div className="tiny muted">Conf: {(strat.confidence || 0) * 100}%</div>
                                    </td>
                                    <td>
                                        <label className="switch">
                                            <input
                                                type="checkbox"
                                                checked={strat.enabled}
                                                onChange={() => toggleStrategy(strat.id)}
                                            />
                                            <span className="slider round"></span>
                                        </label>
                                    </td>
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <input
                                                type="range"
                                                className="slider-institutional"
                                                min="0"
                                                max="1"
                                                step="0.05"
                                                value={strat.weight}
                                                disabled={!strat.enabled}
                                                onChange={(e) => updateWeight(strat.id, parseFloat(e.target.value))}
                                                style={{ width: '80px' }}
                                            />
                                            <span className="small">{(strat.weight * 100).toFixed(0)}%</span>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
            <div className="alert info small" style={{ marginTop: '8px' }}>
                Total Weight: {(flow.stagedData.reduce((acc, curr) => acc + (curr.enabled ? curr.weight : 0), 0) * 100).toFixed(0)}%
            </div>
        </div >
    );
};
