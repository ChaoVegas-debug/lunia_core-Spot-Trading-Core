import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHealth, getOpsState, getStatus } from '../../api/endpoints';
import { apiBaseUrl } from '../../api/client';
import { DataStatus } from '../common/DataStatus';

export const StatusStrip: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };
  const status = usePolledResource((signal) => getStatus(signal, client), 4000, [auth.role]);
  const health = usePolledResource((signal) => getHealth(signal, client), 6000, [auth.role]);
  const ops = usePolledResource((signal) => getOpsState(signal, client), 8000, [auth.role]);

  const stale = ops.lastUpdated ? Date.now() - ops.lastUpdated > 12000 : false;

  return (
    <div className="topbar">
      <div className="flex-row" style={{ gap: 12 }}>
        <span><strong>Mode:</strong> {ops.data?.auto_mode ? 'AUTO' : 'MANUAL'}</span>
        <span><strong>Global stop:</strong> {String(ops.data?.global_stop ?? false)}</span>
        <span><strong>Health:</strong> {health.data?.status ?? 'unknown'}</span>
        <span><strong>Uptime:</strong> {status.data ? `${(status.data.uptime / 60).toFixed(1)} min` : 'n/a'}</span>
        {stale && <span className="status-chip warn">data stale</span>}
      </div>
      <div className="flex-row" style={{ gap: 12, alignItems: 'center' }}>
        <DataStatus loading={status.loading} error={status.error} lastUpdated={status.lastUpdated} staleAfterMs={12000} label="status" />
        <span className="small">API base: {apiBaseUrl()}</span>
        <span className="small">Role: {auth.role}</span>
      </div>
    </div>
  );
};
