import React from 'react';
import { useAuth } from '../../../hooks/useAuth';
import { usePolledResource } from '../../../hooks/usePolledResource';
import { getAdminUsers, updateUserRole } from '../../../api/endpoints';
import type { UserProfile } from '../../../api/types';
import { DataStatus } from '../../common/DataStatus';
import { useDashboard } from '../../../context/DashboardContext';

export const UserManagerWidget: React.FC = () => {
    const auth = useAuth();
    const { addToast } = useDashboard();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };
    const { data, error, loading, lastUpdated, refresh } = usePolledResource<UserProfile[]>((signal) => getAdminUsers(signal, client), 15000, [auth]);

    const handleRoleChange = async (userId: number, newRole: string) => {
        if (!window.confirm(`Are you sure you want to promote User #${userId} to ${newRole}? This is an audited action.`)) return;
        try {
            await updateUserRole(userId, newRole, new AbortController().signal, client);
            refresh();
        } catch (e) {
            addToast({ type: 'ERROR', message: "Failed to update role" });
        }
    };

    return (
        <div className="card">
            <div className="card-header">
                <h3>User & Role Management</h3>
                <DataStatus loading={loading} error={error} lastUpdated={lastUpdated} />
            </div>

            <div className="table-container" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                <table className="table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Email</th>
                            <th>Role</th>
                            <th className="center">Last Login</th>
                            <th className="right">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(data || []).map(u => (
                            <tr key={u.id}>
                                <td className="muted small">#{u.id}</td>
                                <td>{u.email}</td>
                                <td>
                                    <span className={`tiny tag ${u.role === 'ADMIN' ? 'error' : u.role === 'FUND' ? 'warn' : 'info'}`}>
                                        {u.role}
                                    </span>
                                </td>
                                <td className="center small muted">{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : '-'}</td>
                                <td className="right">
                                    {u.role !== 'ADMIN' && (
                                        <div className="flex-row" style={{ justifyContent: 'flex-end', gap: '8px' }}>
                                            <button className="btn-text tiny" onClick={() => handleRoleChange(u.id, 'TRADER')}>TRADER</button>
                                            <button className="btn-text tiny" onClick={() => handleRoleChange(u.id, 'FUND')}>FUND</button>
                                            <button className="btn-text tiny warn-text" onClick={() => handleRoleChange(u.id, 'ADMIN')}>ADMIN</button>
                                        </div>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
