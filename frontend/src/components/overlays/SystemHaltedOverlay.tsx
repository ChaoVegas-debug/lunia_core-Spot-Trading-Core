import React, { useState } from 'react';

interface SystemHaltedOverlayProps {
    reason?: string;
    isOffline?: boolean;
    blocking?: boolean; // If false (Preview Mode), allow clicking through and dismissing
}

export const SystemHaltedOverlay: React.FC<SystemHaltedOverlayProps> = ({ reason, isOffline, blocking = true }) => {
    const [dismissed, setDismissed] = useState(false);

    // If "soft blocking" (preview mode) and user dismissed it, show persistent footer banner
    if (!blocking && dismissed) {
        return (
            <div className="alert warning" style={{
                position: 'fixed',
                bottom: '24px',
                right: '24px',
                width: 'auto',
                zIndex: 998,
                maxWidth: '400px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                border: '1px solid var(--accent-warning)',
                pointerEvents: 'auto'
            }}>
                <div style={{ fontWeight: 'bold' }}>⚠️ {isOffline ? 'OFFLINE' : 'HALTED'} (Preview Mode)</div>
                <div className="small muted">Backend unavailable. Using simulated data.</div>
                <button
                    className="button text-only small"
                    style={{ marginTop: '0.5rem' }}
                    onClick={() => setDismissed(false)}
                >
                    SHOW FULL OVERLAY
                </button>
            </div>
        );
    }

    // Interactive container behavior:
    // If blocking=true, we catch all clicks (pointerEvents: all)
    // If blocking=false, we pass clicks through the backdrop (pointerEvents: none) 
    // BUT we must allow clicks on the card itself (pointerEvents: auto)

    return (
        <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: blocking ? 'rgba(10, 10, 15, 0.85)' : 'rgba(10, 10, 15, 0.6)',
            backdropFilter: 'blur(4px)',
            zIndex: 999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: blocking ? 'all' : 'none',
            flexDirection: 'column'
        }}>
            <div className="halt-card" style={{
                background: 'var(--bg-panel)',
                border: isOffline ? '2px solid var(--accent-warning)' : '2px solid var(--accent-danger)',
                padding: '2rem',
                borderRadius: '12px',
                maxWidth: '400px',
                textAlign: 'center',
                boxShadow: '0 0 30px rgba(0,0,0,0.5)',
                pointerEvents: 'auto' // Always allow clicking the card itself
            }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>
                    {isOffline ? '🔌' : '🛑'}
                </div>
                <h2 style={{
                    color: isOffline ? 'var(--accent-warning)' : 'var(--accent-danger)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    marginBottom: '1rem'
                }}>
                    {isOffline ? 'SYSTEM OFFLINE' : 'SYSTEM HALTED'}
                </h2>

                <p className="muted mb-4">
                    {reason || (isOffline
                        ? "Connection to the trading core has been lost."
                        : "Emergency Stop is active.")}
                </p>

                {/* Preview/Soft-Block Explanation */}
                {!blocking && (
                    <div className="alert info mb-4" style={{ textAlign: 'left' }}>
                        <strong>PREVIEW MODE ACTIVE</strong>
                        <div className="small">
                            You are in Operator Preview. Blocks are softened.
                            {isOffline
                                ? " Backend is unreachable => UI is SIMULATED."
                                : " Backend reports STOP => Inspect UI allowed."
                            }
                        </div>
                    </div>
                )}

                <div className="recovery-steps" style={{ textAlign: 'left', background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                    <strong>Status:</strong>
                    <ul className="pl-4 mt-2" style={{ listStyleType: 'disc', color: 'var(--text-secondary)' }}>
                        {isOffline ? (
                            <>
                                <li>Backend Unreachable</li>
                                <li>Retrying Connection...</li>
                            </>
                        ) : (
                            <>
                                <li>Execution Suspended</li>
                                <li>Investigate Logs</li>
                            </>
                        )}
                    </ul>
                </div>

                {!blocking && (
                    <button
                        className="button primary full-width mt-4"
                        onClick={() => setDismissed(true)}
                    >
                        DISMISS & INSPECT UI (PREVIEW)
                    </button>
                )}
            </div>
        </div>
    );
};

