
import React, { useEffect, useState } from 'react';
import { getFundAccounts } from '../../../api/endpoints';
import { FundAccount } from '../../../api/types';

export const AccountsTable: React.FC = () => {
    const [accounts, setAccounts] = useState<FundAccount[]>([]);

    useEffect(() => {
        const controller = new AbortController();
        getFundAccounts(controller.signal)
            .then((res) => res && setAccounts(res));
        return () => controller.abort();
    }, []);

    return (
        <div className="widget accounts-table">
            <h3>Managed Accounts</h3>
            <table style={{ width: '100%', marginTop: '12px' }}>
                <thead>
                    <tr>
                        <th style={{ textAlign: 'left' }}>ID</th>
                        <th style={{ textAlign: 'left' }}>Name</th>
                        <th style={{ textAlign: 'right' }}>AUM</th>
                        <th style={{ textAlign: 'center' }}>Mode</th>
                        <th style={{ textAlign: 'center' }}>Risk</th>
                        <th style={{ textAlign: 'center' }}>Active</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {accounts.map((acc) => (
                        <tr key={acc.id} style={{ opacity: acc.active ? 1 : 0.5 }}>
                            <td>#{acc.id}</td>
                            <td>{acc.name}</td>
                            <td style={{ textAlign: 'right' }}>${acc.aum.toLocaleString()}</td>
                            <td style={{ textAlign: 'center' }}>{acc.mode}</td>
                            <td style={{ textAlign: 'center' }}>
                                <span className={`tag ${acc.risk_status === 'OK' ? 'green' : 'red'}`}>
                                    {acc.risk_status}
                                </span>
                            </td>
                            <td style={{ textAlign: 'center' }}>{acc.active ? 'Yes' : 'No'}</td>
                            <td>
                                <button className="btn-xs" disabled>View</button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};
