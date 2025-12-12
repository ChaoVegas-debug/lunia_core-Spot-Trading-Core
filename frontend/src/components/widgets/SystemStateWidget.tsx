import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHealth, getOpsState, getStatus } from '../../api/endpoints';
import type { OpsState, StatusSnapshot } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const SystemStateWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };
  const ops = usePolledResource<OpsState>((signal) => getOpsState(signal, client), 2500, [auth.role]);
  const status = usePolledResource<StatusSnapshot>((signal) => getStatus(signal, client), 4000, [auth.role]);
  const health = usePolledResource((signal) => getHealth(signal, client), 7000, [auth.role]);

  const stale = ops.lastUpdated ? Date.now() - ops.lastUpdated > 8000 : false;

  if (ops.loading && !ops.data) return <div className="card">Loading system state...</div>;
  if (ops.error) {
    return <div className="card alert">Failed to load system state: {ops.error.message}</div>;
  }

  const data = ops.data;
  if (!data) {
    return <div className="card alert">No system state available.</div>;
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>System State</h3>
          <p className="small">Runtime flags, health, and mode; polling every 2.5s.</p>
        </div>
        <DataStatus loading={ops.loading} error={ops.error} lastUpdated={ops.lastUpdated} staleAfterMs={8000} />
      </div>
      <div className="grid cols-2">
        <div className="card subtle">
          <div className="flex-row" style={{ justifyContent: 'space-between' }}>
            <strong>Mode</strong>
            <span className={`status-chip ${data.auto_mode ? 'ok' : 'warn'}`}>{data.auto_mode ? 'AUTO' : 'MANUAL'}</span>
          </div>
          <div className="small">Global stop: {String(data.global_stop)}</div>
          <div className="small">Exec mode: {data.exec_mode || 'unknown'}</div>
          <div className="small">Manual override: {String(data.manual_override)}</div>
          {stale && <div className="alert warn">Data stale &gt;8s. Controls disabled until refreshed.</div>}
        </div>
        <div className="card subtle">
          <div className="flex-row" style={{ justifyContent: 'space-between' }}>
            <strong>Health</strong>
            <DataStatus loading={health.loading} error={health.error} lastUpdated={health.lastUpdated} staleAfterMs={12000} />
          </div>
          <div className="small">API status: {health.data?.status ?? 'unknown'}</div>
          <div className="small">Uptime: {status.data ? `${(status.data.uptime / 60).toFixed(1)} min` : 'n/a'}</div>
          <div className="small">Version: {status.data?.version ?? 'n/a'}</div>
        </div>
      </div>
      <div className="grid cols-3" style={{ marginTop: 12 }}>
        <div className="card subtle">
          <div className="flex-row" style={{ justifyContent: 'space-between' }}>
            <span>Trading</span>
            <span className={`status-chip ${data.trading_on ? 'ok' : 'error'}`}>{String(data.trading_on)}</span>
          </div>
          <div className="small">Agent: {String(data.agent_on ?? true)}</div>
        </div>
        <div className="card subtle">
          <div className="flex-row" style={{ justifyContent: 'space-between' }}>
            <span>Spot</span>
            <span className={`status-chip ${data.spot?.enabled !== false ? 'ok' : 'error'}`}>
              {data.spot?.enabled !== false ? 'on' : 'off'}
            </span>
          </div>
          <div className="small">Weights: {Object.keys(data.spot?.weights ?? {}).length}</div>
        </div>
        <div className="card subtle">
          <div className="flex-row" style={{ justifyContent: 'space-between' }}>
            <span>Arbitrage</span>
            <span className={`status-chip ${data.arb_on ? 'ok' : 'warn'}`}>{String(data.arb_on)}</span>
          </div>
          <div className="small">Auto: {String(data.arb?.auto_mode ?? false)}</div>
        </div>
      </div>
    </div>
  );
};
