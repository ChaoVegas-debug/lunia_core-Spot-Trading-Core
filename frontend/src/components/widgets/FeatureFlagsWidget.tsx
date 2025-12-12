import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getFlags, updateFlag } from '../../api/endpoints';
import type { FeatureFlag } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const FeatureFlagsWidget: React.FC = () => {
  const auth = useAuth();
  const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };
  const [refreshKey, setRefreshKey] = useState(0);
  const flags = usePolledResource<{ items: FeatureFlag[] }>((signal) => getFlags(signal, client), 12000, [auth.role, refreshKey]);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const save = async (key: string) => {
    setError(null);
    try {
      const controller = new AbortController();
      await updateFlag(key, { value: editing[key] ?? '' }, controller.signal, client);
      setRefreshKey((v) => v + 1);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Feature Flags</h3>
          <p className="small">Runtime toggles; DB overrides env defaults.</p>
        </div>
        <DataStatus loading={flags.loading} error={flags.error} lastUpdated={flags.lastUpdated} staleAfterMs={15000} />
      </div>
      {error && <div className="alert">{error}</div>}
      {flags.data ? (
        <table className="table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Value</th>
              <th>Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {flags.data.items.map((flag) => (
              <tr key={flag.key}>
                <td>{flag.key}</td>
                <td>
                  <input
                    value={editing[flag.key] ?? String(flag.value)}
                    onChange={(e) => setEditing((prev) => ({ ...prev, [flag.key]: e.target.value }))}
                  />
                </td>
                <td className="small">{flag.updated_at}</td>
                <td>
                  <button className="button ghost" type="button" onClick={() => save(flag.key)}>
                    Save
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div>Loading feature flags...</div>
      )}
    </div>
  );
};
