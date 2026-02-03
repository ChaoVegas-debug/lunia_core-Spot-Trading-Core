import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getLogs } from '../../api/adapter';
import type { LogsResponse } from '../../api/types';
import { DataStatus } from '../common/DataStatus';
import { UiAuditEntry, addAuditEntry, subscribeAudit } from '../../utils/auditLog';
import { WidgetWrapper } from '../common/WidgetWrapper';

export const LogsWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };

  const { data: logsData, error: logsError, refresh: logsRefresh } = usePoller<LogsResponse>({
        key: 'logs_LogsWidget',
        endpoint: '/api/logs',
        fetcher: () => getLogs(new AbortController().signal, client),
        interval_ms: 20000,
        critical: false
    });
    const logs = { data: logsData, error: logsError, loading: false, refresh: logsRefresh };
  const [audit, setAudit] = useState<UiAuditEntry[]>([]);

  useEffect(() => {
    return subscribeAudit(setAudit);
  }, []);

  useEffect(() => {
    addAuditEntry({ ts: new Date().toISOString(), action: 'UI session started', ok: true });
  }, []);

  return (
    <WidgetWrapper
      id="LogsWidget"
      title="Logs"
      loading={logs.loading}
      error={logs.error}
      rightElem={<DataStatus loading={logs.loading} error={logs.error} lastUpdated={logs.lastUpdated} staleAfterMs={30000} />}
    >
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
    </WidgetWrapper>
  );
};
