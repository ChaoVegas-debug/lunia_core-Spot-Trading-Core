import React, { useEffect, useState } from 'react';
import {
  createTenant,
  getTenantBranding,
  getTenants,
  updateTenant,
  updateTenantBranding,
  updateTenantLimits
} from '../../api/endpoints';
import type { TenantBrandingPayload, TenantLimitsRequest, TenantRecord } from '../../api/types';
import { usePolling } from '../../hooks/usePolling';
import { useAuth } from '../../hooks/useAuth';
import { DataStatus } from '../common/DataStatus';

interface FormState extends Partial<TenantRecord> {}

export const TenantsWidget: React.FC = () => {
  const auth = useAuth();
  const [items, setItems] = useState<TenantRecord[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>({ slug: '', name: '' });
  const [branding, setBranding] = useState<TenantBrandingPayload>({});
  const [limits, setLimits] = useState<TenantLimitsRequest>({ limits: [] });
  const [status, setStatus] = useState<string>('idle');
  const [error, setError] = useState<string>('');

  const client = auth.bearerToken
    ? { bearerToken: auth.bearerToken, role: auth.role, tenantId: auth.tenantId }
    : { tenantId: auth.tenantId };

  const refresh = async (signal: AbortSignal) => {
    setStatus('loading');
    setError('');
    try {
      const resp = await getTenants(signal, client);
      setItems(resp.items);
      if (resp.items.length && selectedId === null) {
        setSelectedId(resp.items[0].id);
      }
      setStatus('ready');
    } catch (e: any) {
      setError(e?.message || 'Failed to load tenants');
      setStatus('error');
    }
  };

  usePolling(refresh, 15000);

  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal);
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    if (selectedId) {
      getTenantBranding(selectedId, controller.signal, client)
        .then(setBranding)
        .catch(() => setBranding({}));
    }
    return () => controller.abort();
  }, [selectedId, token]);

  const handleCreate = async () => {
    if (!form.slug || !form.name) {
      setError('Slug and name required');
      return;
    }
    setStatus('saving');
    try {
      await createTenant({ ...form, domains: form.domains || [] }, new AbortController().signal, client);
      setForm({ slug: '', name: '' });
      await refresh(new AbortController().signal);
      setStatus('ready');
    } catch (e: any) {
      setError(e?.message || 'Create failed');
      setStatus('error');
    }
  };

  const handleUpdate = async () => {
    if (!selectedId) return;
    setStatus('saving');
    try {
      await updateTenant(selectedId, form, new AbortController().signal, client);
      await refresh(new AbortController().signal);
      setStatus('ready');
    } catch (e: any) {
      setError(e?.message || 'Update failed');
      setStatus('error');
    }
  };

  const handleBrandingSave = async () => {
    if (!selectedId) return;
    setStatus('saving');
    try {
      await updateTenantBranding(selectedId, branding, new AbortController().signal, client);
      await refresh(new AbortController().signal);
      setStatus('ready');
    } catch (e: any) {
      setError(e?.message || 'Branding update failed');
      setStatus('error');
    }
  };

  const handleLimitsSave = async () => {
    if (!selectedId) return;
    setStatus('saving');
    try {
      await updateTenantLimits(selectedId, limits, new AbortController().signal, client);
      setStatus('ready');
    } catch (e: any) {
      setError(e?.message || 'Limits update failed');
      setStatus('error');
    }
  };

  const selected = items.find((t) => t.id === selectedId) || null;

  return (
    <div className="card">
      <div className="card-header d-flex justify-content-between align-items-center">
        <div>
          <h3>Tenants</h3>
          <p className="muted">Manage tenants, branding, domains, and baseline limits.</p>
        </div>
        <DataStatus status={status} error={error} />
      </div>
      <div className="card-body">
        <div className="grid two-cols gap">
          <div>
            <h4>Existing Tenants</h4>
            <ul className="list">
              {items.map((tenant) => (
                <li key={tenant.id} className={selectedId === tenant.id ? 'active' : ''}>
                  <button
                    className="link"
                    onClick={() => {
                      setSelectedId(tenant.id);
                      auth.setTenantId(tenant.slug);
                    }}
                  >
                    {tenant.name} ({tenant.slug})
                  </button>
                  <div className="small muted">Status: {tenant.status}</div>
                  <div className="small muted">Domains: {tenant.domains?.join(', ') || '—'}</div>
                </li>
              ))}
            </ul>
            <div className="mt-2">
              <h4>Create Tenant</h4>
              <div className="form-group">
                <label>Slug</label>
                <input value={form.slug || ''} onChange={(e) => setForm({ ...form, slug: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Name</label>
                <input value={form.name || ''} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="form-group">
                <label>Domains (comma separated)</label>
                <input
                  value={(form.domains as unknown as string) || ''}
                  onChange={(e) => setForm({ ...form, domains: e.target.value.split(',').map((d) => d.trim()).filter(Boolean) })}
                />
              </div>
              <button onClick={handleCreate}>Create</button>
            </div>
          </div>
          <div>
            {selected ? (
              <div className="stack">
                <div>
                  <h4>Edit Tenant</h4>
                  <div className="form-group">
                    <label>Name</label>
                    <input value={form.name || selected.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Status</label>
                    <input value={form.status || selected.status} onChange={(e) => setForm({ ...form, status: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Domains</label>
                    <input
                      value={(form.domains as unknown as string) || selected.domains?.join(', ')}
                      onChange={(e) => setForm({ ...form, domains: e.target.value.split(',').map((d) => d.trim()).filter(Boolean) })}
                    />
                  </div>
                  <button onClick={handleUpdate}>Save Tenant</button>
                </div>
                <div>
                  <h4>Branding</h4>
                  <div className="form-group">
                    <label>App Name</label>
                    <input value={branding.app_name || ''} onChange={(e) => setBranding({ ...branding, app_name: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Logo URL</label>
                    <input value={branding.logo_url || ''} onChange={(e) => setBranding({ ...branding, logo_url: e.target.value })} />
                  </div>
                  <div className="form-group">
                    <label>Primary Color</label>
                    <input
                      value={branding.primary_color || ''}
                      onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Support Email</label>
                    <input
                      value={branding.support_email || ''}
                      onChange={(e) => setBranding({ ...branding, support_email: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label>Environment</label>
                    <input
                      value={branding.environment || ''}
                      onChange={(e) => setBranding({ ...branding, environment: e.target.value })}
                    />
                  </div>
                  <button onClick={handleBrandingSave}>Save Branding</button>
                </div>
                <div>
                  <h4>Tenant Limits</h4>
                  <div className="form-group">
                    <label>Limits (key=value per line)</label>
                    <textarea
                      value={limits.limits.map((l) => `${l.key}=${l.value}`).join('\n')}
                      onChange={(e) =>
                        setLimits({
                          limits: e.target.value
                            .split('\n')
                            .map((line) => line.trim())
                            .filter(Boolean)
                            .map((line) => {
                              const [key, ...rest] = line.split('=');
                              return { key: key.trim(), value: rest.join('=') };
                            })
                        })
                      }
                    />
                  </div>
                  <button onClick={handleLimitsSave}>Save Limits</button>
                </div>
              </div>
            ) : (
              <p className="muted">Select or create a tenant to edit details.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
