/**
 * ORDERS WIDGET
 * 
 * Active orders monitor with MOCK PROTOCOL for missing endpoint.
 * Table: TIME | ID | TYPE | SIDE | PRICE | QTY | STATUS
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

interface Order {
    order_id: string;
    symbol: string;
    type: 'LIMIT' | 'MARKET' | 'STOP_LOSS';
    side: 'BUY' | 'SELL';
    price: number;
    qty: number;
    status: 'NEW' | 'PARTIALLY_FILLED' | 'PENDING';
    timestamp: number;
}

interface OrdersResponse {
    orders: Order[];
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL: Deterministic seeded orders
const generateMockOrders = (): OrdersResponse => {
    const now = Date.now();
    return {
        orders: [
            { order_id: 'ORD_001', symbol: 'BTCUSDT', type: 'LIMIT', side: 'BUY', price: 42000, qty: 0.1, status: 'NEW', timestamp: now - 120000 },
            { order_id: 'ORD_002', symbol: 'ETHUSDT', type: 'LIMIT', side: 'SELL', price: 2300, qty: 1.5, status: 'PARTIALLY_FILLED', timestamp: now - 60000 },
            { order_id: 'ORD_003', symbol: 'SOLUSDT', type: 'STOP_LOSS', side: 'SELL', price: 95.00, qty: 25, status: 'PENDING', timestamp: now - 30000 },
        ],
        request_id: 'mock-orders',
        latency_ms: 0,
    };
};

const getOrders = async (): Promise<OrdersResponse> => {
    try {
        return await fetchJSON<OrdersResponse>(endpoints.orders_active);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockOrders();
        }
        throw err;
    }
};

export const OrdersWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<OrdersResponse>({
        key: 'orders_active',
        endpoint: endpoints.orders_active,
        fetcher: getOrders,
        interval_ms: 5000,
        stale_threshold_s: 10,
    });

    const orders = data?.orders || [];
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-orders';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    return (
        <WidgetShell
            title="Active Orders"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {orders.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No active orders
                </div>
            ) : (
                <table style={{
                    width: '100%',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    borderCollapse: 'collapse',
                }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-color)', textAlign: 'left' }}>
                            <th style={{ padding: '4px' }}>TIME</th>
                            <th style={{ padding: '4px' }}>ID</th>
                            <th style={{ padding: '4px' }}>TYPE</th>
                            <th style={{ padding: '4px' }}>SIDE</th>
                            <th style={{ padding: '4px', textAlign: 'right' }}>PRICE</th>
                            <th style={{ padding: '4px', textAlign: 'right' }}>QTY</th>
                            <th style={{ padding: '4px' }}>STATUS</th>
                        </tr>
                    </thead>
                    <tbody>
                        {orders.map(ord => {
                            const time = new Date(ord.timestamp).toLocaleTimeString();
                            return (
                                <tr key={ord.order_id} style={{
                                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                                }}>
                                    <td style={{ padding: '4px', color: '#888' }}>{time}</td>
                                    <td style={{ padding: '4px', color: '#aaa' }}>{ord.order_id}</td>
                                    <td style={{ padding: '4px', color: '#ccc' }}>{ord.type}</td>
                                    <td style={{
                                        padding: '4px',
                                        color: ord.side === 'BUY' ? '#10b981' : '#dc2626',
                                        fontWeight: 'bold'
                                    }}>
                                        {ord.side}
                                    </td>
                                    <td style={{ padding: '4px', textAlign: 'right', color: '#fff' }}>
                                        ${ord.price.toFixed(2)}
                                    </td>
                                    <td style={{ padding: '4px', textAlign: 'right', color: '#aaa' }}>
                                        {ord.qty.toFixed(4)}
                                    </td>
                                    <td style={{
                                        padding: '4px',
                                        color: ord.status === 'NEW' ? '#10b981' : ord.status === 'PARTIALLY_FILLED' ? '#f59e0b' : '#888'
                                    }}>
                                        {ord.status}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            )}
        </WidgetShell>
    );
};
