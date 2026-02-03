/**
 * PNL WIDGET
 * 
 * High-density PnL display: Today / 7D / MTD
 * Optional tiny sparkline for visual trend.
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

interface PnLData {
    today: number;
    week: number;
    month: number;
    sparkline?: number[]; // Optional 7-day history for sparkline
}

interface PnLResponse {
    pnl: PnLData;
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL: Deterministic PnL
const generateMockPnL = (): PnLResponse => {
    return {
        pnl: {
            today: 145.32,
            week: 892.15,
            month: 2347.88,
            sparkline: [100, 150, 120, 180, 220, 200, 245],
        },
        request_id: 'mock-pnl',
        latency_ms: 0,
    };
};

const getPnL = async (): Promise<PnLResponse> => {
    try {
        return await fetchJSON<PnLResponse>(endpoints.pnl_history);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockPnL();
        }
        throw err;
    }
};

export const PnLWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<PnLResponse>({
        key: 'pnl_history',
        endpoint: endpoints.pnl_history,
        fetcher: getPnL,
        interval_ms: 10000, // 10s poll (less critical than positions)
        stale_threshold_s: 20,
    });

    const pnl = data?.pnl;
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-pnl';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    // Simple sparkline SVG
    const renderSparkline = (values: number[]) => {
        if (!values || values.length < 2) return null;

        const max = Math.max(...values);
        const min = Math.min(...values);
        const range = max - min || 1;

        const points = values.map((v, i) => {
            const x = (i / (values.length - 1)) * 100;
            const y = 100 - ((v - min) / range) * 100;
            return `${x},${y}`;
        }).join(' ');

        return (
            <svg width="100%" height="30" style={{ marginTop: '8px' }}>
                <polyline
                    points={points}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                />
            </svg>
        );
    };

    return (
        <WidgetShell
            title="PnL"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {!pnl ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No PnL data
                </div>
            ) : (
                <div style={{ padding: '4px' }}>
                    {/* PnL Blocks */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr 1fr',
                        gap: '8px',
                    }}>
                        {/* Today */}
                        <div style={{
                            background: '#1a1a1a',
                            padding: '8px',
                            borderRadius: '3px',
                        }}>
                            <div style={{ fontSize: '9px', color: '#888', textTransform: 'uppercase' }}>
                                Today
                            </div>
                            <div style={{
                                fontSize: '14px',
                                fontFamily: 'monospace',
                                fontWeight: 'bold',
                                color: pnl.today >= 0 ? '#10b981' : '#dc2626',
                                marginTop: '4px',
                            }}>
                                {pnl.today >= 0 ? '+' : ''}{pnl.today.toFixed(2)}
                            </div>
                        </div>

                        {/* 7D */}
                        <div style={{
                            background: '#1a1a1a',
                            padding: '8px',
                            borderRadius: '3px',
                        }}>
                            <div style={{ fontSize: '9px', color: '#888', textTransform: 'uppercase' }}>
                                7D
                            </div>
                            <div style={{
                                fontSize: '14px',
                                fontFamily: 'monospace',
                                fontWeight: 'bold',
                                color: pnl.week >= 0 ? '#10b981' : '#dc2626',
                                marginTop: '4px',
                            }}>
                                {pnl.week >= 0 ? '+' : ''}{pnl.week.toFixed(2)}
                            </div>
                        </div>

                        {/* MTD */}
                        <div style={{
                            background: '#1a1a1a',
                            padding: '8px',
                            borderRadius: '3px',
                        }}>
                            <div style={{ fontSize: '9px', color: '#888', textTransform: 'uppercase' }}>
                                MTD
                            </div>
                            <div style={{
                                fontSize: '14px',
                                fontFamily: 'monospace',
                                fontWeight: 'bold',
                                color: pnl.month >= 0 ? '#10b981' : '#dc2626',
                                marginTop: '4px',
                            }}>
                                {pnl.month >= 0 ? '+' : ''}{pnl.month.toFixed(2)}
                            </div>
                        </div>
                    </div>

                    {/* Optional Sparkline */}
                    {pnl.sparkline && renderSparkline(pnl.sparkline)}
                </div>
            )}
        </WidgetShell>
    );
};
