/**
 * POSITIONS WIDGET
 * 
 * Live positions monitor with MOCK PROTOCOL for missing endpoint.
 * Table: SYMBOL | SIDE | SIZE | ENTRY | MARK | PNL | LIQ
 * 
 * Mock Protocol (if endpoint 404):
 * - Deterministic seeded positions
 * - Amber [MOCKED] badge
 * - meta.source = 'sim'
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

interface Position {
    symbol: string;
    side: 'LONG' | 'SHORT';
    size: number;
    entry_price: number;
    mark_price: number;
    pnl: number;
    liq_price: number;
}

interface PositionsResponse {
    positions: Position[];
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL: Deterministic seeded positions
const generateMockPositions = (): PositionsResponse => {
    return {
        positions: [
            { symbol: 'BTCUSDT', side: 'LONG', size: 0.125, entry_price: 42500, mark_price: 43200, pnl: 87.50, liq_price: 38000 },
            { symbol: 'ETHUSDT', side: 'SHORT', size: 2.5, entry_price: 2250, mark_price: 2180, pnl: 175.00, liq_price: 2600 },
            { symbol: 'SOLUSDT', side: 'LONG', size: 50, entry_price: 98.50, mark_price: 102.30, pnl: 190.00, liq_price: 85.00 },
        ],
        request_id: 'mock-positions',
        latency_ms: 0,
    };
};

const getPositions = async (): Promise<PositionsResponse> => {
    try {
        return await fetchJSON<PositionsResponse>(endpoints.positions);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            // MOCK PROTOCOL: Endpoint missing
            return generateMockPositions();
        }
        throw err;
    }
};

export const PositionsWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<PositionsResponse>({
        key: 'positions',
        endpoint: endpoints.positions,
        fetcher: getPositions,
        interval_ms: 5000,
        stale_threshold_s: 10,
    });

    const positions = data?.positions || [];
    const statusDot = getStatusDot(error, isStale);

    // Check if mocked
    const isMocked = data?.request_id === 'mock-positions';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    return (
        <WidgetShell
            title="Positions"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {positions.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No open positions
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
                            <th style={{ padding: '4px' }}>SYMBOL</th>
                            <th style={{ padding: '4px' }}>SIDE</th>
                            <th style={{ padding: '4px', textAlign: 'right' }}>SIZE</th>
                            <th style={{ padding: '4px', textAlign: 'right' }}>ENTRY</th>
                            <th style={{ padding: '4px', textAlign: 'right' }}>MARK</th>
                            <th style={{ padding: '4px', textAlign: 'right' }}>PNL</th>
                            <th style={{ padding: '4px', textAlign: 'right' }}>LIQ</th>
                        </tr>
                    </thead>
                    <tbody>
                        {positions.map(pos => (
                            <tr key={pos.symbol + pos.side} style={{
                                borderBottom: '1px solid rgba(255,255,255,0.05)',
                            }}>
                                <td style={{ padding: '4px', color: '#fff' }}>{pos.symbol}</td>
                                <td style={{
                                    padding: '4px',
                                    color: pos.side === 'LONG' ? '#10b981' : '#dc2626',
                                    fontWeight: 'bold'
                                }}>
                                    {pos.side}
                                </td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#aaa' }}>
                                    {pos.size.toFixed(4)}
                                </td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#aaa' }}>
                                    ${pos.entry_price.toFixed(2)}
                                </td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#fff' }}>
                                    ${pos.mark_price.toFixed(2)}
                                </td>
                                <td style={{
                                    padding: '4px',
                                    textAlign: 'right',
                                    color: pos.pnl >= 0 ? '#10b981' : '#dc2626',
                                    fontWeight: 'bold'
                                }}>
                                    {pos.pnl >= 0 ? '+' : ''}{pos.pnl.toFixed(2)}
                                </td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#666' }}>
                                    ${pos.liq_price.toFixed(2)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </WidgetShell>
    );
};
