import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { usePolledResource } from '../hooks/usePolledResource';
import { getHealth, getStatus } from '../api/endpoints';
import type { HealthResponse, StatusSnapshot } from '../api/types';

export const SystemPage: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken,
    tenantId: auth.tenantId
  };
  const health = usePolledResource<HealthResponse>((signal) => getHealth(signal, client), 4000, [auth.role, auth.tenantId]);
  const status = usePolledResource<StatusSnapshot>((signal) => getStatus(signal, client), 4000, [auth.role, auth.tenantId]);

  return (
    <div>
      <h2>System Diagnostics</h2>
      <div className="card-grid">
        <div className="card">
          <h3>Health</h3>
          {health.error && <div className="alert">Health error: {health.error.message}</div>}
          {health.data && <div className="small">status: {health.data.status}</div>}
          {!health.data && !health.error && <div>Loading health...</div>}
        </div>
        <div className="card">
          <h3>Status</h3>
          {status.error && <div className="alert">Status error: {status.error.message}</div>}
          {status.data && (
            <>
              <div className="small">version: {status.data.version}</div>
              <div className="small">uptime: {(status.data.uptime / 60).toFixed(1)} min</div>
              <div className="small">active cores: {Object.keys(status.data.active_cores || {}).length}</div>
            </>
          )}
          {!status.data && !status.error && <div>Loading status...</div>}
        </div>
      </div>
    </div>
  );
};
