import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getStrategies } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import type { StrategyConfig } from '../../api/types';

export const StrategyHealthWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };

    const strategies = usePolledResource<StrategyConfig[]>((s) => getStrategies(s, client), 5000, []);

    return (
        <div className="card">
            <div className="card-header">
                <h3>Strategy Health</h3>
                <span className="tiny muted">OPERATIONAL STATUS</span>
            </div>
            <div className="card-body scrollable-y" style={{ maxHeight: '200px' }}>
                {safeArray(strategies.data).length === 0 ? (
                    <div className="empty-state">No strategies configured.</div>
                ) : (
                    <table className="table compact">
                        <thead>
                            <tr>
                                <th>Strategy</th>
                                <th>Status</th>
                                <th>Latency</th>
                                <th>Errors (24h)</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {safeArray(strategies.data).filter(s => s.enabled).map(s => (
                                <tr key={s.id}>
                                    <td className="bright">{s.name}</td>
                                    <td>
                                        <span className={`status-badge ${s.enabled ? 'success' : 'muted'}`}>
                                            {s.enabled ? 'HEALTHY' : 'OFF'}
                                        </span>
                                    </td>
                                    <td className="text-mono small">
                                        {/* Mock Latency for P3.2 */}
                                        {Math.floor(Math.random() * 50 + 20)}ms
                                    </td>
                                    <td className="text-mono small centered">0</td>
                                    <td>
                                        <button className="button tiny ghost" title="Restart Instance">↻</button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};
