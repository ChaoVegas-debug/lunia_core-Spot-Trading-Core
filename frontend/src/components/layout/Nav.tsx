import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useBranding } from '../../hooks/useBranding';

const links = [
  { to: '/user', label: 'User Console', roles: ['USER', 'TRADER', 'FUND', 'ADMIN'] },
  { to: '/trader', label: 'Trader Panel', roles: ['TRADER', 'ADMIN'] },
  { to: '/fund', label: 'Fund Panel', roles: ['FUND', 'ADMIN'] },
  { to: '/admin', label: 'Admin Panel', roles: ['ADMIN'] },
  { to: '/system', label: 'System', roles: ['USER', 'TRADER', 'FUND', 'ADMIN'] },
  { to: '/docs', label: 'Docs', roles: ['USER', 'TRADER', 'FUND', 'ADMIN'] }
];

export const Nav: React.FC = () => {
  const { role } = useAuth();
  const { branding } = useBranding();
  const location = useLocation();

  return (
    <div className="sidebar">
      <h2>{branding.brand_name}</h2>
      {branding.tenant_id && <div className="small muted">Tenant: {branding.tenant_id}</div>}
      <nav>
        {links
          .filter((link) => link.roles.includes(role))
          .map((link) => (
            <Link
              key={link.to}
              to={link.to}
              style={{
                padding: '0.5rem 0.75rem',
                borderRadius: 6,
                background: location.pathname === link.to ? '#1f2937' : 'transparent',
                color: '#e2e8f0'
              }}
            >
              {link.label}
            </Link>
          ))}
      </nav>
      <div className="role">Role: {role}</div>
    </div>
  );
};
