import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export const AdminSidebar: React.FC = () => {
    const { role } = useAuth();
    const location = useLocation();

    return (
        <div className="sidebar" style={{ background: '#111827', borderRight: '1px solid #374151' }}>
            <h3 style={{
                padding: '0 1rem',
                marginBottom: '1.5rem',
                color: '#EF4444', // Red for Admin/Operator
                fontWeight: '700',
                fontSize: '1.1rem',
                letterSpacing: '-0.02em',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
            }}>
                <span>LUNIA</span>
                <span style={{ color: '#F3F4F6', background: '#EF4444', padding: '0.1rem 0.3rem', borderRadius: '4px', fontSize: '0.7em' }}>OPERATOR</span>
            </h3>

            <nav>
                <div className="nav-section">
                    <div className="nav-section-title" style={{ color: '#9CA3AF' }}>GOVERNANCE</div>
                    <Link to="/admin" className={`nav-link ${location.pathname === '/admin' ? 'active' : ''}`}>
                        Overview
                    </Link>
                    <Link to="/admin/users" className={`nav-link ${location.pathname.startsWith('/admin/users') ? 'active' : ''}`}>
                        User Manager
                    </Link>
                    <Link to="/admin/tenants" className={`nav-link ${location.pathname.startsWith('/admin/tenants') ? 'active' : ''}`}>
                        Tenants
                    </Link>
                </div>

                <div className="nav-section">
                    <div className="nav-section-title" style={{ color: '#9CA3AF' }}>SYSTEM</div>
                    <Link to="/admin/audit" className={`nav-link ${location.pathname.startsWith('/admin/audit') ? 'active' : ''}`}>
                        Audit Log
                    </Link>
                    <Link to="/admin/incidents" className={`nav-link ${location.pathname.startsWith('/admin/incidents') ? 'active' : ''}`}>
                        Incidents
                    </Link>
                    <Link to="/admin/flags" className={`nav-link ${location.pathname.startsWith('/admin/flags') ? 'active' : ''}`}>
                        Feature Flags
                    </Link>
                    <Link to="/admin/exchanges" className={`nav-link ${location.pathname.startsWith('/admin/exchanges') ? 'active' : ''}`}>
                        Exchange Health
                    </Link>
                </div>

                <div className="nav-section">
                    <div className="nav-section-title" style={{ color: '#9CA3AF' }}>APP</div>
                    <Link to="/trader" className="nav-link">
                        &larr; Return to Trader
                    </Link>
                </div>
            </nav>
        </div>
    );
};
