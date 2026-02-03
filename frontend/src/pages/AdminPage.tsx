
import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { usePoller } from '../hooks/usePoller';
import { AdminPanel } from './AdminPanel';
import { getAdminStats, getUsers, updateUserRole } from '../api/adapter';
import { AdminOverview, UserProfile, Role } from '../api/types';

import { useDashboard } from '../context/DashboardContext';
import { DiagnosticsPanel } from '../components/admin/DiagnosticsPanel';

export const AdminPage: React.FC = () => {
    const { role } = useAuth();
    const { addToast } = useDashboard();
    const client = { role };

    const { data: statsResData, error: statsResError, refresh: statsResRefresh } = usePoller<AdminOverview>({
        key: 'statsRes_AdminPage',
        endpoint: '/api/admin/stats',
        fetcher: () => getAdminStats(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const statsRes = { data: statsResData, error: statsResError, loading: false, refresh: statsResRefresh };
    const { data: usersResData, error: usersResError, refresh: usersResRefresh } = usePoller<UserProfile[]>({
        key: 'usersRes_AdminPage',
        endpoint: '/api/admin/users',
        fetcher: () => getUsers(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const usersRes = { data: usersResData, error: usersResError, loading: false, refresh: usersResRefresh };
    const [editingUserId, setEditingUserId] = useState<number | null>(null);

    const stats = statsRes.data || {
        total_tenants: 0,
        total_users: 0,
        active_sessions: 0,
        system_aum_usd: 0,
        system_health: { db: '-', redis: '-', engine: '-' },
        alerts: []
    };

    const handleAction = async (userId: number, action: string, newVal: string) => {
        if (!confirm(`Confirm ${action} for User ${userId} ? `)) return;
        try {
            await updateUserRole(userId, action === 'ROLE' ? newVal : 'TRADER', action === 'TIER' ? newVal : 'STD_RETAIL');
            addToast({ type: 'SUCCESS', message: 'User updated successfully' });
            // Force refresh logic would go here or rely on poll
        } catch (e) {
            addToast({ type: 'ERROR', message: 'Update failed' });
        }
    };

    return (
        <div className="page-container" style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>
            <header className="flex-between mb-8">
                <div>
                    <h1 className="text-xl font-bold tracking-tight mb-2">SYSTEM ADMINISTRATION</h1>
                    <p className="text-muted small">Platform Overview & User Governance</p>
                </div>
                <div className="flex gap-4">
                    <div className="text-right">
                        <div className="tiny muted uppercase">System Status</div>
                        <div className="badge success">OPERATIONAL</div>
                    </div>
                </div>
            </header>

            {/* KPI CARDS */}
            <div className="grid grid-cols-4 gap-6 mb-8">
                <div className="card p-4">
                    <div className="tiny muted uppercase mb-2">Total Users</div>
                    <div className="text-2xl font-mono">{stats.total_users}</div>
                    <div className="tiny success mt-1">+2 this week</div>
                </div>
                <div className="card p-4">
                    <div className="tiny muted uppercase mb-2">Active Tenants (Funds)</div>
                    <div className="text-2xl font-mono">{stats.total_tenants}</div>
                    <div className="tiny success mt-1">100% Retention</div>
                </div>
                <div className="card p-4">
                    <div className="tiny muted uppercase mb-2">System AUM</div>
                    <div className="text-2xl font-mono text-primary">${((stats.system_aum_usd || 0) / 1000000).toFixed(1)}M</div>
                    <div className="tiny muted mt-1">Across all pools</div>
                </div>
                <div className="card p-4">
                    <div className="tiny muted uppercase mb-2">Infrastructure Health</div>
                    <div className="flex gap-2 mt-2">
                        <span className={`badge tiny ${stats.system_health.db === 'ok' ? 'success' : 'danger'} `}>DB</span>
                        <span className={`badge tiny ${stats.system_health.redis === 'ok' ? 'success' : 'danger'} `}>CACHE</span>
                        <span className={`badge tiny ${stats.system_health.engine === 'ok' ? 'success' : 'danger'} `}>ENGINE</span>
                    </div>
                </div>
            </div>

            {/* USER MANAGEMENT */}
            <div className="card">
                <div className="card-header flex-between">
                    <h3>User Management</h3>
                    <div className="flex gap-2">
                        <input type="text" placeholder="Search users..." className="input small" style={{ width: '200px' }} />
                        <button className="button secondary small">Filter</button>
                    </div>
                </div>
                <table className="table w-full">
                    <thead>
                        <tr className="text-muted text-sm text-left">
                            <th className="p-3">User ID</th>
                            <th className="p-3">Email</th>
                            <th className="p-3">Role</th>
                            <th className="p-3">Tier</th>
                            <th className="p-3">Status</th>
                            <th className="p-3 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {usersRes.data?.map(u => (
                            <tr key={u.id} className="border-b border-subtle/10 hover:bg-subtle/5">
                                <td className="p-3 font-mono tiny text-muted">#{u.id}</td>
                                <td className="p-3 font-bold">{u.email}</td>
                                <td className="p-3">
                                    <span className={`badge tiny ${u.role === 'ADMIN' ? 'primary' : 'secondary'} `}>{u.role}</span>
                                </td>
                                <td className="p-3">
                                    <span className="badge outline tiny">{u.tier}</span>
                                </td>
                                <td className="p-3">
                                    <span className={`status - dot ${u.is_active ? 'success' : 'danger'} `}></span>
                                    <span className="tiny ml-2">{u.is_active ? 'Active' : 'Suspended'}</span>
                                </td>
                                <td className="p-3 text-right">
                                    <div className="flex gap-2 justify-end">
                                        <button
                                            className="button ghost tiny"
                                            onClick={() => handleAction(u.id, 'TIER', 'INST_PRO')}
                                        >
                                            Promote
                                        </button>
                                        <button
                                            className="button danger tiny outline"
                                            onClick={() => handleAction(u.id, 'BAN', '')}
                                        >
                                            Ban
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                        {(!usersRes.data || usersRes.data.length === 0) && (
                            <tr><td colSpan={6} className="p-8 text-center muted">Loading Users...</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
