import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { postSeedDemo } from '../api/adapter';
import { useAuth } from '../hooks/useAuth';

export const RegisterPage: React.FC = () => {
    const navigate = useNavigate();
    const { login } = useAuth();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const isDemo = import.meta.env.VITE_DEMO_MODE === '1';

    const handleDemoProvision = async () => {
        if (!confirm("Provision a new Demo Environment?\n\nThis will reset the demo state and create a temporary Admin user.")) return;

        setLoading(true);
        setError(null);
        try {
            const controller = new AbortController();
            // postSeedDemo uses a hardcoded dev token internally for the request
            const res = await postSeedDemo(controller.signal);
            console.log("Demo Seed Result:", res);

            const demoEmail = res?.email || 'admin@lunia.fi';
            const demoPass = res?.password || 'admin123';

            // Auto-Login
            const user = await login(demoEmail, demoPass);

            if (user) {
                // AUTO-COMPLETE ONBOARDING for Demo Users
                const STORAGE_KEY = `LUNIA_ONBOARDING_${user.id}`;
                localStorage.setItem(STORAGE_KEY, JSON.stringify({
                    step: 4,
                    status: 'COMPLETED'
                }));
                navigate('/trader');
            } else {
                // Fallback if user fetch failed but login succeeded? Unlikely.
                navigate('/onboarding');
            }

        } catch (err: any) {
            console.error("Provision Failed", err);
            setError("Failed to provision demo environment. Backend usage requires valid Ops Token.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="page-container center-content" style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
            <div className="card" style={{ width: '100%', maxWidth: '480px', padding: '0', overflow: 'hidden', border: '1px solid var(--border-color)' }}>

                {/* Header */}
                <div style={{ padding: '2rem', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)', textAlign: 'center' }}>
                    <h2 style={{ margin: '0 0 0.5rem 0' }}>LUNIA</h2>
                    <p className="small muted uppercase tracking-wide">Institutional Governance</p>
                </div>

                {/* Content */}
                <div style={{ padding: '2rem' }}>

                    <div className="alert info" style={{ marginBottom: '2rem' }}>
                        <strong>Access Restricted</strong>
                        <p className="small" style={{ margin: '0.5rem 0 0 0' }}>
                            Registration for LUNIA is currently by invitation only for qualified institutional partners.
                        </p>
                    </div>

                    {isDemo ? (
                        <div style={{ textAlign: 'center' }}>
                            <div className="badge warning large mb-2">DEMO / EVALUATION MODE</div>
                            <p className="muted small mb-4">
                                You are running in Evaluation Mode. You can provision a temporary isolated environment.
                            </p>

                            {error && <div className="alert error mb-4">{error}</div>}

                            <button
                                className="button primary full-width large"
                                onClick={handleDemoProvision}
                                disabled={loading}
                            >
                                {loading ? 'PROVISIONING...' : 'LAUNCH DEMO ENVIRONMENT'}
                            </button>
                            <p className="tiny muted mt-2">Resets database state.</p>
                        </div>
                    ) : (
                        <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                            <p className="muted mb-4">
                                Please contact your Account Manager or the Governance Committee to request access credentials.
                            </p>
                            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                                <a href="mailto:governance@lunia.fi" className="button secondary">Contact Sales</a>
                            </div>
                        </div>
                    )}

                </div>

                {/* Footer */}
                <div style={{ padding: '1.5rem', background: 'var(--bg-panel)', borderTop: '1px solid var(--border-color)', textAlign: 'center' }}>
                    <span className="muted small">Already have Access? </span>
                    <Link to="/login" className="text-primary hover-glow" style={{ fontWeight: 600 }}>Login Securely</Link>
                </div>

            </div>
        </div>
    );
};
