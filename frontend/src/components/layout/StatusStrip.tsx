import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHealth, getOpsState, getStatus } from '../../api/adapter';
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
        <button
          className="button small"
          style={{
            border: '1px solid var(--accent-primary)',
            color: 'var(--accent-primary)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)'
          }}
          onClick={async () => {
            if (window.confirm("Enter Preview Mode? This will RESET data and seed a demo state.")) {
              try {
                const { postSeedDemo } = await import('../../api/endpoints');
                // No signal needed for fire-and-forget/reload
                await postSeedDemo(new AbortController().signal, client);
                window.location.reload();
              } catch (e) {
                alert("Failed to enter Preview Mode");
              }
            }
          }}
        >
          ⚡ Preview Mode
        </button>
        <DataStatus loading={status.loading} error={status.error} lastUpdated={status.lastUpdated} staleAfterMs={12000} label="status" />
        <span className="small">API base: {apiBaseUrl()}</span>
        <span className="small">Role: {auth.role}</span>
      </div>
    </div>
  );
};
