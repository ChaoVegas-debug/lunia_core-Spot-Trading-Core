
import React, { useState } from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getOrders } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import { useAuth } from '../../hooks/useAuth';

export const TradingBlotterWidget: React.FC = () => {
    const auth = useAuth();
    const [tab, setTab] = useState<'ORDERS' | 'FILLS'>('ORDERS');
    const { data } = usePolledResource((signal) => getOrders(signal, { role: auth.role }), 5000, []);

    const items = tab === 'ORDERS' ? safeArray(data?.orders) : safeArray(data?.fills);

    return (
        <div className="card" style={{ minHeight: '300px' }}>
            <div className="card-header flex-between">
                <h3>Trading Blotter</h3>
                <div className="mode-selector">
                    <button className={tab === 'ORDERS' ? 'active-mode' : ''} onClick={() => setTab('ORDERS')}>Orders</button>
                    <button className={tab === 'FILLS' ? 'active-mode' : ''} onClick={() => setTab('FILLS')}>Fills</button>
                </div>
            </div>

            <div className="table-container" style={{ maxHeight: '250px', overflow: 'auto' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Side</th>
                            <th>Qty</th>
                            <th>Price</th>
                            <th>Venue</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items.map((item: any) => (
                            <tr key={item.id}>
                                <td className="tiny muted">{new Date(item.time).toLocaleTimeString()}</td>
                                <td style={{ fontWeight: 600 }}>{item.symbol}</td>
                                <td className={item.side === 'BUY' ? 'text-green' : 'text-red'}>{item.side}</td>
                                <td className="font-mono">{item.qty}</td>
                                <td className="font-mono">${item.price.toLocaleString()}</td>
                                <td className="small muted">{item.venue}</td>
                                <td><span className={`badge ${item.status === 'FILLED' ? 'success' : 'warning'}`}>{item.status}</span></td>
                            </tr>
                        ))}
                        {items.length === 0 && (
                            <tr><td colSpan={7} style={{ textAlign: 'center', padding: '1rem' }} className="muted">No records found</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
