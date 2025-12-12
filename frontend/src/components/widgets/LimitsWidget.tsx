import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getLimits, upsertLimit } from '../../api/endpoints';
import type { LimitEntry } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const LimitsWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken,
    tenantId: auth.tenantId
  };
  const [refreshKey, setRefreshKey] = useState(0);
  const limits = usePolledResource<{ items: LimitEntry[] }>(
    (signal) => getLimits(signal, client),
    12000,
    [auth.role, auth.tenantId, refreshKey]
  );

  const [form, setForm] = useState<{ scope: string; subject?: string; key: string; value: string }>({ scope: 'global', key: '', value: '' });
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const controller = new AbortController();
      await upsertLimit({ scope: form.scope, subject: form.subject, key: form.key, value: form.value }, controller.signal, client);
      setForm({ scope: 'global', key: '', value: '' });
      setRefreshKey((v) => v + 1);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Limits (soft)</h3>
          <p className="small">Advisory limits for UI banners; not enforced on trading core yet.</p>
        </div>
        <DataStatus loading={limits.loading} error={limits.error} lastUpdated={limits.lastUpdated} staleAfterMs={15000} />
      </div>
      {error && <div className="alert">{error}</div>}
      <form className="grid cols-4" onSubmit={submit} style={{ gap: 8 }}>
        <select value={form.scope} onChange={(e) => setForm((prev) => ({ ...prev, scope: e.target.value }))}>
          <option value="global">global</option>
          <option value="role">role</option>
          <option value="user">user</option>
        </select>
        <input value={form.subject ?? ''} onChange={(e) => setForm((prev) => ({ ...prev, subject: e.target.value }))} placeholder="subject (role or user id)" />
        <input value={form.key} onChange={(e) => setForm((prev) => ({ ...prev, key: e.target.value }))} placeholder="limit key" required />
        <input value={form.value} onChange={(e) => setForm((prev) => ({ ...prev, value: e.target.value }))} placeholder="value" required />
        <button className="button" type="submit">
          Upsert
        </button>
      </form>
      {limits.data ? (
        <table className="table" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Scope</th>
              <th>Subject</th>
              <th>Key</th>
              <th>Value</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {limits.data.items.map((lim) => (
              <tr key={`${lim.scope}-${lim.subject}-${lim.key}`}>
                <td>{lim.scope}</td>
                <td>{lim.subject ?? 'n/a'}</td>
                <td>{lim.key}</td>
                <td>{String(lim.value)}</td>
                <td className="small">{lim.updated_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div>Loading limits...</div>
      )}
    </div>
  );
};
