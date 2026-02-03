/**
 * DRIFT MONITOR WIDGET
 * 
 * Virtual vs Live position drift monitoring.
 * Status: SYNCED / SOFT_DRIFT / HARD_DRIFT
 * 
 * HARD_DRIFT shows red emphasis + action advisory.
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

type DriftStatus = 'SYNCED' | 'SOFT_DRIFT' | 'HARD_DRIFT';

interface DriftData {
    status: DriftStatus;
    drift_pct: number;
    details?: string;
}

interface DriftResponse {
    drift: DriftData;
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL: Always synced
const generateMockDrift = (): DriftResponse => {
    return {
        drift: {
            status: 'SYNCED',
            drift_pct: 0.2,
            details: 'Virtual positions match live within tolerance',
        },
        request_id: 'mock-drift',
        latency_ms: 0,
    };
};

const getDrift = async (): Promise<DriftResponse> => {
    try {
        return await fetchJSON<DriftResponse>(endpoints.risk_drift);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockDrift();
        }
        throw err;
    }
};

export const DriftMonitorWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<DriftResponse>({
        key: 'risk_drift',
        endpoint: endpoints.risk_drift,
        fetcher: getDrift,
        interval_ms: 5000,
        stale_threshold_s: 10,
    });

    const drift = data?.drift;
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-drift';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    // Status color coding
    const getStatusColor = (status: DriftStatus | undefined): string => {
        switch (status) {
            case 'SYNCED': return '#10b981';
            case 'SOFT_DRIFT': return '#f59e0b';
            case 'HARD_DRIFT': return '#dc2626';
            default: return '#666';
        }
    };

    return (
        <WidgetShell
            title="Drift Monitor"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {!drift ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No drift data
                </div>
            ) : (
                <div style={{ padding: '8px' }}>
                    {/* Status Badge */}
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '12px',
                    }}>
                        <div style={{
                            background: getStatusColor(drift.status),
                            color: drift.status === 'SOFT_DRIFT' ? '#000' : '#fff',
                            padding: '6px 12px',
                            borderRadius: '3px',
                            fontSize: '11px',
                            fontWeight: 'bold',
                            letterSpacing: '0.5px',
                        }}>
                            {drift.status}
                        </div>
                        <div style={{
                            fontFamily: 'monospace',
                            fontSize: '10px',
                            color: '#aaa',
                        }}>
                            {drift.drift_pct.toFixed(2)}% drift
                        </div>
                    </div>

                    {/* Details */}
                    {drift.details && (
                        <div style={{
                            fontSize: '10px',
                            color: '#999',
                            marginBottom: '12px',
                            lineHeight: '1.4',
                        }}>
                            {drift.details}
                        </div>
                    )}

                    {/* HARD_DRIFT Advisory */}
                    {drift.status === 'HARD_DRIFT' && (
                        <div style={{
                            background: '#dc262620',
                            border: '1px solid #dc2626',
                            padding: '8px',
                            borderRadius: '3px',
                            marginTop: '8px',
                        }}>
                            <div style={{
                                fontSize: '10px',
                                fontWeight: 'bold',
                                color: '#dc2626',
                                marginBottom: '4px',
                            }}>
                                ⚠️ RECOMMENDED ACTION
                            </div>
                            <div style={{
                                fontSize: '9px',
                                color: '#dc2626',
                            }}>
                                Consider STOP or MANUAL mode to prevent position misalignment.
                            </div>
                        </div>
                    )}
                </div>
            )}
        </WidgetShell>
    );
};
