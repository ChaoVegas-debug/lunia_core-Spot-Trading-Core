import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getCapital } from '../../api/adapter';
import type { OpsCapital } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const CapitalWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };

  const { data: capData, error: capError, refresh: capRefresh } = usePoller<OpsCapital>({
        key: 'cap_CapitalWidget',
        endpoint: '/api/unknown',
        fetcher: () => getCapital(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const cap = { data: capData, error: capError, loading: false, refresh: capRefresh };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Operations Capital</h3>
          <p className="small">Working capital for algo execution.</p>
        </div>
        <DataStatus loading={cap.loading} error={cap.error} lastUpdated={cap.lastUpdated} staleAfterMs={10000} />
      </div>

      <div className="kv-list">
        {cap.data && Object.entries(cap.data).map(([k, v]) => (
          <div key={k} className="kv-item">
            <span className="key">{k}:</span>
            <span className="value code">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
