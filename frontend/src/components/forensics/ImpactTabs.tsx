import React, { useState } from 'react';

interface ImpactTabsProps {
    actionType: string;
    stateBefore: any;
    stateAfter: any;
}

/**
 * IMPACT TABS (ZONE 1)
 * 
 * Displays evidence about what the action will do:
 * - State Diff
 * - Risk Impact
 * - Entry/Exit Plan
 * - Dependency Map
 * - Raw Audit Preview
 */
export const ImpactTabs: React.FC<ImpactTabsProps> = ({ actionType, stateBefore, stateAfter }) => {
    const [activeTab, setActiveTab] = useState<'diff' | 'risk' | 'plan' | 'deps' | 'raw'>('diff');

    const tabs = [
        { id: 'diff', label: '📊 State Diff', icon: '📊' },
        { id: 'risk', label: '⚠️ Risk Impact', icon: '⚠️' },
        { id: 'plan', label: '🗺️ Entry/Exit Plan', icon: '🗺️' },
        { id: 'deps', label: '🔗 Dependencies', icon: '🔗' },
        { id: 'raw', label: '📄 Raw Audit', icon: '📄' }
    ];

    return (
        <div>
            {/* Tab Buttons */}
            <div style={{
                display: 'flex',
                gap: '0.5rem',
                borderBottom: '1px solid var(--border-color)',
                marginBottom: '1rem',
                overflowX: 'auto'
            }}>
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        className={`button ghost small ${activeTab === tab.id ? '' : ''}`}
                        onClick={() => setActiveTab(tab.id as any)}
                        style={{
                            borderBottom: activeTab === tab.id ? '2px solid var(--accent-primary)' : '2px solid transparent',
                            borderRadius: 0,
                            opacity: activeTab === tab.id ? 1 : 0.6,
                            fontWeight: activeTab === tab.id ? 600 : 400,
                            transition: 'all 0.2s ease'
                        }}
                    >
                        <span style={{ marginRight: '0.25rem' }}>{tab.icon}</span>
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div style={{ minHeight: '200px' }}>
                {activeTab === 'diff' && (
                    <div>
                        <h5 style={{ marginBottom: '1rem' }}>State Changes</h5>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            {/* Before */}
                            <div>
                                <div className="small muted" style={{ marginBottom: '0.5rem' }}>BEFORE</div>
                                <pre style={{
                                    background: 'var(--surface-secondary)',
                                    padding: '0.75rem',
                                    borderRadius: '6px',
                                    fontSize: '0.75rem',
                                    overflow: 'auto',
                                    maxHeight: '200px',
                                    border: '1px solid var(--border-color)'
                                }}>
                                    {JSON.stringify(stateBefore || { mode: 'MANUAL', auto_mode: false }, null, 2)}
                                </pre>
                            </div>

                            {/* After */}
                            <div>
                                <div className="small muted" style={{ marginBottom: '0.5rem' }}>AFTER</div>
                                <pre style={{
                                    background: 'var(--surface-secondary)',
                                    padding: '0.75rem',
                                    borderRadius: '6px',
                                    fontSize: '0.75rem',
                                    overflow: 'auto',
                                    maxHeight: '200px',
                                    border: '1px solid var(--accent-primary)'
                                }}>
                                    {JSON.stringify(stateAfter || { mode: 'AUTO', auto_mode: true }, null, 2)}
                                </pre>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'risk' && (
                    <div>
                        <h5 style={{ marginBottom: '1rem' }}>Risk Impact Analysis</h5>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            <div className="alert info">
                                <strong>Execution Authority:</strong>
                                <p className="small">Granting AUTO mode enables autonomous trade execution within configured risk limits.</p>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem' }}>
                                <div style={{ textAlign: 'center', padding: '1rem', background: 'var(--surface-secondary)', borderRadius: '6px' }}>
                                    <div className="small muted">Max Exposure</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>$125K</div>
                                </div>
                                <div style={{ textAlign: 'center', padding: '1rem', background: 'var(--surface-secondary)', borderRadius: '6px' }}>
                                    <div className="small muted">Estimated Freq.</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>~15/hr</div>
                                </div>
                                <div style={{ textAlign: 'center', padding: '1rem', background: 'var(--surface-secondary)', borderRadius: '6px' }}>
                                    <div className="small muted">Risk Score</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--accent-warning)' }}>MEDIUM</div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'plan' && (
                    <div>
                        <h5 style={{ marginBottom: '1rem' }}>Entry & Exit Plan</h5>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            <div>
                                <div className="small muted" style={{ marginBottom: '0.5rem' }}>📥 ENTRY CONDITIONS</div>
                                <ul style={{ paddingLeft: '1.5rem', margin: 0 }}>
                                    <li>All preflight checks PASS</li>
                                    <li>Operator present and authenticated</li>
                                    <li>Risk limits configured and verified</li>
                                </ul>
                            </div>
                            <div>
                                <div className="small muted" style={{ marginBottom: '0.5rem' }}>📤 EXIT TRIGGERS (Auto-Downgrade)</div>
                                <ul style={{ paddingLeft: '1.5rem', margin: 0 }}>
                                    <li>Hard drift detected (&gt;10% allocation deviation)</li>
                                    <li>Risk engine becomes unavailable</li>
                                    <li>Manual STOP command issued</li>
                                    <li>Daily loss limit exceeded</li>
                                </ul>
                            </div>
                            <div>
                                <div className="small muted" style={{ marginBottom: '0.5rem' }}>🔄 REVERSION METHOD</div>
                                <p className="small">Automatic downgrade to MANUAL mode + position freeze + operator notification</p>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'deps' && (
                    <div>
                        <h5 style={{ marginBottom: '1rem' }}>Dependency Map</h5>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            <div className="alert info small">
                                Components that will be affected by this action:
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                <span className="badge">Strategy Engine</span>
                                <span className="badge">Risk Monitor</span>
                                <span className="badge">Order Router</span>
                                <span className="badge">Position Manager</span>
                                <span className="badge">Audit Logger</span>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'raw' && (
                    <div>
                        <h5 style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>Raw Audit Payload</span>
                            <button
                                className="button ghost small"
                                onClick={() => {
                                    const payload = {
                                        action_type: actionType,
                                        state_before: stateBefore,
                                        state_after: stateAfter,
                                        timestamp: new Date().toISOString()
                                    };
                                    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
                                }}
                            >
                                📋 Copy
                            </button>
                        </h5>
                        <pre style={{
                            background: 'var(--surface-secondary)',
                            padding: '1rem',
                            borderRadius: '6px',
                            fontSize: '0.75rem',
                            overflow: 'auto',
                            maxHeight: '300px',
                            border: '1px solid var(--border-color)'
                        }}>
                            {JSON.stringify({
                                action_type: actionType,
                                state_before: stateBefore || { mode: 'MANUAL', auto_mode: false },
                                state_after: stateAfter || { mode: 'AUTO', auto_mode: true },
                                timestamp: new Date().toISOString(),
                                operator_notes: '(to be added at confirmation)'
                            }, null, 2)}
                        </pre>
                    </div>
                )}
            </div>
        </div>
    );
};
