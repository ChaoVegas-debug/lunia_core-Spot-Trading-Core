import React from 'react';
import { Outlet } from 'react-router-dom';
import { AdminSidebar } from './AdminSidebar';
import { useAuth } from '../../hooks/useAuth';
import { TourHelper } from '../../components/common/TourHelper';

export const AdminLayout: React.FC = () => {
    const { logout, user } = useAuth();
    const buildInfo = import.meta.env.VITE_APP_BUILD || 'dev';

    return (
        <div className="layout" style={{ background: '#0B0F19' }}> {/* Darker background */}
            <AdminSidebar />
            <div className="content">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid #374151', paddingBottom: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <h2 style={{ margin: 0, color: '#F3F4F6', fontSize: '1.25rem' }}>Control Plane</h2>
                        {user && <span className="badge secondary tiny" style={{ fontSize: '0.7rem' }}>ID: {user.id}</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div className="small muted">Build: {buildInfo}</div>
                        <button className="button secondary tiny" onClick={logout}>
                            Secure Logout
                        </button>
                    </div>
                </div>

                {/* Main Content Area */}
                <div style={{ flex: 1, overflowY: 'auto' }}>
                    <Outlet />
                </div>

                <footer className="footer" style={{ marginTop: '2rem', borderTop: '1px solid #374151', paddingTop: '1rem' }}>
                    <span className="small muted">LUNIA Governance Kernel Active</span>
                    <span className="small muted">Strict Audit Logging Enabled</span>
                </footer>
            </div>
            <TourHelper />
        </div>
    );
};
