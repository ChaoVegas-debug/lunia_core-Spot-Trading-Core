import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { AdminOverviewWidget } from '../components/widgets/admin/AdminOverviewWidget';
import { TenantManagerWidget } from '../components/widgets/admin/TenantManagerWidget';
import { UserManagerWidget } from '../components/widgets/admin/UserManagerWidget';
import { AuditLogViewer } from '../components/widgets/admin/AuditLogViewer';

export const AdminPanel: React.FC = () => {
  const auth = useAuth();

  // Strict Client-Side Verify (Backend still enforces)
  if (auth.role !== 'ADMIN') {
    return (
      <div className="page-container center-content">
        <div className="card error-border" style={{ padding: '48px', textAlign: 'center' }}>
          <h1 className="error-text">403 Forbidden</h1>
          <p className="muted">Institutional Control Plane access is restricted.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>

      <div style={{ marginBottom: '24px' }}>
        <div className="flex-row" style={{ justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '16px' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '24px', color: '#FF4C4C' }}>Institutional Control Plane</h1>
            <p className="muted small">Governance Level: ROOT • {new Date().toLocaleDateString()}</p>
          </div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: 'minmax(300px, 1fr) minmax(400px, 2fr)', gap: '24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <AdminOverviewWidget />
          <TenantManagerWidget />
        </div>
        <div>
          <UserManagerWidget />
        </div>
      </div>

      <div style={{ marginBottom: '24px' }}>
        <AuditLogViewer />
      </div>

    </div>
  );
};
