import React, { useState } from 'react';
import { useAuth } from '../../../hooks/useAuth';
import { usePolledResource } from '../../../hooks/usePolledResource';
import { getAdminTenants, updateTenantConfig } from '../../../api/endpoints';
import type { Tenant } from '../../../api/types';
import { DataStatus } from '../../common/DataStatus';

export const TenantManagerWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };
    const { data, error, loading, lastUpdated, refresh } = usePolledResource<Tenant[]>((signal) => getAdminTenants(signal, client), 30000, [auth]);

    const [editId, setEditId] = useState<string | null>(null);

    const handleBrandingUpdate = async (id: string) => {
        try {
            // Mock update for demo, usually would open a modal form
            await updateTenantConfig(id, { branding: { name: "Lunia Enterprise", theme: "light" } }, new AbortController().signal, client);
            refresh();
            setEditId(null);
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="card">
            <div className="card-header">
                <h3>Tenants Management</h3>
                <DataStatus loading={loading} error={error} lastUpdated={lastUpdated} />
            </div>

            <div className="table-container">
                <table className="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Name</th>
                            <th>Plan</th>
                            <th className="center">Status</th>
                            <th className="right">Limits</th>
                            <th className="right">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(data || []).map(t => (
                            <tr key={t.id}>
                                <td className="muted small">{t.id}</td>
                                <td style={{ fontWeight: 500 }}>{t.branding?.name || t.name}</td>
                                <td><span className="tiny tag info">{t.plan}</span></td>
                                <td className="center"><span className="tiny tag ok">{t.status}</span></td>
                                <td className="right small muted">
                                    {t.limits?.max_strategies} strats / {t.limits?.max_exchanges} exch
                                </td>
                                <td className="right">
                                    <button className="btn-text small" onClick={() => handleBrandingUpdate(t.id)}>
                                        Edit Branding
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
