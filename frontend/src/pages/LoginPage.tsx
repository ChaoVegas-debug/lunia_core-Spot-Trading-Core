import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import type { Role } from '../api/types';
import { useBranding } from '../hooks/useBranding';

const roles: Role[] = ['USER', 'TRADER', 'FUND', 'ADMIN'];

export const LoginPage: React.FC = () => {
  const { setAuth, login } = useAuth();
  const { branding, loading, error } = useBranding();
  const [role, setRole] = useState<Role>('USER');
  const [adminToken, setAdminToken] = useState('');
  const [opsToken, setOpsToken] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      if (email && password) {
        await login(email, password);
        setAuth((prev) => ({ ...prev, adminToken: adminToken || undefined, opsToken: opsToken || undefined }));
        navigate('/system');
      } else {
        setAuth({ role, adminToken: adminToken || undefined, opsToken: opsToken || undefined });
        navigate(role === 'USER' ? '/user' : `/${role.toLowerCase()}`);
      }
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div style={{ maxWidth: 420, margin: '2rem auto' }}>
      <h2>{branding.brand_name}</h2>
      <div className="small muted">{branding.support_email || 'Support contact pending'}</div>
      <h3>Login / Role Selection</h3>
      <form onSubmit={submit}>
        {loading && <div className="small">Loading branding...</div>}
        {error && <div className="alert warn">Branding fallback in use.</div>}
        <div className="form-control">
          <label>Email (for JWT login)</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" />
        </div>
        <div className="form-control">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••" />
        </div>
        <div className="form-control">
          <label>Role (fallback when no JWT)</label>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {roles.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div className="form-control">
          <label>X-Admin-Token (optional, required for admin controls)</label>
          <input value={adminToken} onChange={(e) => setAdminToken(e.target.value)} placeholder="admin token" />
        </div>
        <div className="form-control">
          <label>X-OPS-TOKEN (optional, arbitrage controls)</label>
          <input value={opsToken} onChange={(e) => setOpsToken(e.target.value)} placeholder="ops token" />
        </div>
        {error && <div className="alert">Login failed: {error}</div>}
        <button className="button" type="submit">
          Continue
        </button>
      </form>
    </div>
  );
};
