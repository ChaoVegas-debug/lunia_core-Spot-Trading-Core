import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useOnboarding } from '../hooks/useOnboarding';

export const OnboardingPage: React.FC = () => {
    const navigate = useNavigate();
    const { step, setStep, complete } = useOnboarding();

    const totalSteps = 4;

    const nextStep = () => {
        if (step < totalSteps) {
            setStep(step + 1);
        } else {
            // FINISH
            complete();
            navigate('/trader');
        }
    };

    const prevStep = () => {
        if (step > 1) {
            setStep(step - 1);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'var(--bg-main)',
            color: 'var(--text-primary)'
        }}>
            <div className="card" style={{ maxWidth: '800px', width: '100%', padding: '0', overflow: 'hidden' }}>

                {/* PROGRESS BAR */}
                <div style={{ background: 'var(--bg-panel-soft)', height: '4px', width: '100%' }}>
                    <div style={{
                        height: '100%',
                        width: `${(step / totalSteps) * 100}%`,
                        background: 'var(--accent-primary)',
                        transition: 'width 0.3s ease'
                    }} />
                </div>

                <div style={{ padding: '3rem' }}>

                    {/* STEP 1: WELCOME */}
                    {step === 1 && (
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>👋</div>
                            <h1 style={{ marginBottom: '1rem' }}>Welcome to Governed Trading</h1>
                            <p className="muted" style={{ fontSize: '1.1rem', lineHeight: 1.6, maxWidth: '600px', margin: '0 auto' }}>
                                You are entering a high-governance environment.
                                Before we begin, you must understand that safety and risk control take precedence over speed and automation.
                            </p>
                        </div>
                    )}

                    {/* STEP 2: WHY LOCKED */}
                    {step === 2 && (
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔒</div>
                            <h1 style={{ marginBottom: '1rem' }}>Why Automation is Locked</h1>
                            <p className="muted" style={{ fontSize: '1.1rem', lineHeight: 1.6, maxWidth: '600px', margin: '0 auto 2rem' }}>
                                Full automation (Black Box) is restricted by default. Access is earned through:
                            </p>
                            <div className="grid" style={{ textAlign: 'left', background: 'var(--bg-panel-soft)', padding: '1.5rem', borderRadius: '8px' }}>
                                <div className="flex-between">
                                    <span>1. Verified Identity</span>
                                    <span className="text-green">✔ Complete</span>
                                </div>
                                <div className="flex-between">
                                    <span>2. Capital Definition</span>
                                    <span className="text-warn">⚠ Pending</span>
                                </div>
                                <div className="flex-between">
                                    <span>3. Risk Profile Setup</span>
                                    <span className="text-warn">⚠ Pending</span>
                                </div>
                                <div className="flex-between">
                                    <span>4. 30 Days of Governance Compliance</span>
                                    <span className="muted"> Locked</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* STEP 3: MODES EXPLAINED */}
                    {step === 3 && (
                        <div>
                            <h1 style={{ textAlign: 'center', marginBottom: '2rem' }}>Operating Modes</h1>
                            <div className="grid cols-3" style={{ gap: '1rem' }}>
                                <div className="card subtle" style={{ padding: '1rem' }}>
                                    <h3 style={{ marginBottom: '0.5rem' }}>MANUAL</h3>
                                    <p className="tiny muted">You execute trades. System monitors risk and provides AI intel.</p>
                                </div>
                                <div className="card subtle" style={{ padding: '1rem', border: '1px solid var(--accent-primary)' }}>
                                    <h3 style={{ marginBottom: '0.5rem', color: 'var(--accent-primary)' }}>SEMI-AUTO</h3>
                                    <p className="tiny muted">AI proposes trades. You review and approve. Recommended for starting.</p>
                                </div>
                                <div className="card subtle" style={{ padding: '1rem', opacity: 0.5 }}>
                                    <h3 style={{ marginBottom: '0.5rem' }}>AUTO</h3>
                                    <p className="tiny muted">Fully autonomous. Locked until governance requirements are met.</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* STEP 4: SETUP TASKS */}
                    {step === 4 && (
                        <div>
                            <h1 style={{ textAlign: 'center', marginBottom: '1rem' }}>Required Setup</h1>
                            <p className="muted" style={{ textAlign: 'center', marginBottom: '2rem' }}>
                                To activate your dashboard, you must complete the following configuration steps in your Personal Cabinet:
                            </p>

                            <div className="grid" style={{ gap: '1rem' }}>
                                <div className="card" style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                    <div style={{ background: 'var(--bg-panel-soft)', padding: '0.5rem', borderRadius: '4px', fontSize: '1.5rem' }}>🔗</div>
                                    <div>
                                        <h3 style={{ margin: 0 }}>Connect Exchange</h3>
                                        <p className="tiny muted">Link Binance, Bybit, or OKX via Read-Only API initially.</p>
                                    </div>
                                </div>
                                <div className="card" style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                    <div style={{ background: 'var(--bg-panel-soft)', padding: '0.5rem', borderRadius: '4px', fontSize: '1.5rem' }}>💰</div>
                                    <div>
                                        <h3 style={{ margin: 0 }}>Define Capital Cap</h3>
                                        <p className="tiny muted">Set the maximum USD amount the system is allowed to touch.</p>
                                    </div>
                                </div>
                                <div className="card" style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                    <div style={{ background: 'var(--bg-panel-soft)', padding: '0.5rem', borderRadius: '4px', fontSize: '1.5rem' }}>🛡</div>
                                    <div>
                                        <h3 style={{ margin: 0 }}>Select Risk Profile</h3>
                                        <p className="tiny muted">Choose between Conservative, Balanced, or Aggressive boundaries.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ACTIONS */}
                    <div style={{ marginTop: '3rem', display: 'flex', justifyContent: 'space-between' }}>
                        <button
                            className="button"
                            onClick={prevStep}
                            disabled={step === 1}
                            style={{ opacity: step === 1 ? 0 : 1 }}
                        >
                            Back
                        </button>
                        <button
                            className="button primary"
                            onClick={nextStep}
                        >
                            {step === totalSteps ? 'Enter Dashboard' : 'Next'}
                        </button>
                    </div>

                </div>
            </div>
        </div>
    );
};
