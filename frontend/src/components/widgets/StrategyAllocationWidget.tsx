import React from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getStrategyAllocations, updateStrategies } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';
import { StrategyAllocationRow } from '../../api/types';

export const StrategyAllocationWidget: React.FC = () => {
    const auth = useAuth();
    const { data, loading, error, refresh } = usePolledResource(getStrategyAllocations, 3000, [auth]);

    const handleToggle = async (id: string, enabled: boolean) => {
        // Mock update via adapter updateStrategies
        await updateStrategies([{ id, enabled }], new AbortController().signal);
        refresh();
    };

    return (
        <div className="card">
            <div className="card-header flex-between">
                <h3>Strategy Allocation</h3>
                <div className="small muted">Global Risk Budget</div>
            </div>

            <div className="table-container institutional-table">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid #333', color: '#888' }}>
                            <th style={{ textAlign: 'left', padding: '8px' }}>Strategy Core</th>
                            <th style={{ textAlign: 'left' }}>Mode</th>
                            <th style={{ textAlign: 'center' }}>Priority</th>
                            <th style={{ textAlign: 'center' }}>% Alloc</th>
                            <th style={{ textAlign: 'right' }}>Active Cap</th>
                            <th style={{ textAlign: 'right' }}>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data?.map((row: StrategyAllocationRow) => (
                            <tr key={row.id} style={{ borderBottom: '1px solid #222', opacity: row.enabled ? 1 : 0.5 }}>
                                <td style={{ padding: '8px' }}>
                                    <div style={{ fontWeight: 600 }}>{row.name}</div>
                                    <div className="tiny muted">{row.core} • {row.horizon}</div>
                                </td>
                                <td>
                                    <span className="tiny font-mono" style={{
                                        color: row.control_mode === 'AI' ? 'var(--accent-primary)' : '#fff'
                                    }}>{row.control_mode}</span>
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    <span className={`badge tiny ${row.priority === 'HIGH' ? 'danger' : 'secondary'}`}>
                                        {row.priority}
                                    </span>
                                </td>
                                <td style={{ textAlign: 'center', width: '25%' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <input
                                            type="range"
                                            min="0" max="100"
                                            value={row.target_alloc_pct * 100}
                                            className="slider-institutional"
                                            style={{ flex: 1 }}
                                            onChange={async (e) => {
                                                const val = parseInt(e.target.value) / 100;
                                                await import('../../api/adapter').then(m => m.updateStrategyAllocation(row.id, val));
                                                refresh();
                                            }}
                                        />
                                        <span className="tiny font-mono" style={{ minWidth: '32px' }}>
                                            {(row.target_alloc_pct * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                </td>
                                <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                                    ${(row.current_alloc_pct * 1000000).toLocaleString()}
                                </td>
                                <td style={{ textAlign: 'right' }}>
                                    <label className="switch">
                                        <input
                                            type="checkbox"
                                            checked={row.enabled}
                                            onChange={(e) => handleToggle(row.id, e.target.checked)}
                                        />
                                        <span className="slider"></span>
                                    </label>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
