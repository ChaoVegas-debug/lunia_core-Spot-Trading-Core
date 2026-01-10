import React from 'react';
import { TenantManagerWidget } from '../../components/widgets/admin/TenantManagerWidget';

export const AdminTenantsPage: React.FC = () => {
    return (
        <div className="admin-page">
            <h3 style={{ marginBottom: '1rem' }}>Tenant Configuration</h3>
            <TenantManagerWidget />
        </div>
    );
};
