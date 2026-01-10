import React from 'react';
import { useNavigate } from 'react-router-dom';

export const LandingPage: React.FC = () => {
    const navigate = useNavigate();

    return (
        <div className="landing-page" style={{
            minHeight: '100vh',
            backgroundColor: 'var(--bg-main)',
            color: 'var(--text-primary)',
            display: 'flex',
            flexDirection: 'column'
        }}>
            {/* NAVIGATION */}
            <nav style={{
                padding: '1.5rem 3rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '1px solid var(--border-color)',
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                position: 'sticky',
                top: 0,
                zIndex: 50
            }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '0.05em' }}>
                    LUNIA <span style={{ color: 'var(--accent-primary)', opacity: 0.5 }}>//</span> ALADDIN
                </div>
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <button
                        className="button"
                        onClick={() => navigate('/login')}
                    >
                        Log In
                    </button>
                    <button
                        className="button primary"
                        onClick={() => navigate('/register')}
                    >
                        Create Account
                    </button>
                </div>
            </nav>

            {/* HERO SECTION */}
            <header style={{
                padding: '8rem 2rem',
                textAlign: 'center',
                maxWidth: '1200px',
                margin: '0 auto',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center'
            }}>
                <div className="badge" style={{ marginBottom: '1rem', border: '1px solid var(--border-color)', background: 'transparent' }}>
                    ALADDIN-CLASS GOVERNANCE ENGINE
                </div>
                <h1 style={{
                    fontSize: '3.5rem',
                    fontWeight: 700,
                    marginBottom: '1rem',
                    letterSpacing: '-0.02em',
                    lineHeight: 1.1,
                    maxWidth: '900px'
                }}>
                    Institutional-Grade Control <br />
                    <span style={{ color: 'var(--text-secondary)' }}>for the AI Age</span>
                </h1>
                <p style={{
                    fontSize: '1.25rem',
                    color: 'var(--text-secondary)',
                    maxWidth: '600px',
                    marginBottom: '3rem',
                    lineHeight: 1.6
                }}>
                    Control Risk. Govern Automation. Stay in Charge.<br />
                    The first trading engine built for safety, not just speed.
                </p>
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <button
                        className="button primary"
                        style={{ padding: '0.75rem 2rem', fontSize: '1rem' }}
                        onClick={() => navigate('/register')}
                    >
                        Start Trading
                    </button>
                    <button
                        className="button"
                        style={{ padding: '0.75rem 2rem', fontSize: '1rem' }}
                        onClick={() => navigate('/login')}
                    >
                        Access Terminal
                    </button>
                </div>
            </header>

            {/* STATS / FEATURES BAR - Institutional Feel */}
            <section style={{
                borderTop: '1px solid var(--border-color)',
                borderBottom: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-panel)',
                padding: '2rem 0'
            }}>
                <div style={{
                    maxWidth: '1200px',
                    margin: '0 auto',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '2rem',
                    padding: '0 2rem'
                }}>
                    <div>
                        <h3 className="tiny uppercase muted" style={{ marginBottom: '0.5rem' }}>Core Philosophy</h3>
                        <p style={{ fontWeight: 600 }}>Governed Automation</p>
                    </div>
                    <div>
                        <h3 className="tiny uppercase muted" style={{ marginBottom: '0.5rem' }}>Risk Management</h3>
                        <p style={{ fontWeight: 600 }}>Pre-Trade Verification</p>
                    </div>
                    <div>
                        <h3 className="tiny uppercase muted" style={{ marginBottom: '0.5rem' }}>Transparency</h3>
                        <p style={{ fontWeight: 600 }}>Explainable AI Logic</p>
                    </div>
                    <div>
                        <h3 className="tiny uppercase muted" style={{ marginBottom: '0.5rem' }}>Security</h3>
                        <p style={{ fontWeight: 600 }}>Non-Custodial Architecture</p>
                    </div>
                </div>
            </section>

            {/* HOW IT WORKS */}
            <section style={{ padding: '6rem 2rem', maxWidth: '1000px', margin: '0 auto' }}>
                <h2 style={{ fontSize: '2rem', marginBottom: '3rem', textAlign: 'center' }}>Workflow Integrity</h2>
                <div className="grid cols-3" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
                    <div className="card subtle" style={{ textAlign: 'center' }}>
                        <div style={{ marginBottom: '1rem', color: 'var(--accent-primary)', fontSize: '1.5rem', fontWeight: 700 }}>01</div>
                        <h3>Connect Exchange</h3>
                        <p className="small muted" style={{ marginTop: '0.5rem' }}>Securely link via API keys. Funds remain on your verified exchange.</p>
                    </div>
                    <div className="card subtle" style={{ textAlign: 'center' }}>
                        <div style={{ marginBottom: '1rem', color: 'var(--accent-primary)', fontSize: '1.5rem', fontWeight: 700 }}>02</div>
                        <h3>Define Governance</h3>
                        <p className="small muted" style={{ marginTop: '0.5rem' }}>Set hard capital caps, risk limits, and operational boundaries.</p>
                    </div>
                    <div className="card subtle" style={{ textAlign: 'center' }}>
                        <div style={{ marginBottom: '1rem', color: 'var(--accent-primary)', fontSize: '1.5rem', fontWeight: 700 }}>03</div>
                        <h3>Execute Controlled</h3>
                        <p className="small muted" style={{ marginTop: '0.5rem' }}>Choose Manual, Semi-Auto, or earn access to Full Automation.</p>
                    </div>
                </div>
            </section>

            {/* TRUST & PROGRESSION (P3.5) */}
            <section style={{ padding: '6rem 2rem', background: 'var(--bg-panel-soft)' }}>
                <div style={{ maxWidth: '1000px', margin: '0 auto', textAlign: 'center' }}>
                    <h2 style={{ fontSize: '2rem', marginBottom: '1rem' }}>Earn Your Authority</h2>
                    <p className="muted" style={{ maxWidth: '600px', margin: '0 auto 3rem' }}>
                        Lunia operates on a "Proof of Competence" model. Unlock higher leverage and advanced algorithms as you demonstrate responsible risk management.
                    </p>

                    <div className="grid cols-3" style={{ gap: '2rem', textAlign: 'left' }}>
                        <div className="card subtle">
                            <div className="badge secondary mb-2">TIER 1</div>
                            <h4>Standard Retail</h4>
                            <ul className="small muted mt-2">
                                <li>• Manual Execution</li>
                                <li>• 1x Leverage Limit</li>
                                <li>• Basic Risk Protection</li>
                            </ul>
                        </div>
                        <div className="card subtle" style={{ border: '1px solid var(--accent-primary)' }}>
                            <div className="badge primary mb-2">TIER 2</div>
                            <h4>Advanced Trader</h4>
                            <ul className="small muted mt-2">
                                <li>• Semi-Auto AI Proposals</li>
                                <li>• 3x Leverage Limit</li>
                                <li>• Trailing Stop Access</li>
                            </ul>
                        </div>
                        <div className="card subtle">
                            <div className="badge expert mb-2">TIER 3</div>
                            <h4>Institutional</h4>
                            <ul className="small muted mt-2">
                                <li>• Full-Auto AI Agents</li>
                                <li>• Custom Risk Models</li>
                                <li>• Dark Pool Routing</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </section>

            {/* SUPPORTED VENUES */}
            <section style={{ backgroundColor: 'var(--bg-panel)', padding: '4rem 2rem', textAlign: 'center' }}>
                <h3 className="small muted uppercase" style={{ letterSpacing: '0.2em', marginBottom: '2rem' }}>Supported Venues</h3>
                <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    gap: '4rem',
                    opacity: 0.7,
                    fontSize: '1.5rem',
                    fontWeight: 700,
                    fontFamily: 'monospace'
                }}>
                    <span>BINANCE</span>
                    <span>BYBIT</span>
                    <span>OKX</span>
                    <span>KRAKEN</span>
                </div>
            </section>

            {/* UPGRADE / PRICING */}
            <section style={{ padding: '6rem 2rem', maxWidth: '1100px', margin: '0 auto' }}>
                <h2 style={{ fontSize: '2rem', marginBottom: '3rem', textAlign: 'center' }}>Institution-Ready Plans</h2>
                <div className="grid cols-3" style={{ gap: '2rem' }}>
                    {/* STARTER */}
                    <div className="card" style={{ padding: '2rem' }}>
                        <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Starter</h3>
                        <div style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '2rem' }}>$0 <span className="small muted">/ mo</span></div>
                        <ul className="small muted" style={{ lineHeight: '1.8', marginBottom: '2rem' }}>
                            <li>Manual Execution</li>
                            <li>Basic Risk Checks</li>
                            <li>1 Exchange Connection</li>
                            <li>Portfolio Tracking</li>
                        </ul>
                        <button className="button full-width outline-primary" onClick={() => navigate('/register')}>Start Free</button>
                    </div>

                    {/* PRO - Highlighted */}
                    <div className="card" style={{ padding: '2rem', border: '1px solid var(--accent-primary)', position: 'relative' }}>
                        <div style={{ position: 'absolute', top: '-10px', right: '50%', transform: 'translateX(50%)', background: 'var(--accent-primary)', color: 'white', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>POPULAR</div>
                        <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem', color: 'var(--accent-primary)' }}>Professional</h3>
                        <div style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '2rem' }}>$499 <span className="small muted">/ mo</span></div>
                        <ul className="small muted" style={{ lineHeight: '1.8', marginBottom: '2rem' }}>
                            <li>Semi-Auto AI Proposals</li>
                            <li>Advanced Risk Engine</li>
                            <li>5 Exchange Connections</li>
                            <li>Priority Support</li>
                        </ul>
                        <button className="button full-width primary" onClick={() => navigate('/register')}>Start Trial</button>
                    </div>

                    {/* ENTERPRISE */}
                    <div className="card" style={{ padding: '2rem' }}>
                        <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>Fund / Enterprise</h3>
                        <div style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '2rem' }}>Custom</div>
                        <ul className="small muted" style={{ lineHeight: '1.8', marginBottom: '2rem' }}>
                            <li>Full Auto Unlocked (Vetted)</li>
                            <li>Dedicated Inference Node</li>
                            <li>Unlimited Connections</li>
                            <li>SLA & Audit Logs</li>
                        </ul>
                        <button className="button full-width outline" onClick={() => navigate('/register')}>Contact Sales</button>
                    </div>
                </div>
            </section>

            {/* SAFETY & GOVERNANCE */}
            <section style={{ backgroundColor: 'var(--bg-panel)', padding: '6rem 2rem' }}>
                <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4rem', alignItems: 'center' }}>
                    <div>
                        <h2 style={{ fontSize: '2rem', marginBottom: '1.5rem' }}>Safety & Governance</h2>
                        <p className="muted" style={{ fontSize: '1.1rem', marginBottom: '2rem' }}>
                            LUNIA is designed with a "Safety First" architecture. Every action is validated against a pre-defined risk model before execution.
                        </p>

                        <div className="grid" style={{ gap: '1.5rem' }}>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <div style={{ color: 'var(--accent-danger)', fontSize: '1.25rem' }}>🛡</div>
                                <div>
                                    <h4 style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Risk Veto</h4>
                                    <p className="small muted">System automatically blocks trades that violate risk policies. Cannot be overridden.</p>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <div style={{ color: 'var(--accent-warning)', fontSize: '1.25rem' }}>🛑</div>
                                <div>
                                    <h4 style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Emergency Stop</h4>
                                    <p className="small muted">Global kill-switch to immediately halt all activity and cancel open orders.</p>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: '1rem' }}>
                                <div style={{ color: 'var(--accent-primary)', fontSize: '1.25rem' }}>⚖️</div>
                                <div>
                                    <h4 style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Capital Allocator</h4>
                                    <p className="small muted">Strict capital caps ensure the system never risks more than authorized.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div>
                        {/* Abstract Visual Representation of Governance */}
                        <div style={{
                            background: 'var(--bg-main)',
                            border: '1px solid var(--border-color)',
                            borderRadius: 'var(--border-radius)',
                            padding: '2rem',
                            position: 'relative'
                        }}>
                            <div className="flex-between" style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
                                <span className="tiny font-mono muted">GOVERNANCE_ENGINE</span>
                                <span className="status-chip ok">ACTIVE</span>
                            </div>
                            <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                                <span className="small">Max Daily Drawdown</span>
                                <span className="small font-mono text-primary">2.00%</span>
                            </div>
                            <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                                <span className="small">Max Exposure</span>
                                <span className="small font-mono text-primary">15% / Asset</span>
                            </div>
                            <div className="flex-between" style={{ marginBottom: '1.5rem' }}>
                                <span className="small">Blacklist</span>
                                <span className="small font-mono text-primary">MEME, PERP</span>
                            </div>

                            <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '1rem', borderRadius: '4px', border: '1px dashed var(--accent-danger)' }}>
                                <div className="flex-between">
                                    <span className="tiny text-red font-mono">VIOLATION DETECTED</span>
                                    <span className="tiny text-red font-mono">BLOCKING</span>
                                </div>
                                <p className="tiny" style={{ marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                                    Order size exceeds Volatility Adjusted Position Sizing (VAPS) limit.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* FOOTER */}
            <footer style={{
                marginTop: 'auto',
                borderTop: '1px solid var(--border-color)',
                padding: '3rem 2rem',
                backgroundColor: 'var(--bg-main)'
            }}>
                <div style={{ maxWidth: '1200px', margin: '0 auto', textAlign: 'center', color: 'var(--text-muted)' }}>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginBottom: '2rem', fontSize: '0.9rem' }}>
                        <span>Individual Traders</span>
                        <span>Family Offices</span>
                        <span>Hedge Funds</span>
                        <span>SaaS / White Label</span>
                    </div>
                    <div className="tiny" style={{ opacity: 0.6, lineHeight: 1.6, maxWidth: '800px', margin: '0 auto' }}>
                        <p>LUNIA / ALADDIN is a software provider only. We are not a bank, broker, or investment advisor.</p>
                        <p>We do not hold custody of user funds. All execution occurs on user-connected exchanges.</p>
                        <p>Trading cryptocurrencies involves significant risk. Governed automation tools do not guarantee profits.</p>
                        <p style={{ marginTop: '1rem' }}>&copy; 2025 LUNIA Technologies. All Rights Reserved.</p>
                    </div>
                </div>
            </footer>
        </div>
    );
};
