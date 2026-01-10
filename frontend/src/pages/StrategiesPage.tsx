import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { usePolledResource } from '../hooks/usePolledResource';
import {
    getStrategies,
    updateStrategies,
    setStrategyProfile,
    haltStrategies
} from '../api/adapter';
import type { StrategyConfig } from '../api/types';
import { useLocation } from 'react-router-dom';
import { StrategyPerformanceMetrics } from '../components/widgets/StrategyPerformanceMetrics';
import { usePreview } from '../hooks/usePreview';
import { useDashboard } from '../context/DashboardContext';
import { StrategyOrdersDrawer } from '../components/drawers/StrategyOrdersDrawer';
import { DuplicateStrategyModal } from '../components/modals/DuplicateStrategyModal';

export const StrategiesPage: React.FC = () => {
    const auth = useAuth();
    const location = useLocation() as { state: any };
    const { isPreview, previewStore } = usePreview();
    const { addToast } = useDashboard();

    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

    // In Preview: we might want to poll 'previewStore' strategies instead of 'adapter' if fully sim?
    // For now, adapter.getStrategies is likely what we use, and maybe that adapter should switch 
    // to previewStore if preview is on? 
    // Assuming adapter is NOT fully preview-aware yet for 'getStrategies', we can hybridize here.

    // HYBRID FETCH:
    const strategiesResource = usePolledResource<StrategyConfig[]>((signal) => {
        if (isPreview) {
            // Return promise resolving to preview store strategies
            return Promise.resolve(previewStore.getState().strategies);
        }
        return getStrategies(signal, client);
    }, 4000, [auth, isPreview]); // Re-fetch on preview mode toggle

    const [loading, setLoading] = useState(false);

    // Modal/Drawer States
    const [drawerStrategyId, setDrawerStrategyId] = useState<string | null>(null);
    const [duplicateStrategy, setDuplicateStrategy] = useState<StrategyConfig | null>(null);

    const handleProfile = async (profile: 'SHIELD' | 'BALANCED' | 'ROCKET') => {
        // if (!confirm(`Switch entire strategy profile to ${profile}? This will adjust all weights.`)) return;
        setLoading(true);
        try {
            if (isPreview) {
                // journalStore.addLog('MODE_CHANGE', `Profile Switched to ${profile} (SIM)`, 'HUMAN');
                previewStore.deployStrategy(profile, 0.2); // Mock helper with default weight
                addToast({ type: 'SUCCESS', message: `Profile switched to ${profile}` });
            } else {
                await setStrategyProfile(profile, new AbortController().signal, client);
                addToast({ type: 'SUCCESS', message: `Profile switched to ${profile}` });
            }
            strategiesResource.refresh();
        } catch (e) {
            addToast({ type: 'ERROR', message: `Failed: ${String(e)}` });
        } finally { setLoading(false); }
    };

    const handleHalt = async () => {
        if (!confirm("EMERGENCY HALT ALL STRATEGIES?")) return;
        setLoading(true);
        try {
            if (isPreview) {
                previewStore.flattenPortfolio(); // Reuse flatten as "Halt" or setGlobalStop
                addToast({ type: 'WARNING', message: "All Strategies HALTED (Simulated)" });
            } else {
                await haltStrategies(new AbortController().signal, client);
                addToast({ type: 'WARNING', message: "All Strategies HALTED" });
            }
            strategiesResource.refresh();
        } catch (e) { addToast({ type: 'ERROR', message: String(e) }); } finally { setLoading(false); }
    };

    const toggleStrategy = async (id: string, currentEnabled: boolean, weight: number) => {
        setLoading(true);
        try {
            if (isPreview) {
                previewStore.toggleStrategy(id, !currentEnabled);
                addToast({ type: 'INFO', message: `Strategy ${id} ${!currentEnabled ? 'Enabled' : 'Paused'}` });
            } else {
                await updateStrategies([{ id, enabled: !currentEnabled, weight }], new AbortController().signal, client);
                addToast({ type: 'INFO', message: `Strategy ${id} updated` });
            }
            strategiesResource.refresh();
        } catch (e) { addToast({ type: 'ERROR', message: String(e) }); } finally { setLoading(false); }
    };

    const handleSimulate = (id: string) => {
        if (isPreview) {
            previewStore.simulateStrategyRun(id);
            addToast({ type: 'SUCCESS', message: `Simulation run for ${id}` });
        } else {
            addToast({ type: 'WARNING', message: "Simulation endpoint not available in Production Env." });
        }
    };

    const handleDuplicate = (strategy: StrategyConfig) => {
        setDuplicateStrategy(strategy);
    };

    const handleArchive = async (id: string) => {
        if (!confirm(`Are you sure you want to Archive strategy ${id}?`)) return;
        if (isPreview) {
            previewStore.archiveStrategy(id);
            strategiesResource.refresh();
            addToast({ type: 'INFO', message: `Strategy ${id} archived` });
        } else {
            addToast({ type: 'WARNING', message: "Archive Endpoint unavailable / not enabled in Production." });
        }
    };

    const saveDuplicate = async (newConfig: Partial<StrategyConfig>) => {
        if (isPreview && duplicateStrategy) {
            previewStore.duplicateStrategy(duplicateStrategy.id, newConfig);
            strategiesResource.refresh();
            addToast({ type: 'SUCCESS', message: "Strategy Duplicated (Sim)" });
        } else {
            addToast({ type: 'WARNING', message: "Create Strategy Endpoint unavailable / not enabled in Production." });
        }
    };

    return (
        <div className="strategies-page">
            <header className="flex-between" style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between' }}>
                <div>
                    {isPreview && (
                        <div className="tiny badge warning mb-2">PREVIEW / SIMULATION MODE</div>
                    )}
                    <h1 style={{ margin: 0 }}>STRATEGY ENGINE</h1>
                    <div className="small muted">Algorithmic Profiles & Weights</div>
                </div>
                <button className="button danger" onClick={handleHalt} disabled={loading} style={{ fontWeight: 'bold' }}>
                    STOP ALL STRATEGIES
                </button>
            </header>

            <div className="card" style={{ marginBottom: '2rem' }}>
                <h3>Global Profile Selection</h3>
                <p className="small muted">One-click configuration for market conditions.</p>
                <div className="grid-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginTop: '1rem' }}>
                    <button className="button secondary" onClick={() => handleProfile('SHIELD')}>
                        <strong style={{ display: 'block', fontSize: '1.2em' }}>🛡️ SHIELD</strong>
                        <span className="small">Low Risk • Capital Preservation</span>
                    </button>
                    <button className="button primary" onClick={() => handleProfile('BALANCED')}>
                        <strong style={{ display: 'block', fontSize: '1.2em' }}>⚖️ BALANCED</strong>
                        <span className="small">Moderate • Growth & Yield</span>
                    </button>
                    <button className="button secondary" onClick={() => handleProfile('ROCKET')}>
                        <strong style={{ display: 'block', fontSize: '1.2em' }}>🚀 ROCKET</strong>
                        <span className="small">High Risk • Max Velocity</span>
                    </button>
                </div>
            </div>

            <div className="card">
                <h3>Strategy Registry</h3>
                <div className="table-container">
                    <table className="data-table" style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid #333' }}>
                                <th style={{ padding: '1rem' }}>Name</th>
                                <th>Core Logic</th>
                                <th>Horizon</th>
                                <th>Risk Class</th>
                                <th style={{ textAlign: 'center' }}>Weight</th>
                                <th style={{ textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {strategiesResource.data?.map(s => (
                                <tr key={s.id} style={{ borderBottom: '1px solid #222', opacity: s.enabled ? 1 : 0.6 }}>
                                    <td style={{ padding: '1rem' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <strong>{s.name}</strong>
                                            <span className={`tiny badge ${s.enabled ? 'success' : 'secondary'}`} style={{ fontSize: '0.6rem' }}>
                                                {s.enabled ? 'LIVE' : 'PAUSED'}
                                            </span>
                                        </div>
                                        <div className="small muted">{s.id}</div>

                                        <div style={{ marginTop: '0.5rem', display: 'flex', gap: '1rem' }}>
                                            <span className="tiny font-mono muted">
                                                Active Orders: <strong className="text-primary">{(s as any).order_count || 0}</strong>
                                            </span>
                                            {/* Last Updated could go here */}
                                        </div>

                                        <StrategyPerformanceMetrics
                                            strategyId={s.id}
                                            roi={s.metric_roi ?? ((Math.random() * 20) - 5)}
                                            sharpe={s.metric_sharpe ?? ((Math.random() * 2) + 0.5)}
                                            drawdown={s.metric_drawdown ?? (Math.random() * 10)}
                                            winRate={s.metric_win_rate ?? (40 + (Math.random() * 40))}
                                        />
                                    </td>
                                    <td><span className="badge">{s.core}</span></td>
                                    <td>{s.horizon}</td>
                                    <td>
                                        <span className={`badge ${s.risk_label === 'LOW' ? 'success' : s.risk_label === 'HIGH' ? 'danger' : 'warning'}`}>
                                            {s.risk_label}
                                        </span>
                                    </td>
                                    <td style={{ textAlign: 'center', fontFamily: 'monospace' }}>
                                        {(s.weight * 100).toFixed(1)}%
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end' }}>
                                            <div style={{ display: 'flex', gap: '4px' }}>
                                                {/* ROW 1: Lifecycle Controls */}
                                                <button
                                                    className="button tiny ghost"
                                                    title="Simulate Event"
                                                    onClick={() => handleSimulate(s.id)}
                                                >
                                                    ⚡ SIM
                                                </button>
                                                <button
                                                    className="button tiny ghost"
                                                    title="View Orders"
                                                    onClick={() => setDrawerStrategyId(s.id)}
                                                >
                                                    ORDERS
                                                </button>
                                            </div>
                                            <div style={{ display: 'flex', gap: '4px' }}>
                                                {/* ROW 2: Admin Controls */}
                                                <button
                                                    className="button tiny ghost"
                                                    onClick={() => handleDuplicate(s)}
                                                >
                                                    COPY
                                                </button>
                                                <button
                                                    className="button tiny ghost danger"
                                                    onClick={() => handleArchive(s.id)}
                                                >
                                                    ARCHIVE
                                                </button>
                                                <button
                                                    className={`button tiny ${s.enabled ? 'secondary' : 'primary'}`}
                                                    style={{ minWidth: '80px' }}
                                                    onClick={() => toggleStrategy(s.id, s.enabled, s.weight)}
                                                >
                                                    {s.enabled ? 'PAUSE' : 'MAKE LIVE'}
                                                </button>
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            {(!strategiesResource.data || strategiesResource.data.length === 0) && (
                                <tr><td colSpan={6} style={{ padding: '2rem', textAlign: 'center' }}>Loading strategies...</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* DRAWERS & MODALS */}
            {drawerStrategyId && (
                <StrategyOrdersDrawer
                    strategyId={drawerStrategyId}
                    isOpen={true}
                    onClose={() => setDrawerStrategyId(null)}
                />
            )}

            {duplicateStrategy && (
                <DuplicateStrategyModal
                    strategy={duplicateStrategy}
                    isOpen={true}
                    onClose={() => setDuplicateStrategy(null)}
                    onSave={saveDuplicate}
                />
            )}
        </div>
    );
};
