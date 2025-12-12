import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getLogs } from '../../api/endpoints';
import type { LogsResponse } from '../../api/types';
import { DataStatus } from '../common/DataStatus';
import { UiAuditEntry, addAuditEntry, subscribeAudit } from '../../utils/auditLog';

export const LogsWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };

  const logs = usePolledResource<LogsResponse>((signal) => getLogs(signal, client), 20000, [auth.role]);
  const [audit, setAudit] = useState<UiAuditEntry[]>([]);

  useEffect(() => {
    return subscribeAudit(setAudit);
  }, []);

  useEffect(() => {
    // seed with a UI start entry when component mounts
    addAuditEntry({ ts: new Date().toISOString(), action: 'UI session started', ok: true });
  }, []);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Logs</h3>
          <p className="small">Backend API log + local UI audit of control clicks.</p>
        </div>
        <DataStatus loading={logs.loading} error={logs.error} lastUpdated={logs.lastUpdated} staleAfterMs={30000} />
      </div>
      {logs.error && <div className="alert">Backend logs endpoint unavailable ({logs.error.message})</div>}
      <div className="grid cols-2">
        <div className="card subtle">
          <h4>Backend</h4>
          {logs.data && logs.data.items.length > 0 ? (
            <ul className="list">
              {logs.data.items.slice(0, 20).map((item) => (
                <li key={`${item.ts}-${item.message}`} className="list-row">
                  <div className="small">{item.ts} • {item.level}</div>
                  <div className="small muted">{item.message}</div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="small">Backend logs endpoint unavailable or empty.</div>
          )}
        </div>
        <div className="card subtle">
          <h4>UI audit</h4>
          {audit.length > 0 ? (
            <ul className="list">
              {audit.map((item) => (
                <li key={`${item.ts}-${item.action}`} className="list-row">
                  <div className="small">{new Date(item.ts).toLocaleTimeString()}</div>
                  <div>{item.action}</div>
                  {item.details && <div className="small muted">{item.details}</div>}
                  <span className={`status-chip ${item.ok ? 'ok' : 'error'}`}>{item.ok ? 'OK' : 'FAIL'}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="small">No local actions yet.</div>
          )}
        </div>
      </div>
    </div>
  );
};
