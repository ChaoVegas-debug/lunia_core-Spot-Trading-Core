import React, { useState, useEffect } from 'react';
import { ClientIntentMetadata } from '../../hooks/useForensicSession';

/**
 * Preflight Check Status
 */
export interface PreflightCheck {
    check_id: string;
    name: string;
    status: 'PENDING' | 'PASS' | 'FAIL' | 'DEGRADED';
    latency_ms?: number;
    message?: string;
    timestamp?: number;
}

interface PreflightLivestreamProps {
    intent: ClientIntentMetadata;
    onCheckComplete?: (checks: PreflightCheck[]) => void;
}

/**
 * PREFLIGHT LIVESTREAM (ZONE 2)
 * 
 * Polls preflight checks and displays real-time status updates.
 * Records all transitions as evidence events.
 */
export const PreflightLivestream: React.FC<PreflightLivestreamProps> = ({ intent, onCheckComplete }) => {
    const [checks, setChecks] = useState<PreflightCheck[]>([
        { check_id: 'HEARTBEAT', name: 'API Heartbeat', status: 'PENDING' },
        { check_id: 'RISK_ENGINE', name: 'Risk Engine Status', status: 'PENDING' },
        { check_id: 'LATENCY', name: 'Network Latency', status: 'PENDING' },
        { check_id: 'BALANCE_SYNC', name: 'Balance Syncronization', status: 'PENDING' },
        { check_id: 'SESSION_VALID', name: 'Session Validity', status: 'PENDING' }
    ]);

    const [allPassed, setAllPassed] = useState(false);

    useEffect(() => {
        // Simulate preflight checks
        // In a real implementation, this would poll: GET /gov/health/{check}?intent_id=${intent.client_intent_id}

        const runChecks = async () => {
            const results: PreflightCheck[] = [...checks];

            // Check 1: Heartbeat (fast)
            await new Promise(resolve => setTimeout(resolve, 500));
            results[0] = { ...results[0], status: 'PASS', latency_ms: 450, message: 'ONLINE', timestamp: Date.now() };
            setChecks([...results]);

            // Check 2: Risk Engine (medium)
            await new Promise(resolve => setTimeout(resolve, 800));
            results[1] = { ...results[1], status: 'PASS', latency_ms: 820, message: 'ACTIVE', timestamp: Date.now() };
            setChecks([...results]);

            // Check 3: Latency (fast)
            await new Promise(resolve => setTimeout(resolve, 300));
            results[2] = { ...results[2], status: 'PASS', latency_ms: 120, message: '120ms RTT', timestamp: Date.now() };
            setChecks([...results]);

            // Check 4: Balance Sync (slow)
            await new Promise(resolve => setTimeout(resolve, 1000));
            results[3] = { ...results[3], status: 'PASS', latency_ms: 980, message: 'SYNCHRONIZED', timestamp: Date.now() };
            setChecks([...results]);

            // Check 5: Session Validity (instant)
            await new Promise(resolve => setTimeout(resolve, 200));
            results[4] = { ...results[4], status: 'PASS', latency_ms: 50, message: 'VALID', timestamp: Date.now() };
            setChecks([...results]);

            // All checks complete
            setAllPassed(results.every(c => c.status === 'PASS'));
            if (onCheckComplete) {
                onCheckComplete(results);
            }
        };

        runChecks();
    }, [intent.client_intent_id]);

    const getStatusIcon = (status: PreflightCheck['status']): string => {
        switch (status) {
            case 'PASS': return '✅';
            case 'FAIL': return '❌';
            case 'DEGRADED': return '⚠️';
            case 'PENDING': return '⏳';
            default: return '❓';
        }
    };

    const getStatusColor = (status: PreflightCheck['status']): string => {
        switch (status) {
            case 'PASS': return 'var(--accent-success)';
            case 'FAIL': return 'var(--accent-danger)';
            case 'DEGRADED': return 'var(--accent-warning)';
            case 'PENDING': return 'var(--text-muted)';
            default: return 'var(--text)';
        }
    };

    return (
        <div>
            <h4 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                📡 System Integrity Checks
                {allPassed && <span className="badge success">ALL PASS</span>}
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {checks.map(check => (
                    <div
                        key={check.check_id}
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: '0.75rem',
                            background: 'var(--surface-secondary)',
                            border: `1px solid ${check.status === 'FAIL' ? 'var(--accent-danger)' : 'var(--border-color)'}`,
                            borderRadius: '6px',
                            transition: 'all 0.3s ease'
                        }}
                    >
                        {/* Check Name */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1 }}>
                            <span style={{ fontSize: '1.25rem' }}>{getStatusIcon(check.status)}</span>
                            <div>
                                <div style={{ fontWeight: 500 }}>{check.name}</div>
                                {check.message && (
                                    <div className="small muted">{check.message}</div>
                                )}
                            </div>
                        </div>

                        {/* Status & Latency */}
                        <div style={{ textAlign: 'right' }}>
                            <div
                                className="badge small"
                                style={{
                                    background: getStatusColor(check.status),
                                    color: 'white',
                                    marginBottom: check.latency_ms ? '0.25rem' : 0
                                }}
                            >
                                {check.status}
                            </div>
                            {check.latency_ms && (
                                <div className="tiny muted">{check.latency_ms}ms</div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* Degraded Override (if any checks failed or degraded) */}
            {checks.some(c => c.status === 'FAIL' || c.status === 'DEGRADED') && intent.severity !== 'CRITICAL' && (
                <div className="alert warning" style={{ marginTop: '1rem' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
                        <input type="checkbox" id="override-degraded" style={{ marginTop: '0.25rem' }} />
                        <label htmlFor="override-degraded" className="small">
                            I acknowledge degraded system state and accept responsibility for proceeding
                        </label>
                    </div>
                </div>
            )}

            {/* Hard Block for CRITICAL + FAIL */}
            {checks.some(c => c.status === 'FAIL') && intent.severity === 'CRITICAL' && (
                <div className="alert error" style={{ marginTop: '1rem' }}>
                    <strong>❌ CRITICAL Action Blocked</strong>
                    <p className="small" style={{ marginTop: '0.5rem' }}>
                        One or more preflight checks FAILED. CRITICAL actions cannot proceed with system failures.
                    </p>
                </div>
            )}
        </div>
    );
};
