import React from 'react';
import { ExchangeHealthWidget } from '../../components/widgets/admin/ExchangeHealthWidget';

export const AdminExchangesPage: React.FC = () => {
    return (
        <div className="admin-page">
            <h3 style={{ marginBottom: '1rem' }}>Global Venue Connectivity</h3>
            <ExchangeHealthWidget />
        </div>
    );
};
