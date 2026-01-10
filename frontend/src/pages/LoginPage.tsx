import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await login(email, password);
      navigate('/trader');
    } catch (err: any) {
      console.error("Login Error", err);
      // Distinguish errors
      if (err.status === 401 || err.message?.includes('401')) {
        setError("Invalid Credentials. Please verify your institutional access.");
      } else if (err.message?.includes('Failed to fetch') || err.status === 503) {
        setError("Service Unreachable. The Governance Engine may be offline.");
      } else {
        setError("Authentication Failed. " + (err.message || 'Unknown Error'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container center-content" style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <div className="card" style={{ width: '100%', maxWidth: '420px', padding: '0', overflow: 'hidden', border: '1px solid var(--border-color)', boxShadow: '0 4px 24px rgba(0,0,0,0.2)' }}>

        <div style={{ padding: '2.5rem', background: 'linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%)', borderBottom: '1px solid var(--border-color)', textAlign: 'center' }}>
          <h2 style={{ margin: '0 0 0.5rem 0', letterSpacing: '-0.5px' }}>LUNIA</h2>
          <p className="tiny muted uppercase tracking-wide opacity-70">Institutional Trading Engine</p>
        </div>

        <div style={{ padding: '2rem' }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

            {error && (
              <div className="alert error" style={{ fontSize: '0.85rem' }}>
                {error}
              </div>
            )}

            <div>
              <label className="tiny muted uppercase mb-1 block">Identity / Email</label>
              <input
                className="input full-width"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="name@fund.com"
                style={{ padding: '12px' }}
              />
            </div>

            <div>
              <div className="flex-between mb-1">
                <label className="tiny muted uppercase block">Secure Key</label>
              </div>
              <input
                className="input full-width"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                style={{ padding: '12px' }}
              />
            </div>

            <button
              type="submit"
              className="button primary large full-width"
              disabled={loading || !email || !password}
              style={{ marginTop: '1rem' }}
            >
              {loading ? 'AUTHENTICATING...' : 'SECURE LOGIN'}
            </button>
          </form>
        </div>

        <div style={{ padding: '1.5rem', textAlign: 'center', background: 'var(--bg-panel)', borderTop: '1px solid var(--border-color)' }}>
          <span className="muted small">New Partner? </span>
          <Link to="/register" className="text-primary hover-glow" style={{ fontWeight: 600 }}>Request Access</Link>
        </div>
      </div>
    </div>
  );
};
