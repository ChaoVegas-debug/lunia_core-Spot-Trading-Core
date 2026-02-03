/**
 * INCIDENTS WIDGET
 * 
 * Dense operational incidents timeline.
 * Format: [time] [severity] [title] [source]
 * 
 * MOCK PROTOCOL: Seeded incident history if endpoint missing.
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

type IncidentSeverity = 'LOW' | 'MED' | 'HIGH' | 'CRITICAL';

interface Incident {
    timestamp: number;
    severity: IncidentSeverity;
    title: string;
    source: string; // 'EXCHANGE', 'GOVERNOR', 'STRATEGY', 'OPERATOR'
}

interface IncidentsResponse {
    incidents: Incident[];
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL: Realistic incident timeline
const generateMockIncidents = (): IncidentsResponse => {
    const now = Date.now();
    return {
        incidents: [
            { timestamp: now - 120000, severity: 'HIGH', title: 'Order rejection - insufficient margin', source: 'EXCHANGE' },
            { timestamp: now - 300000, severity: 'MED', title: 'Strategy paused - risk limit', source: 'GOVERNOR' },
            { timestamp: now - 600000, severity: 'LOW', title: 'Websocket reconnect', source: 'EXCHANGE' },
            { timestamp: now - 900000, severity: 'MED', title: 'Latency spike detected (>500ms)', source: 'STRATEGY' },
            { timestamp: now - 1200000, severity: 'HIGH', title: 'Manual mode transition', source: 'OPERATOR' },
        ],
        request_id: 'mock-incidents',
        latency_ms: 0,
    };
};

const getIncidents = async (): Promise<IncidentsResponse> => {
    try {
        return await fetchJSON<IncidentsResponse>(endpoints.ops_incidents);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockIncidents();
        }
        throw err;
    }
};

export const IncidentsWidget: React.FC = () => {
    const { data, error, meta, isStale, lastGood } = usePoller<IncidentsResponse>({
        key: 'ops_incidents',
        endpoint: endpoints.ops_incidents,
        fetcher: getIncidents,
        interval_ms: 10000,
        stale_threshold_s: 20,
    });

    const incidents = data?.incidents || [];
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-incidents';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    // Severity color
    const getSeverityColor = (severity: IncidentSeverity): string => {
        switch (severity) {
            case 'CRITICAL': return '#dc2626';
            case 'HIGH': return '#f59e0b';
            case 'MED': return '#f59e0b';
            case 'LOW': return '#666';
        }
    };

    return (
        <WidgetShell
            title="Incidents"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {incidents.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No recent incidents
                </div>
            ) : (
                <div style={{ fontSize: '10px', fontFamily: 'monospace' }}>
                    {incidents.map((inc, idx) => {
                        const time = new Date(inc.timestamp).toLocaleTimeString();
                        return (
                            <div
                                key={idx}
                                style={{
                                    padding: '6px 4px',
                                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                                    display: 'grid',
                                    gridTemplateColumns: '70px 50px 1fr 80px',
                                    gap: '8px',
                                    alignItems: 'center',
                                }}
                            >
                                {/* Time */}
                                <span style={{ color: '#888' }}>{time}</span>

                                {/* Severity */}
                                <span style={{
                                    color: getSeverityColor(inc.severity),
                                    fontWeight: 'bold',
                                }}>
                                    {inc.severity}
                                </span>

                                {/* Title */}
                                <span style={{ color: '#ccc' }}>{inc.title}</span>

                                {/* Source */}
                                <span style={{
                                    color: '#666',
                                    fontSize: '9px',
                                    textAlign: 'right',
                                }}>
                                    [{inc.source}]
                                </span>
                            </div>
                        );
                    })}
                </div>
            )}
        </WidgetShell>
    );
};
