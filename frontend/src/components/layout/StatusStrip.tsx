import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getHealth, getOpsState, getStatus, getBalances } from '../../api/adapter';
import { apiBaseUrl } from '../../api/client';
import { DataStatus } from '../common/DataStatus';
import { useDashboard } from '../../context/DashboardContext';
import { previewStore } from '../../preview/PreviewStore';

export const StatusStrip: React.FC = () => {
  const auth = useAuth();
  const { toggleDiagnostics, showDiagnostics, addToast } = useDashboard();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };

  const [useRealData, setUseRealData] = React.useState(previewStore.getState().use_real_data);
  React.useEffect(() => {
    const unsub = previewStore.subscribe(() => {
      setUseRealData(previewStore.getState().use_real_data);
    });
    return () => { unsub(); };
  }, []);

  const { data: statusData, error: statusError, refresh: statusRefresh } = usePoller({
        key: 'status_StatusStrip',
        endpoint: '/api/status',
        fetcher: () => getStatus(new AbortController().signal, client),
        interval_ms: 4000,
        critical: true
    });
    const status = { data: statusData, error: statusError, loading: false, refresh: statusRefresh };
  const { data: healthData, error: healthError, refresh: healthRefresh } = usePoller({
        key: 'health_StatusStrip',
        endpoint: '/api/health',
        fetcher: () => getHealth(new AbortController().signal, client),
        interval_ms: 6000,
        critical: true
    });
    const health = { data: healthData, error: healthError, loading: false, refresh: healthRefresh };
  const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller({
        key: 'ops_StatusStrip',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 8000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

  // Poll balances less frequently (30s) to not spam limits, just for "Connected" check
  const { data: balancesData, error: balancesError, refresh: balancesRefresh } = usePoller({
        key: 'balances_StatusStrip',
        endpoint: '/api/balances',
        fetcher: () => getBalances(new AbortController().signal, client),
        interval_ms: 30000,
        critical: true
    });
    const balances = { data: balancesData, error: balancesError, loading: false, refresh: balancesRefresh };

  const stale = ops.lastUpdated ? Date.now() - ops.lastUpdated > 12000 : false;
  const isHealthy = health.data?.status === 'ok';

  // Compute Asset Count
  const assetCount = balances.data?.balances?.filter((b: any) => parseFloat(b.free) > 0 || parseFloat(b.locked) > 0).length || 0;
  // usePolledResource returns { data, error, lastUpdated }. Not status string.
  const exchangeConnected = !!balances.data?.balances && !balances.error;

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

        {/* Exchange Status */}
        {exchangeConnected && (
          <>
            <div className="separator" style={{ width: 1, height: 16, background: '#333' }}></div>
            <div className="flex-row gap-1" title="Binance Spot Connection">
              <span className="tiny font-bold uppercase text-primary">BINANCE {useRealData ? 'REAL BALANCE' : 'SIMULATED'}</span>
              <span className="tiny muted">({assetCount} Assets)</span>
              <span className="status-chip warn tiny" style={{ fontSize: '0.65rem', padding: '1px 4px' }}>DRY RUN</span>
            </div>
          </>
        )}

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
