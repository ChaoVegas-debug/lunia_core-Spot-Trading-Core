import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getAudit } from '../../api/endpoints';
import type { AuditEvent } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const AuditWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken,
    tenantId: auth.tenantId
  };
  const [filters, setFilters] = useState<{ actor?: string; action?: string; result?: string }>({});
  const audit = usePolledResource<{ items: AuditEvent[] }>(
    (signal) => getAudit(signal, client, { limit: 100, ...filters }),
    12000,
    [auth.role, auth.tenantId, filters]
  );

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Audit Trail</h3>
          <p className="small">Latest control and admin actions.</p>
        </div>
        <DataStatus loading={audit.loading} error={audit.error} lastUpdated={audit.lastUpdated} staleAfterMs={15000} />
      </div>
      <div className="grid cols-3" style={{ gap: 8 }}>
        <input value={filters.actor ?? ''} onChange={(e) => setFilters((prev) => ({ ...prev, actor: e.target.value }))} placeholder="actor role" />
        <input value={filters.action ?? ''} onChange={(e) => setFilters((prev) => ({ ...prev, action: e.target.value }))} placeholder="action" />
        <select value={filters.result ?? ''} onChange={(e) => setFilters((prev) => ({ ...prev, result: e.target.value || undefined }))}>
          <option value="">all</option>
          <option value="OK">OK</option>
          <option value="FAIL">FAIL</option>
        </select>
      </div>
      {audit.data ? (
        <table className="table" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Time</th>
              <th>Actor</th>
              <th>Action</th>
              <th>Target</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {audit.data.items.map((ev) => (
              <tr key={ev.id}>
                <td className="small">{ev.ts}</td>
                <td>{ev.actor_role ?? 'n/a'}</td>
                <td>{ev.action}</td>
                <td>{ev.target ?? ''}</td>
                <td>{ev.result}</td>
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
