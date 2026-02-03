import React from 'react';
import type { OpsState } from '../../api/types';

interface StartConfirmationModalProps {
    isOpen: boolean;
    onCancel: () => void;
    onConfirm: (mode: 'dry' | 'real') => void;
    ops: OpsState | null;
    loading?: boolean;
}

export const StartConfirmationModal: React.FC<StartConfirmationModalProps> = ({
    isOpen,
    onCancel,
    onConfirm,
    ops,
    loading = false
}) => {
    if (!isOpen) return null;

    const globalStop = ops?.global_stop || false;
    // VARIANT A: Use system_mode for governance display, airlock for live gating
    const systemMode = ops?.system_mode || (ops?.auto_mode ? 'AUTO' : 'MANUAL');
    const airlockStatus = ops?.airlock_status || 'NOT_READY';
    const isBlocked = globalStop || airlockStatus === 'BLOCKED';

    // VARIANT A FIX: Live mode available if airlock is ARMED and not stopped
    // (run_mode will be 'real' when user clicks "Start LIVE" and backend confirms)
    const canGoLive = airlockStatus === 'ARMED' && !globalStop;

    return (
        <div className="modal-overlay" style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
            <div className="modal-content" style={{
                background: 'var(--bg-panel)', padding: '2rem', borderRadius: '12px',
                maxWidth: '480px', width: '90%', border: '1px solid var(--border-color)'
            }}>
                <h2 style={{ margin: 0, marginBottom: '1rem', color: 'var(--color-primary)' }}>
                    🚀 START Trading Pipeline
                </h2>

                {/* Gates Summary */}
                <div style={{ marginBottom: '1.5rem' }}>
                    <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        GOVERNANCE GATES
                    </div>
                    <div style={{ display: 'grid', gap: '0.5rem' }}>
                        <GateRow label="Global Stop" value={globalStop ? 'ACTIVE' : 'CLEAR'} ok={!globalStop} />
                        <GateRow label="System Mode" value={systemMode} ok={systemMode !== 'STOP'} />
                        <GateRow label="Airlock" value={airlockStatus} ok={airlockStatus === 'ARMED'} />
                    </div>
                </div>

                {/* Blocked Warning */}
                {isBlocked && (
                    <div style={{
                        background: 'rgba(255,0,0,0.1)', border: '1px solid var(--color-danger)',
                        padding: '0.75rem', borderRadius: '6px', marginBottom: '1rem'
                    }}>
                        <strong style={{ color: 'var(--color-danger)' }}>⚠ START BLOCKED</strong>
                        <p style={{ margin: '0.5rem 0 0', fontSize: '13px' }}>
                            {globalStop ? 'System is halted by Global Stop.' : 'Airlock security is active.'}
                        </p>
                    </div>
                )}

                {/* Mode Description */}
                {!isBlocked && (
                    <div style={{ marginBottom: '1.5rem', fontSize: '13px', color: 'var(--text-secondary)' }}>
                        <p style={{ margin: 0 }}>
                            <strong>DRY Mode:</strong> Signals generated, no real orders placed.
                        </p>
                        {canGoLive && (
                            <p style={{ margin: '0.5rem 0 0', color: 'var(--color-warning)' }}>
                                <strong>LIVE Mode:</strong> Real orders will be transmitted to exchanges!
                            </p>
                        )}
                    </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                    <button className="button ghost" onClick={onCancel} disabled={loading}>
                        Cancel
                    </button>

                    {!isBlocked && (
                        <>
                            <button
                                className="button primary"
                                onClick={() => onConfirm('dry')}
                                disabled={loading}
                            >
                                {loading ? 'Starting...' : 'Start DRY'}
                            </button>

                            {canGoLive && (
                                <button
                                    className="button danger"
                                    onClick={() => onConfirm('real')}
                                    disabled={loading}
                                >
                                    Start LIVE ⚡
                                </button>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};

const GateRow: React.FC<{ label: string; value: string; ok: boolean }> = ({ label, value, ok }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
        <span style={{ color: 'var(--text-muted)' }}>{label}</span>
        <span style={{
            color: ok ? 'var(--color-success)' : 'var(--color-danger)',
            fontWeight: 'bold'
        }}>
            {ok ? '✓' : '✗'} {value}
        </span>
    </div>
);
