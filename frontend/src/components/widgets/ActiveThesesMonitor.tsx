import React from 'react';

export const ActiveThesesMonitor: React.FC = () => {
    return (
        <div style={{
            padding: '2rem',
            background: '#0f172a',
            border: '1px solid #1e293b',
            borderRadius: '12px',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center'
        }}>
            <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1.5rem' }}>📊</div>
                <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.5rem', fontWeight: '700', color: '#f1f5f9' }}>
                    Active Theses (0)
                </h3>
                <div style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '2rem', maxWidth: '400px' }}>
                    Real-time thesis monitoring will appear here once proposals are approved and enter execution
                </div>

                <div style={{
                    padding: '1.5rem',
                    background: '#1e293b',
                    borderRadius: '8px',
                    border: '1px solid #334155',
                    textAlign: 'left',
                    marginBottom: '1.5rem'
                }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#cbd5e1', marginBottom: '1rem' }}>
                        EPOCH D: Biological Governance
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: '#94a3b8', lineHeight: '1.6', marginBottom: '1rem' }}>
                        This panel will display:
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.5rem', color: '#94a3b8', fontSize: '0.8125rem', lineHeight: '1.8' }}>
                        <li>Thesis Health timeline (cellular degradation tracking)</li>
                        <li>Watchdog status (Price / Time / Thesis monitors)</li>
                        <li>"What Changed Since Approve" delta analysis</li>
                        <li>Live vs. Expected performance comparison</li>
                        <li>Automatic thesis invalidation alerts</li>
                    </ul>
                </div>

                <div style={{
                    padding: '1rem',
                    background: 'rgba(139, 92, 246, 0.1)',
                    border: '1px solid #8b5cf6',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    color: '#c4b5fd'
                }}>
                    💡 Requires: Thesis Tracking Engine + Watchdog Infrastructure
                </div>
            </div>
        </div>
    );
};
