
import React, { useEffect, useState } from 'react';
import { getAdminTenants } from '../../../api/endpoints';
import { Tenant } from '../../../api/types';

export const LimitsOverviewWidget: React.FC = () => {
    const [tenant, setTenant] = useState<Tenant | null>(null);

    useEffect(() => {
        const controller = new AbortController();
        getAdminTenants(controller.signal)
            .then((res) => {
                if (res && res.length > 0) setTenant(res[0]); // Default tenant
            })
            .catch(() => { });
        return () => controller.abort();
    }, []);

    if (!tenant) return <div className="widget loading">Loading Limits...</div>;

    return (
        <div className="widget limits-overview">
            <h3>Tenant Limits</h3>
            <div className="kv-list" style={{ marginTop: '12px' }}>
                <div className="kv-item" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #333' }}>
                    <span className="key muted">Plan</span>
                    <span className="value accent">{tenant.plan}</span>
                </div>
                <div className="kv-item" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #333' }}>
                    <span className="key muted">Max Accounts</span>
                    <span className="value">{tenant.limits?.max_accounts || 'Unlimited'}</span>
                </div>
                <div className="kv-item" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #333' }}>
                    <span className="key muted">Max AUM</span>
                    <span className="value">{tenant.limits?.max_aum === -1 ? 'Unlimited' : `$${tenant.limits?.max_aum}`}</span>
                </div>
                <div className="kv-item" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #333' }}>
                    <span className="key muted">Max Strategies</span>
                    <span className="value">{tenant.limits?.max_strategies}</span>
                </div>
                <div className="kv-item" style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                    <span className="key muted">Max Exchanges</span>
                    <span className="value">{tenant.limits?.max_exchanges}</span>
                </div>
            </div>
        </div>
    );
};
