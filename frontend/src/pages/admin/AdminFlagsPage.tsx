import React from 'react';
import { FeatureFlagsWidget } from '../../components/widgets/admin/FeatureFlagsWidget';

export const AdminFlagsPage: React.FC = () => {
    return (
        <div className="admin-page">
            <div className="alert warning" style={{ marginBottom: '1rem' }}>
                Warning: Modifying feature flags changes runtime behavior for all tenants.
            </div>
            <FeatureFlagsWidget />
        </div>
    );
};
