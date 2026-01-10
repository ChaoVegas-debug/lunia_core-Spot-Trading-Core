import React from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getExchangeAllocations } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';
import { ExchangeAllocationRow } from '../../api/types';

export const ExchangeAllocationWidget: React.FC = () => {
    const auth = useAuth();
    const { data } = usePolledResource(getExchangeAllocations, 5000, [auth]);

    const toggleExchange = async (id: string, enabled: boolean) => {
        await import('../../api/adapter').then(m => m.updateExchangeEnabled(id, enabled));
        // refresh handled by polling or optimistic update could be added
    };

    const updateRisk = async (id: string, val: number) => {
        await import('../../api/adapter').then(m => m.updateExchangeRiskLimit(id, val));
    };

    return (
        <div className="card">
            <div className="card-header">
                <h3>Exchange Risk & Capital</h3>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                {data?.map((exch: ExchangeAllocationRow) => (
                    <div key={exch.id} style={{
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid rgba(255,255,255,0.05)',
                        padding: '12px',
                        borderRadius: '4px'
                    }}>
                        <div className="flex-between mb-2">
                            <div style={{ fontWeight: 'bold' }}>{exch.name}</div>
                            <span className={`tiny badge ${exch.connected ? 'success' : 'danger'}`}>
                                {exch.connected ? 'CONN' : 'ERR'}
                            </span>
                        </div>

                        <div className="flex-between tiny muted mb-1">
                            <span>Balance</span>
                            <span className="font-mono text-white">${exch.total_balance_usd.toLocaleString()}</span>
                        </div>

                        <div className="flex-between tiny muted mb-1">
                            <span>Risk Limit</span>
                            <span className="font-mono text-warning">{(exch.risk_limit_pct * 100).toFixed(0)}%</span>
                        </div>
                        <input
                            type="range"
                            min="0" max="100"
                            value={exch.risk_limit_pct * 100}
                            className="slider-institutional"
                            style={{ width: '100%', marginBottom: '8px' }}
                            onChange={(e) => updateRisk(exch.id, parseInt(e.target.value) / 100)}
                        />

                        <div style={{ marginTop: '8px' }}>
                            <div className="tiny muted mb-1">Usage {(exch.usage_pct * 100).toFixed(0)}%</div>
                            <div style={{ height: '4px', background: '#222', borderRadius: '2px', overflow: 'hidden' }}>
                                <div style={{
                                    width: `${(exch.usage_pct / exch.risk_limit_pct) * 100}%`,
                                    height: '100%',
                                    background: exch.usage_pct > exch.risk_limit_pct ? 'var(--accent-danger)' : 'var(--accent-primary)'
                                }} />
                            </div>
                        </div>

                        <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'flex-end' }}>
                            <label className="switch tiny-switch">
                                <input
                                    type="checkbox"
                                    checked={exch.enabled}
                                    onChange={(e) => toggleExchange(exch.id, e.target.checked)}
                                />
                                <span className="slider"></span>
                            </label>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
