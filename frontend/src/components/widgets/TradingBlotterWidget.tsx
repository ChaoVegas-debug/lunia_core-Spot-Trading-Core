
import React, { useState } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getOrders } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import { useAuth } from '../../hooks/useAuth';
import { WidgetWrapper } from '../common/WidgetWrapper';

export const TradingBlotterWidget: React.FC = () => {
    const auth = useAuth();
    const [tab, setTab] = useState<'ORDERS' | 'FILLS'>('ORDERS');
    const { data, error } = usePoller({
        key: 'trading_blotter',
        endpoint: '/api/orders',
        fetcher: () => getOrders(new AbortController().signal, { role: auth.role }),
        interval_ms: 5000,
        critical: false
    });
    const loading = false;

    const items = tab === 'ORDERS' ? safeArray(data?.orders) : safeArray(data?.fills);

    return (
        <WidgetWrapper
            id="TradingBlotterWidget"
            title="Trading Blotter"
            loading={loading}
            error={error}
            rightElem={
                <div className="mode-selector">
                    <button className={tab === 'ORDERS' ? 'active-mode' : ''} onClick={() => setTab('ORDERS')}>Orders</button>
                    <button className={tab === 'FILLS' ? 'active-mode' : ''} onClick={() => setTab('FILLS')}>Fills</button>
                </div>
            }
        >
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
        </WidgetWrapper>
    );
};
