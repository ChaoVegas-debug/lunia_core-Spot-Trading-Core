/**
 * BALANCES WIDGET - F2 REFACTORED
 * 
 * Institutional live capital monitor with F1 standard compliance.
 * Dense table: ASSET | FREE | LOCKED | TOTAL | USD
 * Sorted by USD descending, filtered for non-zero balances.
 * 
 * Uses:
 * - WidgetShell (standard wrapper)
 * - usePoller (institutional polling)
 * - endpoints registry (wiring discipline)
 * - FailClosedPanel + ProvenanceFooter (automatic via WidgetShell)
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';

interface Balance {
    asset: string;
    free: number;
    locked: number;
}

interface BalancesResponse {
    balances: Balance[];
    request_id?: string;
    latency_ms?: number;
}

const getBalances = async (): Promise<BalancesResponse> => {
    return await fetchJSON<BalancesResponse>(endpoints.balances);
};

export const BalancesWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<BalancesResponse>({
        key: 'balances',
        endpoint: endpoints.balances,
        fetcher: getBalances,
        interval_ms: 5000,
        stale_threshold_s: 10,
        pause_when_hidden: true,
        force_refresh_on_focus: true,
    });

    const balances = data?.balances || [];

    // Filter zero balances and sort by USD value desc
    const processedBalances = balances
        .map(b => ({
            ...b,
            total: b.free + b.locked,
            usd: (b.free + b.locked) * 1.0, // Placeholder conversion
        }))
        .filter(b => b.total > 0.00001) // Epsilon filter
        .sort((a, b) => b.usd - a.usd);

    const statusDot = getStatusDot(error, isStale);

    return (
        <WidgetShell
            title="Live Balances"
            badgeType="LIVE"
            statusDot={statusDot}
            meta={meta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {processedBalances.length === 0 ? (
                <div style={{
                    padding: '1rem',
                    textAlign: 'center',
                    color: '#666',
                    fontSize: '11px'
                }}>
                    No balances available
                </div>
            ) : (
                <table style={{
                    width: '100%',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    borderCollapse: 'collapse',
                }}>
                    <thead>
                        <tr style={{
                            borderBottom: '1px solid var(--border-color)',
                            textAlign: 'left',
                        }}>
                            <th style={{ padding: '4px', fontWeight: 'bold' }}>ASSET</th>
                            <th style={{ padding: '4px', fontWeight: 'bold', textAlign: 'right' }}>FREE</th>
                            <th style={{ padding: '4px', fontWeight: 'bold', textAlign: 'right' }}>LOCKED</th>
                            <th style={{ padding: '4px', fontWeight: 'bold', textAlign: 'right' }}>TOTAL</th>
                            <th style={{ padding: '4px', fontWeight: 'bold', textAlign: 'right' }}>USD</th>
                        </tr>
                    </thead>
                    <tbody>
                        {processedBalances.map(bal => (
                            <tr key={bal.asset} style={{
                                borderBottom: '1px solid rgba(255,255,255,0.05)',
                            }}>
                                <td style={{ padding: '4px', color: '#fff' }}>{bal.asset}</td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#aaa' }}>
                                    {bal.free.toFixed(8)}
                                </td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#aaa' }}>
                                    {bal.locked.toFixed(8)}
                                </td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#fff', fontWeight: 'bold' }}>
                                    {bal.total.toFixed(8)}
                                </td>
                                <td style={{ padding: '4px', textAlign: 'right', color: '#10b981' }}>
                                    ${bal.usd.toFixed(2)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </WidgetShell>
    );
};
