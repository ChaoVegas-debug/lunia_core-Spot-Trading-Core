import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getAudit } from '../../api/adapter';
import type { SystemEvent } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const AuditWidget: React.FC = () => {
  const auth = useAuth();
  const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

  // Migrated to usePoller
  const { data: auditData, error: auditError, refresh: auditRefresh } = usePoller<{ items: SystemEvent[] }>({
    key: 'audit_widget',
    endpoint: '/api/audit',
    fetcher: () => getAudit(new AbortController().signal, client),
    interval_ms: 12000,
    critical: false
  });
  const audit = { data: auditData, error: auditError, loading: false, lastUpdated: undefined, refresh: auditRefresh };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Audit Trail</h3>
          <p className="small">Latest control and admin actions.</p>
        </div>
        <DataStatus loading={audit.loading} error={audit.error} lastUpdated={audit.lastUpdated} staleAfterMs={15000} />
      </div>

      {audit.data && audit.data.items ? (
        <table className="table" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Time</th>
              <th>Type</th>
              <th>Payload</th>
            </tr>
          </thead>
          <tbody>
            {audit.data.items.slice().reverse().map((ev) => (
              <tr key={ev.id}>
                <td className="small">{new Date(ev.timestamp).toLocaleTimeString()}</td>
                <td>{ev.type}</td>
                <td className="code tiny" style={{ maxWidth: '300px', overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                  {JSON.stringify(ev.payload)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div>Loading audit trail...</div>
      )}
    </div>
  );
};
