import React from 'react';
import { useAuth } from '../../../hooks/useAuth';
import { usePolledResource } from '../../../hooks/usePolledResource';
import { getAdminOverview } from '../../../api/endpoints';
import type { AdminOverview } from '../../../api/types';
import { DataStatus } from '../../common/DataStatus';

export const AdminOverviewWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };
    const { data, error, loading, lastUpdated } = usePolledResource<AdminOverview>((signal) => getAdminOverview(signal, client), 10000, [auth]);

    return (
        <div className="card">
            <div className="card-header">
                <h3>System Status</h3>
                <DataStatus loading={loading} error={error} lastUpdated={lastUpdated} staleAfterMs={20000} />
            </div>

            <div className="grid cols-4" style={{ gap: '12px', marginTop: '12px' }}>
                <div className="card subtle center">
                    <div className="tiny muted">Tenants</div>
                    <div className="xlarge">{data?.total_tenants}</div>
                </div>
                <div className="card subtle center">
                    <div className="tiny muted">Users</div>
                    <div className="xlarge">{data?.total_users}</div>
                </div>
                <div className="card subtle center">
                    <div className="tiny muted">Sessions</div>
                    <div className="xlarge ok">{data?.active_sessions}</div>
                </div>
                <div className="card subtle center">
                    <div className="tiny muted">API Health</div>
                    <div className={`xlarge ${data?.system_health?.api === 'healthy' ? 'ok' : 'error'}`}>
                        {data?.system_health?.api === 'healthy' ? 'OK' : 'ERR'}
                    </div>
                </div>
            </div>

            {data?.alerts && data.alerts.length > 0 && (
                <div style={{ marginTop: '16px' }}>
                    <h4 className="small muted transform-upper">Infrastructure Alerts</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                        {data.alerts.map((alert, i) => (
                            <div key={i} className={`alert tiny ${alert.level === 'Error' ? 'error' : 'warn'}`}>
                                <strong>{alert.level}</strong>: {alert.message}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
