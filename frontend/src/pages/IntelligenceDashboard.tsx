import React from 'react';
import { usePreview } from '../context/PreviewModeContext';

export const IntelligenceDashboard: React.FC = () => {
    const { state } = usePreview();
    const { intelligence } = state;

    if (!intelligence) return <div className="p-4">Loading Intelligence Core...</div>;

    return (
        <div className="intelligence-dashboard p-4">
            <header className="mb-6 flex-between">
                <div>
                    <h1 className="text-2xl font-bold mb-1">Intelligence Ecosystem</h1>
                    <p className="text-muted">Autonomous Optimization & Market Analysis</p>
                </div>
                <div className="flex-gap">
                    <div className="badge primary p-2 text-lg">
                        CONFIDENCE: {intelligence.confidence_score}%
                    </div>
                    <div className="badge warning p-2 text-lg">
                        REGIME: {intelligence.market_regime}
                    </div>
                </div>
            </header>

            <div className="grid cols-2 gap-4">
                {/* Panel 1: Active Insights */}
                <div className="card">
                    <div className="card-header">
                        <h3>Active Insights</h3>
                        <span className="small text-muted">Real-time Logic Streams</span>
                    </div>
                    <div className="insight-list">
                        {intelligence.active_insights.map(insight => (
                            <div key={insight.id} className="alert mb-2 flex-between" style={{
                                borderLeft: `4px solid ${insight.type === 'OPPORTUNITY' ? 'var(--accent-success)' : insight.type === 'RISK' ? 'var(--accent-danger)' : 'var(--accent-primary)'}`
                            }}>
                                <div>
                                    <div className="font-bold text-xs mb-1 opacity-75">{insight.type}</div>
                                    <div>{insight.message}</div>
                                </div>
                                <div className="text-right">
                                    <div className="text-xl font-mono">{(insight.confidence * 100).toFixed(0)}%</div>
                                    <div className="tiny muted">Prob</div>
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="mt-4 text-center">
                        <button className="button secondary full-width">View Full Reasoning Logs</button>
                    </div>
                </div>

                {/* Panel 2: System Optimization (Mock) */}
                <div className="card">
                    <div className="card-header">
                        <h3>Self-Optimization Cycles</h3>
                        <span className="tiny text-green">ACTIVE</span>
                    </div>
                    <div className="p-4 bg-panel-soft rounded min-h-[200px] font-mono text-xs">
                        <div className="mb-2 text-muted">Last Optimization: {new Date(intelligence.last_optimization).toLocaleString()}</div>
                        <div className="text-green mb-1">{'>'} Scanning 52 assets for liquidity islands... DONE</div>
                        <div className="text-green mb-1">{'>'} Analyzing volatility surface vs Model A... DONE</div>
                        <div className="text-warn mb-1">{'>'} Detected drift in SOL/USDT correlations (0.85 -&gt; 0.62)</div>
                        <div className="text-green mb-1">{'>'} Adjusting hedge ratios... PENDING</div>
                        <div className="text-muted mt-2 animated-cursor">_</div>
                    </div>
                </div>
            </div>
        </div>
    );
};
