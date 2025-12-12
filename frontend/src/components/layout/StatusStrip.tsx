import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHealth, getOpsState, getStatus, getTenants } from '../../api/endpoints';
import { apiBaseUrl } from '../../api/client';
import { DataStatus } from '../common/DataStatus';
import { useBranding } from '../../hooks/useBranding';
import type { TenantRecord } from '../../api/types';

export const StatusStrip: React.FC = () => {
  const auth = useAuth();
  const { branding, loading: brandingLoading, error: brandingError, lastUpdated: brandingUpdatedAt } = useBranding();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken,
    tenantId: auth.tenantId
  };
  const [tenantOptions, setTenantOptions] = useState<TenantRecord[]>([]);

  useEffect(() => {
    const controller = new AbortController();
    if (auth.role === 'ADMIN' && auth.bearerToken) {
      getTenants(controller.signal, client)
        .then((resp) => setTenantOptions(resp.items))
        .catch(() => setTenantOptions([]));
    }
    return () => controller.abort();
  }, [auth.role, auth.bearerToken, auth.tenantId]);

  const status = usePolledResource((signal) => getStatus(signal, client), 4000, [auth.role, auth.tenantId]);
  const health = usePolledResource((signal) => getHealth(signal, client), 6000, [auth.role, auth.tenantId]);
  const ops = usePolledResource((signal) => getOpsState(signal, client), 8000, [auth.role, auth.tenantId]);

  const stale = ops.lastUpdated ? Date.now() - ops.lastUpdated > 12000 : false;

  return (
    <div className="topbar">
      <div className="flex-row" style={{ gap: 12 }}>
        <span><strong>Mode:</strong> {ops.data?.auto_mode ? 'AUTO' : 'MANUAL'}</span>
        <span><strong>Global stop:</strong> {String(ops.data?.global_stop ?? false)}</span>
        <span><strong>Health:</strong> {health.data?.status ?? 'unknown'}</span>
        <span><strong>Uptime:</strong> {status.data ? `${(status.data.uptime / 60).toFixed(1)} min` : 'n/a'}</span>
        <span><strong>Brand:</strong> {branding.brand_name}</span>
        <span className="small"><strong>Tenant:</strong> {auth.tenantId || branding.tenant_id || 'default'}</span>
        {stale && <span className="status-chip warn">data stale</span>}
      </div>
      <div className="flex-row" style={{ gap: 12, alignItems: 'center' }}>
        <DataStatus loading={status.loading} error={status.error} lastUpdated={status.lastUpdated} staleAfterMs={12000} label="status" />
        <DataStatus loading={brandingLoading} error={brandingError} lastUpdated={brandingUpdatedAt} staleAfterMs={60000} label="brand" />
        <span className="small">API base: {apiBaseUrl()}</span>
        <span className="small">Role: {auth.role}</span>
        {auth.role === 'ADMIN' && tenantOptions.length > 0 && (
          <label className="small" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Tenant:
            <select
              value={auth.tenantId || ''}
              onChange={(e) => auth.setTenantId(e.target.value || null)}
              style={{ padding: '2px 6px' }}
            >
              <option value="">default</option>
              {tenantOptions.map((t) => (
                <option key={t.id} value={t.slug}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
    </div>
  );
};
