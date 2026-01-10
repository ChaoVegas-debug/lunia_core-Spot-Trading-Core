import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHealth, getOpsState, getStatus } from '../../api/adapter';
import { apiBaseUrl } from '../../api/client';
import { DataStatus } from '../common/DataStatus';
import { useDashboard } from '../../context/DashboardContext';

export const StatusStrip: React.FC = () => {
  const auth = useAuth();
  const { toggleDiagnostics, showDiagnostics, addToast } = useDashboard();
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
  const isHealthy = health.data?.status === 'ok';

  return (
    <div className="topbar">
      <div className="flex-row" style={{ gap: 12, alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: isHealthy ? '#22c55e' : '#ef4444' }} />
          <span className="tiny font-bold uppercase">{isHealthy ? 'SYSTEM ONLINE' : 'DISCONNECTED'}</span>
        </div>
        <div className="separator" style={{ width: 1, height: 16, background: '#333' }}></div>
        <span><strong>Mode:</strong> <span className={ops.data?.auto_mode ? 'text-primary' : 'text-muted'}>{ops.data?.auto_mode ? 'AUTO' : 'MANUAL'}</span></span>
        <span><strong>Stop:</strong> <span className={ops.data?.global_stop ? 'text-danger' : 'text-muted'}>{String(ops.data?.global_stop ?? false)}</span></span>
        <span><strong>Uptime:</strong> {status.data ? `${(status.data.uptime / 60).toFixed(1)}m` : '-'}</span>
        {stale && <span className="status-chip warn">data stale</span>}
      </div>
      <div className="flex-row" style={{ gap: 12, alignItems: 'center' }}>
        <button
          className={`button tiny ${showDiagnostics ? 'active' : 'ghost'}`}
          onClick={toggleDiagnostics}
          title="Toggle API Wiring Inspector"
        >
          🐞 DIAG
        </button>

        <button
          className="button tiny outline"
          onClick={async () => {
            if (window.confirm("Enter Preview Mode? This will RESET data and seed a demo state.")) {
              try {
                const { postSeedDemo } = await import('../../api/endpoints');
                await postSeedDemo(new AbortController().signal, client);
                addToast({ type: 'SUCCESS', message: 'Preview Mode Seeded. Reloading...' });
                setTimeout(() => window.location.reload(), 1000);
              } catch (e) {
                addToast({ type: 'ERROR', message: "Failed to enter Preview Mode" });
              }
            }
          }}
        >
          ⚡ RSIM
        </button>
        <span className="small muted">v{import.meta.env.VITE_APP_BUILD || 'dev'}</span>
      </div>
    </div>
  );
};
