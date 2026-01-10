import React from 'react';
import { usePolledResource } from '../../../hooks/usePolledResource';
import { getExchanges } from '../../../api/endpoints';
import { useAuth } from '../../../hooks/useAuth';
import type { ExchangeConfig } from '../../../api/types';

export const ExchangeHealthWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken };
    const { data: exchanges, loading } = usePolledResource<ExchangeConfig[]>((s) => getExchanges(s, client), 3000, [auth.role]);

    if (loading && !exchanges) return <div className="card">Loading Exchange Health...</div>;

    return (
        <div className="card">
            <div className="card-header">
                <h3>Exchange Health Monitor</h3>
            </div>

            <table className="table">
                <thead>
                    <tr>
                        <th>Venue</th>
                        <th>Status</th>
                        <th>Ping</th>
                        <th>Allocation</th>
                        <th>Risk Label</th>
                    </tr>
                </thead>
                <tbody>
                    {(exchanges || []).map(ex => (
                        <tr key={ex.id}>
                            <td className="font-mono">{ex.name.toUpperCase()}</td>
                            <td>
                                <span className={`badge ${ex.connected ? 'success' : 'danger'}`}>
                                    {ex.connected ? 'ONLINE' : 'OFFLINE'}
                                </span>
                            </td>
                            <td className="font-mono text-green">~45ms</td> {/* Mock Ping for visual */}
                            <td className="font-mono">{(ex.allocation * 100).toFixed(1)}%</td>
                            <td>
                                <span className="badge secondary tiny">{ex.risk_label || 'STANDARD'}</span>
                            </td>
                        </tr>
                    ))}
                    {(!exchanges || exchanges.length === 0) && (
                        <tr>
                            <td colSpan={5} className="muted text-center" style={{ padding: '24px' }}>
                                No exchanges configured.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};
