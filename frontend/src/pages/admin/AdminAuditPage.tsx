import React from 'react';
import { AuditLogViewer } from '../../components/widgets/admin/AuditLogViewer';

export const AdminAuditPage: React.FC = () => {
    return (
        <div className="admin-page">
            <h3 style={{ marginBottom: '1rem' }}>Immutable Audit Log</h3>
            <AuditLogViewer />
        </div>
    );
};
