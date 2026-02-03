import React, { useState } from 'react';
import { EvidenceEvent } from '../../lib/forensics/evidenceTypes';

interface ExecutionTraceProps {
    intentId: string;
    events: EvidenceEvent[];
    finalStatus?: 'SUCCESS' | 'PARTIAL' | 'FAILED';
}

/**
 * EXECUTION TRACE (ZONE 4)
 * 
 * Post-execution timeline showing:
 * - All request/response events
 * - request_ids from headers
 * - Latencies
 * - Final status
 * - Undo generator (future)
 */
export const ExecutionTrace: React.FC<ExecutionTraceProps> = ({ intentId, events, finalStatus }) => {
    const [expanded, setExpanded] = useState(false);

    const intentEvents = events.filter(e => e.client_intent_id === intentId);

    const getStatusColor = (status: number | string): string => {
        if (typeof status === 'number') {
            if (status >= 200 && status < 300) return 'var(--accent-success)';
            if (status >= 400) return 'var(--accent-danger)';
            return 'var(--accent-warning)';
        }
        if (status === 'SUCCESS') return 'var(--accent-success)';
        if (status === 'FAILED') return 'var(--accent-danger)';
        return 'var(--text-muted)';
    };

    const getStepIcon = (step: string): string => {
        if (step.includes('PREFLIGHT')) return '🔍';
        if (step.includes('CONFIRM')) return '✅';
        if (step.includes('EXECUTE')) return '⚡';
        if (step.includes('BUNDLE')) return '📦';
        return '📋';
    };

    if (intentEvents.length === 0) {
        return (
            <div className="alert info">
                < span className="small" > No execution events recorded for this intent.</span >
            </div >
        );
    }

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h4>📈 Execution Trace</h4>
                {finalStatus && (
                    <span
                        className="badge"
                        style={{
                            background: getStatusColor(finalStatus),
                            color: 'white',
                            fontWeight: 600,
                            padding: '0.5rem 1rem'
                        }}
                    >
                        {finalStatus}
                    </span>
                )}
            </div>

            {/* Timeline */}
            <div style={{ position: 'relative', paddingLeft: '2rem' }}>
                {/* Vertical Line */}
                <div style={{
                    position: 'absolute',
                    left: '0.75rem',
                    top: '0.5rem',
                    bottom: '0.5rem',
                    width: '2px',
                    background: 'var(--border-color)'
                }} />

                {/* Events */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {intentEvents.map((event, idx) => (
                        <div key={event.event_id} style={{ position: 'relative' }}>
                            {/* Timeline Dot */}
                            <div style={{
                                position: 'absolute',
                                left: '-1.25rem',
                                top: '0.5rem',
                                width: '10px',
                                height: '10px',
                                borderRadius: '50%',
                                background: getStatusColor(event.status),
                                border: '2px solid var(--surface)'
                            }} />

                            {/* Event Card */}
                            <div style={{
                                background: 'var(--surface-secondary)',
                                border: '1px solid var(--border-color)',
                                borderRadius: '6px',
                                padding: '0.75rem',
                                transition: 'all 0.2s ease'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <span style={{ fontSize: '1.25rem' }}>{getStepIcon(event.step)}</span>
                                        <div>
                                            <div style={{ fontWeight: 500 }}>{event.step.replace(/_/g, ' ')}</div>
                                            {event.endpoint && (
                                                <div className="tiny muted">
                                                    <code>{event.method} {event.endpoint}</code>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    <div style={{ textAlign: 'right' }}>
                                        <div className="tiny muted">{new Date(event.ts_ms).toLocaleTimeString()}</div>
                                        {event.latency_ms && (
                                            <div className="tiny" style={{ color: 'var(--accent-info)' }}>
                                                {event.latency_ms}ms
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Details */}
                                {(event.request_id || event.payload_hash || event.notes) && (
                                    <div style={{
                                        display: 'grid',
                                        gridTemplateColumns: 'auto 1fr',
                                        gap: '0.25rem 0.75rem',
                                        fontSize: '0.75rem',
                                        paddingTop: '0.5rem',
                                        borderTop: '1px solid var(--border-color)'
                                    }}>
                                        {event.request_id && (
                                            <>
                                                <span className="muted">request_id:</span>
                                                <code>{event.request_id}</code>
                                            </>
                                        )}
                                        {event.payload_hash && (
                                            <>
                                                <span className="muted">payload_hash:</span>
                                                <code>{event.payload_hash.slice(0, 16)}...</code>
                                            </>
                                        )}
                                        {event.notes && (
                                            <>
                                                <span className="muted">notes:</span>
                                                <span>{event.notes}</span>
                                            </>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Undo Generator (Mock) */}
            {finalStatus === 'SUCCESS' && (
                <div style={{ marginTop: '1rem', textAlign: 'center' }}>
                    <button
                        className="button ghost small"
                        onClick={() => console.log('[Forensic] Generate undo intent')}
                        title="Generate reversing intent (non-automatic)"
                    >
                        🔄 Generate Undo Intent
                    </button>
                </div>
            )}
        </div>
    );
};
