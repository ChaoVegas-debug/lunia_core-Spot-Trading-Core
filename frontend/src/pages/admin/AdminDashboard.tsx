import React from 'react';
import { AdminOverviewWidget } from '../../components/widgets/admin/AdminOverviewWidget';
import { AdminSubscriptionWidget } from '../../components/widgets/admin/AdminSubscriptionWidget';

export const AdminDashboard: React.FC = () => {
    return (
        <div className="admin-page">
            <h1 className="visually-hidden">Dashboard</h1>
            <AdminOverviewWidget />

            {/* Quick Links / Status Cards could go here if not in widget */}
            <div className="grid cols-3" style={{ marginTop: '24px', gap: '16px' }}>
                <div className="card" style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                    <div className="small muted uppercase">System Status</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#10B981' }}>OPERATIONAL</div>
                </div>
                <div className="card" style={{ padding: '16px', background: 'rgba(59, 130, 246, 0.05)', border: '1px solid rgba(59, 130, 246, 0.2)' }}>
                    <div className="small muted uppercase">Active Strategy Core</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#3B82F6' }}>SHIELD v1.2</div>
                </div>
                <div className="card" style={{ padding: '16px' }}>
                    <div className="small muted uppercase">Governance Mode</div>
                    <div className="badge primary">STRICT</div>
                </div>
            </div>

            {/* P2.2: Dev Tools for Subscription Simulation */}
            <div style={{ marginTop: '24px' }}>
                <AdminSubscriptionWidget />
            </div>

            {/* P2.3: System Modules Navigation (Surfaced Capabilities) */}
            <div style={{ marginTop: '24px' }}>
                <h3 className="section-header">System Modules</h3>
                <div className="grid cols-3" style={{ gap: '16px' }}>
                    <a href="/admin/users" className="card hover-bright p-4 text-decoration-none">
                        <div className="flex-between mb-2">
                            <span className="tiny font-bold uppercase text-primary">IAM</span>
                            <span>👥</span>
                        </div>
                        <h4>User Management</h4>
                        <p className="tiny muted">Role assignment & access control</p>
                    </a>

                    <a href="/admin/exchanges" className="card hover-bright p-4 text-decoration-none">
                        <div className="flex-between mb-2">
                            <span className="tiny font-bold uppercase text-primary">Connectivity</span>
                            <span>🔌</span>
                        </div>
                        <h4>Exchange Health</h4>
                        <p className="tiny muted">Latency & connection status</p>
                    </a>

                    <a href="/admin/flags" className="card hover-bright p-4 text-decoration-none">
                        <div className="flex-between mb-2">
                            <span className="tiny font-bold uppercase text-primary">Config</span>
                            <span>🚩</span>
                        </div>
                        <h4>Feature Flags</h4>
                        <p className="tiny muted">Runtime toggle management</p>
                    </a>

                    <a href="/admin/audit" className="card hover-bright p-4 text-decoration-none">
                        <div className="flex-between mb-2">
                            <span className="tiny font-bold uppercase text-primary">Compliance</span>
                            <span>📜</span>
                        </div>
                        <h4>Audit Log</h4>
                        <p className="tiny muted">Immutable system record</p>
                    </a>

                    <a href="/admin/incidents" className="card hover-bright p-4 text-decoration-none">
                        <div className="flex-between mb-2">
                            <span className="tiny font-bold uppercase text-primary">Ops</span>
                            <span>🚨</span>
                        </div>
                        <h4>Incident Timeline</h4>
                        <p className="tiny muted">Critical event history</p>
                    </a>

                    <a href="/admin/tenants" className="card hover-bright p-4 text-decoration-none" style={{ opacity: 0.6 }}>
                        <div className="flex-between mb-2">
                            <span className="tiny font-bold uppercase text-primary">Multi-Tenancy</span>
                            <span>🏢</span>
                        </div>
                        <h4>Tenants</h4>
                        <p className="tiny muted">Read-only view</p>
                    </a>
                </div>
            </div>
        </div>
    );
};
