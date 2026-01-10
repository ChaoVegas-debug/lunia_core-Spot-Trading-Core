import React from 'react';
import { UserManagerWidget } from '../../components/widgets/admin/UserManagerWidget';

export const AdminUsersPage: React.FC = () => {
    return (
        <div className="admin-page">
            <div className="flex-between" style={{ marginBottom: '1rem' }}>
                <h3>User Management</h3>
                <button className="button primary tiny" disabled title="Use 'postSeedDemo' for creating users">
                    + Invite User
                </button>
            </div>
            <UserManagerWidget />
        </div>
    );
};
