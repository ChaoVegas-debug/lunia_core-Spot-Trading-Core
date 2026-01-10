import React, { useState } from 'react';
import { useAuth } from '../../../hooks/useAuth';
import { usePolledResource } from '../../../hooks/usePolledResource';
import { getAdminAudit } from '../../../api/endpoints';
import type { AuditEvent } from '../../../api/types';
import { DataStatus } from '../../common/DataStatus';

export const AuditLogViewer: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };
    const [filterAction, setFilterAction] = useState<string>('');

    // We pass the filter as dependency to re-fetch when changed
    const { data, error, loading, lastUpdated } = usePolledResource<AuditEvent[]>((signal) => getAdminAudit(filterAction || undefined, signal, client), 10000, [auth, filterAction]);

    return (
        <div className="card" style={{ height: '100%' }}>
            <div className="card-header">
                <h3>Governance Audit Logs</h3>
                <div className="flex-row" style={{ gap: '12px' }}>
                    <input
                        type="text"
                        placeholder="Filter Action..."
                        className="input small"
                        value={filterAction}
                        onChange={(e) => setFilterAction(e.target.value)}
                        style={{ width: '140px' }}
                    />
                    <DataStatus loading={loading} error={error} lastUpdated={lastUpdated} />
                </div>
            </div>

            <div className="table-container" style={{ maxHeight: '600px', overflowY: 'auto' }}>
                <table className="table compact" style={{ fontSize: '12px' }}>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Actor</th>
                            <th>Action</th>
                            <th>Target</th>
                            <th className="right">Result</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(data || []).map(e => (
                            <tr key={e.id}>
                                <td className="muted" style={{ whiteSpace: 'nowrap' }}>{new Date(e.ts).toLocaleString()}</td>
                                <td>
                                    <span className="tiny info-text">{e.actor_role}</span>{' '}
                                    <span className="muted">#{e.actor_user_id}</span>
                                </td>
                                <td style={{ fontWeight: 500 }}>{e.action}</td>
                                <td className="muted">{e.target || '-'}</td>
                                <td className="right">
                                    <span className={`tiny tag ${e.result === 'OK' ? 'ok' : 'error'}`}>{e.result}</span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
