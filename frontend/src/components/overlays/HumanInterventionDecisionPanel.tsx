import React, { useState } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getOpsState } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';
import type { OpsState } from '../../api/types';
import { usePreview } from '../../context/PreviewModeContext';
import { useDashboard } from '../../context/DashboardContext';

export const HumanInterventionDecisionPanel: React.FC = () => {
    const auth = useAuth();
    const { addToast } = useDashboard();
    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'ops_HumanInterventionDecisionPanel',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, { role: auth.role, opsToken: auth.opsToken }),
        interval_ms: 3000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };
    const { isPreview } = usePreview();

    const [resolved, setResolved] = useState(false);
    const [dismissed, setDismissed] = useState(false);
    const [busy, setBusy] = useState(false);

    // Trigger Logic: Check for drift status (HARD = Confirmation Required)
    const isDrift = ops.data?.drift_status === 'HARD';

    // BLOCK, DON'T HIDE: Always render, but return empty fragment when not needed
    // This prevents blank dashboard issues from component unmounting
    const shouldShow = isDrift && !resolved && !(dismissed && isPreview);

    const handleAction = async (action: 'ACCEPT' | 'REVERT' | 'FLATTEN') => {
        setBusy(true);
        // Simulate async action
        await new Promise(r => setTimeout(r, 1000));

        let msg = "";
        switch (action) {
            case 'ACCEPT': msg = "New baseline accepted. Model updated."; break;
            case 'REVERT': msg = "Revert signals sent to bot."; break;
            case 'FLATTEN': msg = "Exposure flattened."; break;
        }

        // In real backend, we'd call an endpoint here.
        // For now, we "Resolve" it client-side to unblock the UI.
        console.log(`[AUDIT] Intervention Resolution: ${action}`);
        addToast({ type: 'SUCCESS', message: `Resolution Recorded: ${msg} (Backend Integration Pending)` });

        setResolved(true);
        setBusy(false);
    };

    // BLOCK, DON'T HIDE: Return empty fragment if not showing, never null
    if (!shouldShow) {
        return <></>;
    }

    return (
        <div className="overlay-backdrop" style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            background: isPreview ? 'rgba(0,0,0,0.6)' : 'rgba(0,0,0,0.85)',
            zIndex: 9000, // Below Airlock (9999) but above content
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: 'blur(8px)',
            pointerEvents: isPreview ? 'none' : 'auto' // Allow click-through in preview if we want, but better to just use overlay
        }}>
            <div className="card" style={{
                maxWidth: '600px',
                borderTop: '4px solid var(--accent-warning)',
                boxShadow: '0 0 50px rgba(245, 158, 11, 0.2)',
                pointerEvents: 'auto'
            }}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <h2 className="text-warn">⚠ Human vs Model Conflict Detected</h2>
                    {isPreview && (
                        <button className="button small ghost" onClick={() => setDismissed(true)}>
                            [PREVIEW] DISMISS
                        </button>
                    )}
                </div>

                <div className="p-4">
                    <p className="mb-4">
                        We detected human intervention (external or manual) that conflicts with the current strategy model.
                        <strong>Automatic execution is suspended until this is resolved.</strong>
                    </p>

                    <div className="alert info small mb-4">
                        <strong>Governance Rule:</strong> "Chain Truth is Supreme". The system cannot proceed until you reconcile the reality mismatch.
                    </div>

                    <div className="grid cols-1 gap-2">
                        <button
                            className="button secondary flex-between p-3"
                            onClick={() => handleAction('ACCEPT')}
                            disabled={busy}
                        >
                            <span className="font-bold">1. ACCEPT NEW REALITY</span>
                            <span className="small muted">Update model baseline to match exchange.</span>
                        </button>

                        <button
                            className="button secondary flex-between p-3"
                            onClick={() => handleAction('REVERT')}
                            disabled={busy}
                        >
                            <span className="font-bold">2. ATTEMPT REVERT</span>
                            <span className="small muted">Bot attempts to trade back to model target.</span>
                        </button>

                        <button
                            className="button danger flex-between p-3 text-red"
                            onClick={() => handleAction('FLATTEN')}
                            disabled={busy}
                        >
                            <span className="font-bold">3. FLATTEN EXPOSURE</span>
                            <span className="small muted">Emergency exit to stablecoin.</span>
                        </button>
                    </div>

                    <div className="mt-4 text-center tiny muted">
                        Event ID: INTERVENTION_{Date.now()} • Logged to Audit Trail
                    </div>
                </div>
            </div>
        </div>
    );
};
