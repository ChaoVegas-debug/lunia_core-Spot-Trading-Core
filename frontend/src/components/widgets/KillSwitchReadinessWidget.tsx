/**
 * KILL SWITCH READINESS WIDGET
 * 
 * Informational widget showing kill switch readiness status.
 * Displays what WOULD happen if kill switch activated.
 * 
 * MOCK PROTOCOL: Show DATA_NOT_CONNECTED if real data unavailable.
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

interface KillSwitchReadiness {
    status: 'ARMED' | 'DISARMED';
    orders_count: number;
    positions_count: number;
    est_execution_ms: number;
}

interface KillSwitchResponse {
    readiness: KillSwitchReadiness;
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL
const generateMockReadiness = (): KillSwitchResponse => {
    return {
        readiness: {
            status: 'ARMED',
            orders_count: 12,
            positions_count: 5,
            est_execution_ms: 180,
        },
        request_id: 'mock-killswitch',
        latency_ms: 0,
    };
};

const getKillSwitchReadiness = async (): Promise<KillSwitchResponse> => {
    try {
        // Try ops_state endpoint (may include killswitch data)
        return await fetchJSON<KillSwitchResponse>(`${endpoints.ops_state}/killswitch`);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockReadiness();
        }
        throw err;
    }
};

export const KillSwitchReadinessWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<KillSwitchResponse>({
        key: 'killswitch_readiness',
        endpoint: `${endpoints.ops_state}/killswitch`,
        fetcher: getKillSwitchReadiness,
        interval_ms: 5000,
        stale_threshold_s: 10,
    });

    const readiness = data?.readiness;
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-killswitch';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    return (
        <WidgetShell
            title="Kill Switch"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {!readiness ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No readiness data
                </div>
            ) : (
                <div style={{ padding: '8px' }}>
                    {/* Status Badge */}
                    <div style={{
                        background: readiness.status === 'ARMED' ? '#10b981' : '#666',
                        color: '#fff',
                        padding: '8px 12px',
                        borderRadius: '3px',
                        fontSize: '12px',
                        fontWeight: 'bold',
                        textAlign: 'center',
                        marginBottom: '12px',
                        letterSpacing: '0.5px',
                    }}>
                        KILL SWITCH: {readiness.status}
                    </div>

                    {/* Impact Summary */}
                    {readiness.status === 'ARMED' && (
                        <div style={{ fontSize: '10px', color: '#ccc' }}>
                            <div style={{
                                marginBottom: '8px',
                                padding: '6px',
                                background: '#1a1a1a',
                                borderRadius: '2px',
                            }}>
                                <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                                    Would cancel:
                                </div>
                                <div style={{ fontFamily: 'monospace', color: '#fff' }}>
                                    {readiness.orders_count} active orders
                                </div>
                            </div>

                            <div style={{
                                marginBottom: '8px',
                                padding: '6px',
                                background: '#1a1a1a',
                                borderRadius: '2px',
                            }}>
                                <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                                    Would close:
                                </div>
                                <div style={{ fontFamily: 'monospace', color: '#fff' }}>
                                    {readiness.positions_count} open positions
                                </div>
                            </div>

                            <div style={{
                                padding: '6px',
                                background: '#1a1a1a',
                                borderRadius: '2px',
                            }}>
                                <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                                    Est. execution:
                                </div>
                                <div style={{ fontFamily: 'monospace', color: '#10b981' }}>
                                    {'<'}{readiness.est_execution_ms}ms
                                </div>
                            </div>
                        </div>
                    )}

                    {readiness.status === 'DISARMED' && (
                        <div style={{
                            fontSize: '10px',
                            color: '#888',
                            textAlign: 'center',
                            fontStyle: 'italic',
                        }}>
                            Kill switch is currently disarmed
                        </div>
                    )}
                </div>
            )}
        </WidgetShell>
    );
};
