import React, { useState } from 'react';
import { usePreview } from '../../context/PreviewModeContext';
import { safeArray } from '../../utils/safe';
import { PREVIEW_BADGE_TEXT, PREVIEW_MODE } from '../../config/preview';

export const PreviewStatusBadge: React.FC = () => {
    const { isSimulation, simHealth, toggleSimulation, isPreview, state, actions } = usePreview();
    const [showDiag, setShowDiag] = useState(false);

    if (!isPreview) return null;

    const apiBase = import.meta.env.VITE_API_BASE_URL;
    const isOffline = !state.backend_reachable;

    const handleDriftToggle = (enabled: boolean) => {
        actions.triggerDrift(enabled ? 'HARD' : 'NONE');
    };

    const handleReset = () => {
        if (confirm("Reset Simulation State? This will reload the page.")) {
            window.location.reload();
        }
    };

    return (
        <>
            <div
                onClick={() => setShowDiag(true)}
                style={{
                    position: 'fixed',
                    top: '64px', // below navbar
                    right: '24px',
                    zIndex: 9999,
                    background: isSimulation ? 'rgba(255, 152, 0, 0.95)' : 'rgba(33, 150, 243, 0.95)',
                    color: 'white',
                    padding: '6px 16px',
                    borderRadius: '24px',
                    fontSize: '11px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                    backdropFilter: 'blur(8px)',
                    border: '1px solid rgba(255,255,255,0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                }}
            >
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: isOffline ? '#ff4d4d' : '#4caf50' }} />
                {PREVIEW_BADGE_TEXT} | {isSimulation ? 'SIMULATION' : 'LIVE'}
            </div>

            {showDiag && (
                <div className="modal-backdrop" style={{ zIndex: 10000 }}>
                    <div className="modal-content" style={{ width: '600px', maxHeight: '90vh', overflowY: 'auto' }}>
                        <div className="card-header">
                            <h3>Preview Diagnostics</h3>
                            <button className="button text-only" onClick={() => setShowDiag(false)}>×</button>
                        </div>
                        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            <div className={`alert ${isOffline ? 'warning' : 'success'}`}>
                                <strong>Backend Status:</strong> {isOffline ? 'OFFLINE (Unreachable)' : 'ONLINE (Connected)'}
                                {isOffline && <div className="small">Adapter automatically fell back to Simulation.</div>}
                            </div>

                            <div className="grid-2">
                                <div>
                                    <label className="small muted">API BASE</label>
                                    <div className="font-mono small">{apiBase}</div>
                                </div>
                                <div>
                                    <label className="small muted">MODE FLAG</label>
                                    <div className="font-mono small">{PREVIEW_MODE ? 'TRUE' : 'FALSE'}</div>
                                </div>
                            </div>

                            <div className="divider" />

                            <div className="flex-row justify-between align-center">
                                <div>
                                    <div className="label">Simulation Enabled</div>
                                    <div className="small muted">Allow fallback to mock data</div>
                                </div>
                                <label className="switch">
                                    <input type="checkbox" checked={isSimulation} onChange={toggleSimulation} />
                                    <span className="slider round"></span>
                                </label>
                            </div>

                            <div className="flex-row justify-between align-center">
                                <div>
                                    <div className="label">Force Simulation</div>
                                    <div className="small muted">Ignore real backend even if online</div>
                                </div>
                                <label className="switch">
                                    <input type="checkbox" checked={state.force_sim} onChange={(e) => actions.setForceSim(e.target.checked)} />
                                    <span className="slider round"></span>
                                </label>
                            </div>

                            <div className="flex-row justify-between align-center">
                                <div>
                                    <div className="label">Simulate Drift (Hard)</div>
                                    <div className="small muted">Triggers Intervention Flow</div>
                                </div>
                                <label className="switch">
                                    <input
                                        type="checkbox"
                                        checked={state.ops.drift_status === 'HARD'}
                                        onChange={(e) => handleDriftToggle(e.target.checked)}
                                    />
                                    <span className="slider round"></span>
                                </label>
                            </div>

                            <div className="bg-darker p-3 rounded font-mono small">
                                <div className="mb-2"><strong>Simulated State (In-Memory)</strong></div>
                                <div>Ops Mode: <span style={{ color: 'var(--accent-primary)' }}>{state.ops.exec_mode}</span></div>
                                <div>Health: <span style={{ color: '#4caf50' }}>{JSON.stringify(simHealth.status, null, 2)}</span></div>
                                <div>Users: {safeArray(state.users).length} | Strategies: {safeArray(state.strategies).length}</div>
                            </div>

                            <div className="divider" />

                            <strong>Event Log (Simulated)</strong>
                            <div className="bg-darker p-2 rounded font-mono small" style={{ height: '150px', overflowY: 'auto' }}>
                                {safeArray(state.audit_log).length === 0 && <div className="muted">No events yet.</div>}
                                {safeArray(state.audit_log).map(evt => (
                                    <div key={evt.id} style={{ marginBottom: '4px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '2px' }}>
                                        <span style={{ color: 'var(--text-muted)' }}>[{evt.timestamp.split('T')[1].split('.')[0]}]</span>{' '}
                                        <strong style={{ color: evt.severity === 'CRITICAL' ? 'red' : 'inherit' }}>{evt.type}</strong>:{' '}
                                        {evt.message}
                                    </div>
                                ))}
                            </div>

                            <div className="flex-row gap-2 mt-4">
                                <button className="button ghost full-width" onClick={handleReset}>RESET SIMULATION</button>
                                <button className="button primary full-width" onClick={() => setShowDiag(false)}>CLOSE</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
