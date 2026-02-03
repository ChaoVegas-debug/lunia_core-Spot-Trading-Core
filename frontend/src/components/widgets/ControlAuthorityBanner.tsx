import React, { useEffect, useState } from 'react';
import { getOpsState } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import type { OpsState } from '../../api/types';

export const ControlAuthorityBanner: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };
    const { data: opsData } = usePoller<OpsState>({
        key: 'control_authority_ops',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 2000,
        critical: true  // Core system health
    });
    const ops = { data: opsData };

    const [autoStartTime, setAutoStartTime] = useState<number | null>(null);
    const [elapsed, setElapsed] = useState<string>('');

    // Timer logic for Auto Mode
    useEffect(() => {
        if (ops.data?.auto_mode) {
            // If we don't have a start time tracked locally, set it now (approximate)
            // Or ideally, the backend would provide 'auto_enabled_at'. 
            // For now, checks localStorage to persist across refreshes
            const stored = localStorage.getItem('auto_start_ts');
            if (stored) {
                setAutoStartTime(parseInt(stored, 10));
            } else {
                const now = Date.now();
                localStorage.setItem('auto_start_ts', now.toString());
                setAutoStartTime(now);
            }
        } else {
            localStorage.removeItem('auto_start_ts');
            setAutoStartTime(null);
            setElapsed('');
        }
    }, [ops.data?.auto_mode]);

    useEffect(() => {
        if (!autoStartTime) return;

        const interval = setInterval(() => {
            const diff = Math.floor((Date.now() - autoStartTime) / 1000);
            const h = Math.floor(diff / 3600).toString().padStart(2, '0');
            const m = Math.floor((diff % 3600) / 60).toString().padStart(2, '0');
            const s = (diff % 60).toString().padStart(2, '0');
            setElapsed(`${h}:${m}:${s}`);
        }, 1000);

        return () => clearInterval(interval);
    }, [autoStartTime]);

    const isGlobalStop = ops.data?.global_stop;
    const isAuto = ops.data?.auto_mode;
    const vetoReason = ops.data?.veto_reason;

    // Styles
    const containerStyle: React.CSSProperties = {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '1rem',
        marginBottom: '1rem',
        borderRadius: '4px',
        border: '1px solid',
        backgroundColor: 'var(--bg-panel)', // fallback
        color: '#fff',
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        transition: 'all 0.3s ease'
    };

    if (isGlobalStop) {
        Object.assign(containerStyle, {
            borderColor: '#ff4444',
            backgroundColor: 'rgba(50, 0, 0, 0.9)',
            boxShadow: '0 0 15px rgba(255, 68, 68, 0.3)'
        });
    } else if (isAuto) {
        Object.assign(containerStyle, {
            borderColor: '#00ccff',
            backgroundColor: 'rgba(0, 20, 40, 0.9)',
            boxShadow: '0 0 10px rgba(0, 204, 255, 0.2)'
        });
    } else {
        // Manual / Semi
        Object.assign(containerStyle, {
            borderColor: '#666',
            backgroundColor: 'var(--bg-panel)',
        });
    }

    return (
        <div style={containerStyle}>
            {/* LEFT: STATUS */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{
                    fontSize: '1.5rem',
                    fontWeight: 'bold',
                    textTransform: 'uppercase',
                    color: isGlobalStop ? '#ff4444' : (isAuto ? '#00ccff' : '#aaa')
                }}>
                    {isGlobalStop ? 'HARD STOP ACTIVE' : (isAuto ? 'AI AUTOPILOT' : 'MANUAL CONTROL')}
                </div>

                {isAuto && !isGlobalStop && (
                    <div style={{
                        fontFamily: 'monospace',
                        fontSize: '1.2rem',
                        color: '#00ccff',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: 'rgba(0, 204, 255, 0.1)'
                    }}>
                        T+{elapsed}
                    </div>
                )}
            </div>

            {/* RIGHT: DETAILS */}
            <div style={{ textAlign: 'right' }}>
                {isGlobalStop ? (
                    <div style={{ color: '#ffaaaa', maxWidth: '400px', fontSize: '0.9rem' }}>
                        <strong>REASON:</strong> {vetoReason || 'Emergency Stop Triggered'}
                    </div>
                ) : (
                    <div style={{ color: '#888', fontSize: '0.8rem', letterSpacing: '0.05em' }}>
                        AUTHORITY: {isAuto ? 'ALGORITHM' : 'HUMAN OPERATOR'}
                    </div>
                )}
            </div>
        </div>
    );
};
