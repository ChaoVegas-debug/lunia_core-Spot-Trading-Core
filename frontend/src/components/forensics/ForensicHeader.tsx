import React from 'react';
import { ClientIntentMetadata, ForensicSessionMetadata, AnomalyFlag } from '../../hooks/useForensicSession';
import { getIntentTimeRemaining } from '../../hooks/useForensicSession';

interface ForensicHeaderProps {
    session: ForensicSessionMetadata;
    intent?: ClientIntentMetadata;
    anomalies?: AnomalyFlag[];
}

/**
 * FORENSIC HEADER COMPONENT (ZONE 0)
 * 
 * Displays:
 * - forensic_session_id
 * - client_intent_id
 * - Severity badge
 * - TTL countdown
 * - Anomaly badges
 */
export const ForensicHeader: React.FC<ForensicHeaderProps> = ({ session, intent, anomalies = [] }) => {
    const [timeRemaining, setTimeRemaining] = React.useState(0);

    // Update TTL countdown
    React.useEffect(() => {
        if (!intent) return;

        const updateTimer = () => {
            const remaining = getIntentTimeRemaining(intent);
            setTimeRemaining(remaining);
        };

        updateTimer();
        const interval = setInterval(updateTimer, 1000);
        return () => clearInterval(interval);
    }, [intent]);

    const formatTime = (ms: number): string => {
        const totalSeconds = Math.floor(ms / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    };

    const getSeverityColor = (severity: string): string => {
        switch (severity) {
            case 'CRITICAL': return 'var(--accent-danger)';
            case 'HIGH': return 'var(--accent-warning)';
            case 'MEDIUM': return 'var(--accent-info)';
            default: return 'var(--text-muted)';
        }
    };

    const getAnomalyIcon = (type: string): string => {
        switch (type) {
            case 'UNUSUAL_TIME': return '🕒';
            case 'GEO_MISMATCH': return '🌍';
            case 'HIGH_VELOCITY': return '⚡';
            case 'DEVICE_CHANGE': return '🧩';
            default: return '⚠️';
        }
    };

    const ttlPercent = intent ? ((timeRemaining / intent.ttl_ms) * 100) : 100;

    return (
        <div style={{
            background: 'var(--surface-secondary)',
            border: `1px solid ${intent ? getSeverityColor(intent.severity) : 'var(--border-color)'}`,
            borderRadius: '6px',
            padding: '1rem',
            marginBottom: '1rem'
        }}>
            {/* IDs Row */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
                {/* Session ID */}
                <div style={{ flex: 1, minWidth: '200px' }}>
                    <div className="small muted" style={{ marginBottom: '0.25rem' }}>Forensic Session</div>
                    <code style={{
                        fontSize: '0.75rem',
                        background: 'var(--surface-tertiary)',
                        padding: '0.25rem 0.5rem',
                        borderRadius: '4px',
                        display: 'inline-block',
                        fontFamily: 'monospace'
                    }}>
                        {session.forensic_session_id.slice(0, 18)}...
                    </code>
                </div>

                {/* Intent ID */}
                {intent && (
                    <div style={{ flex: 1, minWidth: '200px' }}>
                        <div className="small muted" style={{ marginBottom: '0.25rem' }}>Client Intent</div>
                        <code style={{
                            fontSize: '0.75rem',
                            background: 'var(--surface-tertiary)',
                            padding: '0.25rem 0.5rem',
                            borderRadius: '4px',
                            display: 'inline-block',
                            fontFamily: 'monospace'
                        }}>
                            {intent.client_intent_id.slice(0, 18)}...
                        </code>
                    </div>
                )}

                {/* Severity Badge */}
                {intent && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div className="small muted">Severity</div>
                        <span
                            className="badge"
                            style={{
                                background: getSeverityColor(intent.severity),
                                color: 'white',
                                fontWeight: 600,
                                padding: '0.25rem 0.75rem'
                            }}
                        >
                            {intent.severity}
                        </span>
                    </div>
                )}
            </div>

            {/* TTL Progress Bar */}
            {intent && (
                <div style={{ marginBottom: '0.75rem' }}>
                    <div className="flex-between small muted" style={{ marginBottom: '0.25rem' }}>
                        <span>Intent Validity</span>
                        <span>{formatTime(timeRemaining)} remaining</span>
                    </div>
                    <div style={{
                        background: 'var(--surface-tertiary)',
                        height: '6px',
                        borderRadius: '3px',
                        overflow: 'hidden'
                    }}>
                        <div style={{
                            background: ttlPercent > 20 ? 'var(--accent-success)' : 'var(--accent-danger)',
                            height: '100%',
                            width: `${ttlPercent}%`,
                            transition: 'width 0.3s ease'
                        }} />
                    </div>
                </div>
            )}

            {/* Anomaly Badges */}
            {anomalies.length > 0 && (
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {anomalies.map((anomaly, idx) => (
                        <div
                            key={idx}
                            className="badge"
                            style={{
                                background: anomaly.severity === 'CRITICAL' ? 'var(--accent-danger)' :
                                    anomaly.severity === 'WARNING' ? 'var(--accent-warning)' :
                                        'var(--accent-info)',
                                color: 'white',
                                fontSize: '0.75rem',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.25rem',
                                padding: '0.25rem 0.5rem'
                            }}
                            title={anomaly.message}
                        >
                            <span>{getAnomalyIcon(anomaly.type)}</span>
                            <span>{anomaly.type.replace(/_/g, ' ')}</span>
                        </div>
                    ))}
                </div>
            )}

            {/* Verify Integrity Button (future) */}
            {intent && (
                <div style={{ marginTop: '0.75rem', textAlign: 'right' }}>
                    <button
                        className="button ghost small"
                        onClick={() => console.log('[Forensic] Verify integrity requested')}
                        title="Verify chain-of-custody integrity"
                    >
                        🔒 Verify Integrity Chain
                    </button>
                </div>
            )}
        </div>
    );
};
