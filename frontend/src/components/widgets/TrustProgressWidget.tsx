import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePreview } from '../../hooks/usePreview';

export const TrustProgressWidget: React.FC = () => {
    const auth = useAuth();
    const { isPreview, previewStore } = usePreview();

    // Determine Tier and Stats
    // In Preview, we might want to let the operator "See" what it looks like as different tiers?
    // For now, adhere to auth.user.tier or fallback
    const tier = auth.role === 'ADMIN' ? 'INSTITUTIONAL (Admin Override)' :
        auth.user?.tier || 'STD_RETAIL';

    // Logic for Progression
    const isInst = tier.includes('INST') || auth.role === 'ADMIN';
    const isAdv = tier === 'ADV_RETAIL';

    let trustScore = 50;
    let nextLevel = 'ADVANCED RETAIL';
    let progress = 0.5;

    if (isInst) {
        trustScore = 100;
        nextLevel = 'MAXIMUM AUTHORITY';
        progress = 1.0;
    } else if (isAdv) {
        trustScore = 80;
        nextLevel = 'INSTITUTIONAL LITE';
        progress = 0.8;
    }

    // CAPABILITY MATRIX (Phase 6.2)
    // Rows: Capabilities
    // Cols: Tiers (Implied by status)
    const capabilities = [
        { name: 'Manual Spot Trading', req: 'BEGINNER', status: 'UNLOCKED' },
        { name: 'Basic Algo Strategies', req: 'STD_RETAIL', status: tier === 'BEGINNER' ? 'LOCKED' : 'UNLOCKED' },
        { name: 'Market Making Bots', req: 'ADV_RETAIL', status: (isAdv || isInst) ? 'UNLOCKED' : 'LOCKED' },
        { name: 'Arbitrage Engine', req: 'INST_LITE', status: isInst ? 'UNLOCKED' : 'LOCKED' },
        { name: 'Dark Pool Access', req: 'INST_LITE', status: isInst ? 'UNLOCKED' : 'LOCKED' },
        { name: 'Leverage > 5x', req: 'INST_LITE', status: isInst ? 'UNLOCKED' : 'LOCKED' }
    ];

    // TIMELINE EVENTS (Phase 6.1)
    // Mix of static milestones and dynamic events from PreviewStore if available
    const timelineEvents = [
        { time: '2025-12-19 14:00', title: 'Onboarding Completed', type: 'MILESTONE' },
        { time: '2025-12-19 14:15', title: 'Risk Parameters Acknowledged', type: 'MILESTONE' },
        ...(isPreview ? previewStore.getState().audit_log
            .filter(e => e.type === 'MODE_CHANGE' || e.type === 'VETO' || e.type === 'DEPLOY')
            .slice(0, 3)
            .map(e => ({
                time: new Date(e.timestamp).toLocaleString(),
                title: `[SIM] ${e.message}`,
                type: 'SIMULATION'
            }))
            : []
        )
    ];

    // BLOCKERS (Why locked)
    const blockers = [];
    if (!isInst) {
        if (trustScore < 90) blockers.push("Trust Score < 90");
        if (!auth.opsToken) blockers.push("Missing Institutional Setup");
    }

    return (
        <div className="card trust-widget" style={{
            background: 'linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-deep) 100%)',
            border: '1px solid var(--border-color)'
        }}>
            <div className="card-header flex-between">
                <div>
                    <h3>Operator Trust & Integrity</h3>
                    <div className="tiny font-mono muted">ID: {(auth.user?.email || 'Unknown').split('@')[0].toUpperCase()}</div>
                </div>
                {isPreview && <span className="badge warning">PREVIEW SIMULATION</span>}
            </div>

            <div className="card-body">
                {/* HUD */}
                <div className="flex-between" style={{ alignItems: 'flex-end', marginBottom: '12px' }}>
                    <div>
                        <div className="muted small uppercase mb-1">Current Tier</div>
                        <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--expert-color)' }}>
                            {tier}
                        </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                        <div className="muted small uppercase mb-1">Trust Score</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--accent-primary)' }}>
                            {trustScore}<span className="small muted">/100</span>
                        </div>
                    </div>
                </div>

                {/* PROGRESS BAR */}
                <div className="progress-container" style={{ marginBottom: '24px' }}>
                    <div className="flex-between tiny muted mb-1">
                        <span>Current Authority</span>
                        <span>Next: {nextLevel}</span>
                    </div>
                    <div style={{
                        height: '6px',
                        background: 'rgba(255,255,255,0.1)',
                        borderRadius: '3px',
                        overflow: 'hidden'
                    }}>
                        <div style={{
                            width: `${progress * 100}%`,
                            background: 'var(--gradient-primary)',
                            height: '100%',
                            boxShadow: '0 0 10px var(--accent-primary)'
                        }} />
                    </div>
                </div>

                <div className="layout-split" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>

                    {/* LEFT: CAPABILITY MATRIX & UNLOCKS */}
                    <div>
                        <div className="small simple-header mb-3 uppercase tracking-widest text-secondary">Capability Matrix</div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {capabilities.map((u, i) => (
                                <div key={i} className="flex-between p-2 rounded" style={{
                                    background: u.status === 'UNLOCKED' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255,255,255,0.03)',
                                    border: u.status === 'UNLOCKED' ? '1px solid var(--accent-success)' : '1px solid transparent',
                                    opacity: u.status === 'LOCKED' ? 0.6 : 1,
                                    padding: '0.5rem',
                                    borderRadius: '4px'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <span>{u.status === 'UNLOCKED' ? '🔓' : '🔒'}</span>
                                        <div>
                                            <div className="small font-bold">{u.name}</div>
                                            {u.status === 'LOCKED' && <div className="tiny muted">Requires {u.req}</div>}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* WHY LOCKED */}
                        {blockers.length > 0 && (
                            <div className="mt-4 p-2" style={{ background: 'rgba(245, 158, 11, 0.1)', borderRadius: '4px', marginTop: '1rem' }}>
                                <div className="tiny font-bold uppercase text-warn mb-1">Why Next Level is Locked:</div>
                                <ul className="tiny muted" style={{ margin: 0, paddingLeft: '1.2rem' }}>
                                    {blockers.map((b, i) => <li key={i}>{b}</li>)}
                                </ul>
                            </div>
                        )}
                    </div>

                    {/* RIGHT: TIMELINE */}
                    <div>
                        <div className="small simple-header mb-3 uppercase tracking-widest text-secondary">Trust Timeline</div>
                        <div className="timeline-feed" style={{ borderLeft: '2px solid var(--border-color)', paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            {timelineEvents.map((evt, i) => (
                                <div key={i} className="timeline-item">
                                    <div className="tiny muted mb-1">{evt.time}</div>
                                    <div className="small" style={{ color: evt.type === 'SIMULATION' ? 'var(--accent-warning)' : 'inherit' }}>
                                        {evt.title}
                                    </div>
                                </div>
                            ))}
                            <div className="timeline-item opacity-50">
                                <div className="tiny muted mb-1">Pending</div>
                                <div className="small">Continue consistent trading activity...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
