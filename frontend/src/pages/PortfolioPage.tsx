import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { usePolledResource } from '../hooks/usePolledResource';
import {
    getPortfolioStructure,
    runPortfolioAction,
    setPortfolioDraftConfig,
    setPortfolioDraftAssets,
    analyzePortfolioDraft,
    createPortfolio
} from '../api/adapter';
import type { PortfolioDefinition } from '../api/types';

import { useLocation } from 'react-router-dom';
import { useDashboard } from '../context/DashboardContext';

import { PortfolioDetailDrawer } from '../components/portfolio/PortfolioDetailDrawer';
import { AIResearchCards } from '../components/widgets/AIResearchCards';
import { CreatePortfolioWizard } from '../components/widgets/CreatePortfolioWizard';

export const PortfolioPage: React.FC = () => {
    const auth = useAuth();
    const location = useLocation() as { state: any };
    const client = {
        role: auth.role,
        adminToken: auth.adminToken,
        opsToken: auth.opsToken,
        bearerToken: auth.bearerToken
    };

    const portfolios = usePolledResource<PortfolioDefinition[]>((signal) => getPortfolioStructure(signal, client), 4000, [auth]);
    const [view, setView] = useState<'ACTIVE' | 'WIZARD'>(
        location.state?.tourActive && location.state?.stepId === 'portfolio-wizard' ? 'WIZARD' : 'ACTIVE'
    );

    // Selection for Drawer
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const selectedPortfolio = portfolios.data?.find(p => p.id === selectedId);

    // Wizard State
    const [step, setStep] = useState(1);
    const [config, setConfig] = useState({ horizon: '1 MONTH', risk_profile: 'BALANCED' });
    const [assetsInput, setAssetsInput] = useState('BTC, ETH');
    const [analysis, setAnalysis] = useState<any>(null);
    const [loading, setLoading] = useState(false);

    const { addToast } = useDashboard();

    const handleAction = async (e: React.MouseEvent, id: string, action: 'PAUSE' | 'RESUME' | 'DERISK' | 'REBALANCE') => {
        e.stopPropagation(); // Prevent drawer open
        // if (!confirm(`Confirm ${action} for portfolio ${id}?`)) return;
        try {
            await runPortfolioAction(id, action, new AbortController().signal, client);
            portfolios.refresh();
            addToast({ type: 'SUCCESS', message: `Portfolio ${id} ${action}ED` });
        } catch (e) {
            addToast({ type: 'ERROR', message: `Action failed: ${e}` });
        }
    };

    const runStep1 = async () => {
        setLoading(true);
        try {
            await setPortfolioDraftConfig(config, new AbortController().signal, client);
            setStep(2);
            addToast({ type: 'INFO', message: "Configuration Set" });
        } catch (e) { addToast({ type: 'ERROR', message: String(e) }); } finally { setLoading(false); }
    };

    const runStep2 = async () => {
        setLoading(true);
        const assetList = assetsInput.split(',').map(s => s.trim().toUpperCase()).filter(s => s);
        try {
            await setPortfolioDraftAssets(assetList, new AbortController().signal, client);
            setStep(3);
            addToast({ type: 'INFO', message: `Assets selected: ${assetList.length}` });
        } catch (e) { addToast({ type: 'ERROR', message: String(e) }); } finally { setLoading(false); }
    };

    const runStep3 = async () => {
        setLoading(true);
        try {
            const result = await analyzePortfolioDraft(new AbortController().signal, client);
            setAnalysis(result);
            addToast({ type: 'SUCCESS', message: "AI Analysis Complete" });
        } catch (e) { addToast({ type: 'ERROR', message: String(e) }); } finally { setLoading(false); }
    };

    const runDeploy = async () => {
        // if (!confirm("Deploy this portfolio to LIVE trading?")) return;
        setLoading(true);
        try {
            await createPortfolio(new AbortController().signal, client);
            addToast({ type: 'SUCCESS', message: "Portfolio Created Successfully!" });
            setView('ACTIVE');
            setStep(1);
            setAnalysis(null);
            portfolios.refresh();
        } catch (e) { addToast({ type: 'ERROR', message: String(e) }); } finally { setLoading(false); }
    };

    return (
        <div className="portfolio-page">
            <header className="flex-between" style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between' }}>
                <div>
                    {location.state?.tourActive && location.state?.stepId === 'portfolio-wizard' && (
                        <div style={{ marginBottom: '8px' }}>
                            <span className="tiny font-bold uppercase" style={{
                                backgroundColor: 'var(--accent-primary)',
                                color: 'white',
                                padding: '2px 8px',
                                borderRadius: '4px'
                            }}>
                                Step 6: Create Portfolio
                            </span>
                        </div>
                    )}
                    <h1 style={{ margin: 0 }}>PORTFOLIO ENGINE</h1>
                    <div className="small muted">Lifecycle Management & Construction</div>
                </div>
                <div className="button-group">
                    <button className={`button ${view === 'ACTIVE' ? 'primary' : 'secondary'}`} onClick={() => setView('ACTIVE')}>Active Portfolios</button>
                    <button className={`button ${view === 'WIZARD' ? 'primary' : 'secondary'}`} onClick={() => setView('WIZARD')}>Create New</button>
                </div>
            </header>

            {view === 'ACTIVE' && (
                <div className="active-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: '1.5rem' }}>

                    {portfolios.data?.map(p => (
                        <div
                            key={p.id}
                            className="card hover-effect"
                            style={{
                                borderLeft: `4px solid ${p.status === 'ACTIVE' ? '#22c55e' : (p.status === 'PAUSED' ? '#eab308' : '#ef4444')}`,
                                cursor: 'pointer',
                                transition: 'transform 0.1s'
                            }}
                            onClick={() => setSelectedId(p.id)}
                            title="Click to view details"
                        >
                            <div className="flex-between">
                                <h3>{p.id}</h3>
                                <span className={`badge ${p.status === 'ACTIVE' ? 'success' : (p.status === 'PAUSED' ? 'warning' : 'danger')}`}>
                                    {p.status}
                                </span>
                            </div>
                            <div className="small muted" style={{ marginBottom: '1rem' }}>
                                {p.type} • {p.risk_profile} • {p.horizon}
                            </div>

                            <table style={{ width: '100%', marginBottom: '1rem', fontSize: '0.85rem' }}>
                                <thead>
                                    <tr style={{ textAlign: 'left', color: '#888' }}>
                                        <th>Asset</th>
                                        <th style={{ textAlign: 'right' }}>Target</th>
                                        <th style={{ textAlign: 'right' }}>Sector</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {p.assets.slice(0, 4).map(a => (
                                        <tr key={a.symbol}>
                                            <td><strong>{a.symbol}</strong></td>
                                            <td style={{ textAlign: 'right' }}>{(a.weight * 100).toFixed(0)}%</td>
                                            <td style={{ textAlign: 'right' }}><span className="badge small subtle">{a.sector}</span></td>
                                        </tr>
                                    ))}
                                    {p.assets.length > 4 && (
                                        <tr><td colSpan={3} className="text-center tiny muted pt-2">+{p.assets.length - 4} more</td></tr>
                                    )}
                                </tbody>
                            </table>

                            <div className="actions" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                                {p.status !== 'ACTIVE' ? (
                                    <button className="button primary small" onClick={(e) => handleAction(e, p.id, 'RESUME')}>Resume</button>
                                ) : (
                                    <button className="button secondary small" onClick={(e) => handleAction(e, p.id, 'PAUSE')}>Pause</button>
                                )}
                                <button className="button secondary small" onClick={(e) => handleAction(e, p.id, 'REBALANCE')}>Rebalance</button>

                                {/* P2.3: De-Risk / Flatten */}
                                <button
                                    className="button danger outline small"
                                    style={{ gridColumn: 'span 2' }}
                                    onClick={(e) => handleAction(e, p.id, 'DERISK')}
                                    title="Close all positions into stablecoin (Scoped)"
                                >
                                    De-Risk (Flatten)
                                </button>
                            </div>
                        </div>
                    ))}

                    {(!portfolios.data || portfolios.data.length === 0) && (
                        <div className="muted border-dashed border-2 rounded p-8 text-center">
                            No active portfolios found.<br />
                            <button className="button text" onClick={() => setView('WIZARD')}>Create one with the Wizard</button>
                        </div>
                    )}
                </div>
            )}

            {/* Drawer */}
            {selectedPortfolio && (
                <PortfolioDetailDrawer
                    portfolio={selectedPortfolio}
                    onClose={() => setSelectedId(null)}
                    client={client}
                />
            )}

            {view === 'WIZARD' && (
                <div className="wizard-container" style={{ maxWidth: '800px', margin: '0 auto' }}>
                    <div className="steps" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2rem' }}>
                        <div className={`step ${step >= 1 ? 'active' : ''}`}>1. Configuration</div>
                        <div className={`step ${step >= 2 ? 'active' : ''}`}>2. Asset Selection</div>
                        <div className={`step ${step >= 3 ? 'active' : ''}`}>3. AI Analysis</div>
                        <div className={`step ${step >= 4 ? 'active' : ''}`}>4. Deploy</div>
                    </div>

                    <div className="card">
                        {step === 1 && (
                            <div className="step-content">
                                <h3>Step 1: Portfolio Configuration</h3>
                                <div className="form-group">
                                    <label>Investment Horizon</label>
                                    <select value={config.horizon} onChange={e => setConfig({ ...config, horizon: e.target.value })} style={{ width: '100%', padding: '0.5rem', marginBottom: '1rem' }}>
                                        <option value="1 WEEK">Short Term (1 Week)</option>
                                        <option value="1 MONTH">Medium Term (1 Month)</option>
                                        <option value="1 YEAR">Long Term (1 Year)</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Risk Profile</label>
                                    <select value={config.risk_profile} onChange={e => setConfig({ ...config, risk_profile: e.target.value })} style={{ width: '100%', padding: '0.5rem', marginBottom: '1rem' }}>
                                        <option value="SHIELD">SHIELD (Conservative)</option>
                                        <option value="BALANCED">BALANCED (Moderate)</option>
                                        <option value="ROCKET">ROCKET (Aggressive)</option>
                                    </select>
                                </div>
                                <button className="button primary" onClick={runStep1} disabled={loading}>Next: Asset Selection &rarr;</button>
                            </div>
                        )}

                        {step === 2 && (
                            <div className="step-content">
                                <h3>Step 2: Asset Selection</h3>
                                <p className="muted small">Enter comma-separated symbols you wish to include.</p>
                                <textarea
                                    value={assetsInput}
                                    onChange={e => setAssetsInput(e.target.value)}
                                    style={{ width: '100%', minHeight: '100px', padding: '0.5rem', marginBottom: '1rem', fontFamily: 'monospace' }}
                                />
                                <div className="flex-gap">
                                    <button className="button secondary" onClick={() => setStep(1)} disabled={loading}>&larr; Back</button>
                                    <button className="button primary" onClick={runStep2} disabled={loading}>Next: AI Analysis &rarr;</button>
                                </div>
                            </div>
                        )}

                        {step === 3 && (
                            <div className="step-content">
                                <h3>Step 3: AI Validation & Scoring</h3>
                                {!analysis ? (
                                    <div style={{ textAlign: 'center', padding: '2rem' }}>
                                        <p>Click below to run Monte Carlo simulations and correlation analysis.</p>
                                        <button className="button primary" onClick={runStep3} disabled={loading}>Run Analysis</button>
                                    </div>
                                ) : (
                                    <div className="analysis-results">
                                        <div className="alert custom" style={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                                <span>Confidence Score</span>
                                                <strong style={{ color: analysis.confidence > 0.8 ? '#4ade80' : '#facc15' }}>
                                                    {(analysis.confidence * 100).toFixed(1)}%
                                                </strong>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                                <span>Est. Drawdown</span>
                                                <strong style={{ color: '#f87171' }}>
                                                    {(analysis.drawdown_est * 100).toFixed(1)}%
                                                </strong>
                                            </div>
                                            <hr style={{ borderColor: '#334155' }} />
                                            <ul className="small muted">
                                                {analysis.notes?.map((n: string, i: number) => <li key={i}>{n}</li>)}
                                            </ul>
                                        </div>
                                        <div className="flex-gap" style={{ marginTop: '1rem' }}>
                                            <button className="button secondary" onClick={() => setAnalysis(null)} disabled={loading}>Re-Run</button>
                                            <button className="button primary" onClick={runDeploy} disabled={loading} style={{ backgroundColor: '#22c55e' }}>DEPLOY PORTFOLIO</button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
