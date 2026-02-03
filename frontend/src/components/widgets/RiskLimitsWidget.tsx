/**
 * RISK LIMITS WIDGET
 * 
 * 3 Utilization Bars for risk monitoring:
 * - Exposure Utilization (current / max)
 * - Daily Drawdown (current / limit)
 * - Leverage (current / max)
 * 
 * Color-coded: Grey (safe), Amber (>70%), Red (>90%)
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

interface RiskLimit {
    label: string;
    current: number;
    max: number;
    unit: string; // '%', '$', 'x'
}

interface RiskLimitsResponse {
    limits: RiskLimit[];
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL: Safe default limits
const generateMockLimits = (): RiskLimitsResponse => {
    return {
        limits: [
            { label: 'Exposure Utilization', current: 45, max: 100, unit: '%' },
            { label: 'Daily Drawdown', current: 12, max: 100, unit: '%' },
            { label: 'Leverage', current: 2.3, max: 5.0, unit: 'x' },
        ],
        request_id: 'mock-risk-limits',
        latency_ms: 0,
    };
};

const getRiskLimits = async (): Promise<RiskLimitsResponse> => {
    try {
        return await fetchJSON<RiskLimitsResponse>(endpoints.risk_limits);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockLimits();
        }
        throw err;
    }
};

export const RiskLimitsWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<RiskLimitsResponse>({
        key: 'risk_limits',
        endpoint: endpoints.risk_limits,
        fetcher: getRiskLimits,
        interval_ms: 10000, // 10s poll
        stale_threshold_s: 20,
    });

    const limits = data?.limits || [];
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-risk-limits';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    // Color based on utilization
    const getColor = (current: number, max: number): string => {
        const pct = (current / max) * 100;
        if (pct >= 90) return '#dc2626'; // Red
        if (pct >= 70) return '#f59e0b'; // Amber
        return '#666'; // Grey
    };

    return (
        <WidgetShell
            title="Risk Limits"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {limits.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No risk limits configured
                </div>
            ) : (
                <div style={{ padding: '4px' }}>
                    {limits.map((limit, idx) => {
                        const pct = (limit.current / limit.max) * 100;
                        const color = getColor(limit.current, limit.max);

                        return (
                            <div key={idx} style={{ marginBottom: '12px' }}>
                                {/* Label + Values */}
                                <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    marginBottom: '4px',
                                    fontSize: '10px',
                                }}>
                                    <span style={{ color: '#ccc', fontWeight: 'bold' }}>
                                        {limit.label}
                                    </span>
                                    <span style={{ fontFamily: 'monospace', color }}>
                                        {limit.current.toFixed(limit.unit === 'x' ? 1 : 0)}
                                        {limit.unit} / {limit.max.toFixed(limit.unit === 'x' ? 1 : 0)}
                                        {limit.unit}
                                    </span>
                                </div>

                                {/* Progress Bar */}
                                <div style={{
                                    width: '100%',
                                    height: '8px',
                                    background: '#1a1a1a',
                                    borderRadius: '2px',
                                    overflow: 'hidden',
                                }}>
                                    <div style={{
                                        width: `${Math.min(pct, 100)}%`,
                                        height: '100%',
                                        background: color,
                                        transition: 'width 0.3s ease',
                                    }} />
                                </div>

                                {/* Percentage */}
                                <div style={{
                                    fontSize: '9px',
                                    color: '#888',
                                    marginTop: '2px',
                                    fontFamily: 'monospace',
                                }}>
                                    {pct.toFixed(1)}%
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </WidgetShell>
    );
};
