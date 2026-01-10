import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { usePolledResource } from '../hooks/usePolledResource';
import {
    getExchangeKeys,
    getOpsState,
    getStrategies,
    getPortfolioStructure
} from '../api/adapter';
import type { PortfolioDefinition } from '../api/types';

export const GettingStartedPage: React.FC = () => {
    const navigate = useNavigate();
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };

    // Poll all states related to onboarding
    const keys = usePolledResource<any[]>((signal) => getExchangeKeys(signal, client), 2000, [auth]);
    const ops = usePolledResource<any>((signal) => getOpsState(signal, client), 2000, [auth]);
    const strats = usePolledResource<any[]>((signal) => getStrategies(signal, client), 2000, [auth]);
    const portfolios = usePolledResource<PortfolioDefinition[]>((signal) => getPortfolioStructure(signal, client), 2000, [auth]);

    // Derived Status
    const hasKeys = keys.data && keys.data.some(k => k.status === 'CONNECTED');
    const hasMode = ops.data && ops.data.system_mode && ops.data.system_mode !== 'MANUAL';
    const hasCap = ops.data && ops.data.ops && ops.data.ops.capital && ops.data.ops.capital.cap_pct > 0;
    const hasStrat = strats.data && strats.data.some((s: any) => s.enabled);
    const hasPortfolio = portfolios.data && portfolios.data.length > 0;

    const tourActive = window.history.state?.usr?.tourActive;

    const stepStatus = [
        { id: 1, label: 'Connect Exchange Keys', done: hasKeys, route: '/exchange-keys', btn: 'Connect' },
        { id: 2, label: 'Set System Mode', done: hasMode, route: '/system', btn: 'Configure' },
        { id: 3, label: 'Set Capital Cap > 0%', done: hasCap, route: '/system', btn: 'Set Cap' },
        { id: 4, label: 'Select Strategy Profile', done: hasStrat, route: '/strategies', btn: 'Select' },
        { id: 5, label: 'Create First Portfolio', done: hasPortfolio, route: '/portfolio', btn: 'Create' },
    ];

    const allDone = stepStatus.every(s => s.done);

    const startTour = () => {
        navigate('/exchange-keys', { state: { tourActive: true, stepId: 'connect-keys' } });
    };

    return (
        <div className="page-container" style={{ maxWidth: '800px', margin: '0 auto', padding: '48px 24px' }}>
            <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
                <h1 className="text-primary" style={{ fontSize: '2rem', marginBottom: '0.5rem', fontWeight: 600 }}>
                    Welcome to Lunia Terminal
                </h1>
                <p className="muted" style={{ fontSize: '1.1rem' }}>
                    Follow the setup guide to activate the algorithmic engine.
                </p>
            </div>

            <div className="card" style={{ padding: '2rem', border: '1px solid var(--border-color)', marginBottom: '2rem' }}>
                <div className="flex-between">
                    <div>
                        <h2 style={{ margin: 0, fontSize: '1.2rem' }}>Setup Checklist</h2>
                        <p className="muted small" style={{ marginTop: '0.5rem' }}>
                            {allDone ? "All systems operational." : "Complete these steps to enable live trading."}
                        </p>
                    </div>
                    {!allDone ? (
                        <button className="button primary large" onClick={startTour}>
                            Start Guided Tour &rarr;
                        </button>
                    ) : (
                        <div style={{ display: 'flex', gap: '1rem' }}>
                            <button className="button secondary large" onClick={startTour}>
                                Restart Tour ↻
                            </button>
                            <button className="button success large" onClick={() => navigate('/trader')}>
                                Go to Dashboard &rarr;
                            </button>
                        </div>
                    )}
                </div>

                <div style={{ marginTop: '2rem' }}>
                    {stepStatus.map((step) => (
                        <div key={step.id} style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '1rem',
                            borderBottom: '1px solid var(--border-color)',
                            backgroundColor: step.done ? 'var(--bg-panel-soft)' : 'transparent'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                <div style={{
                                    width: '24px',
                                    height: '24px',
                                    borderRadius: '50%',
                                    backgroundColor: step.done ? 'var(--status-ok)' : 'var(--bg-panel)',
                                    border: `2px solid ${step.done ? 'var(--status-ok)' : 'var(--text-muted)'}`,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: step.done ? 'white' : 'transparent',
                                    fontSize: '14px',
                                    fontWeight: 'bold'
                                }}>
                                    ✓
                                </div>
                                <span style={{
                                    textDecoration: step.done ? 'line-through' : 'none',
                                    color: step.done ? 'var(--text-muted)' : 'var(--text-primary)',
                                    fontWeight: 500
                                }}>
                                    {step.label}
                                </span>
                            </div>
                            {!step.done && (
                                <button className="button secondary small" onClick={() => navigate(step.route)}>
                                    {step.btn} &rarr;
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            <div style={{ textAlign: 'center', marginTop: '3rem' }}>
                <p className="small muted">
                    Running in {import.meta.env.MODE} mode. <br />
                    <span className="tiny">Build: {import.meta.env.VITE_APP_BUILD || 'dev-local'}</span>
                </p>
            </div>
        </div>
    );
};
