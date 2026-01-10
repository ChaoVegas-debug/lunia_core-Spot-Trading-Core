import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { isPreviewEnabled } from '../../config/preview';

interface NavItem {
  to: string;
  label: string;
  roles: string[];
  previewOnly?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const sections: NavSection[] = [
  {
    title: 'Trading',
    items: [
      { to: '/trader', label: 'Dashboard', roles: ['TRADER', 'ADMIN'] },
      { to: '/portfolio', label: 'Portfolio', roles: ['TRADER', 'ADMIN'] },
      { to: '/risk', label: 'Risk', roles: ['TRADER', 'ADMIN'] },
      { to: '/strategies', label: 'Strategies', roles: ['TRADER', 'ADMIN'] },
    ]
  },
  {
    title: 'Management',
    items: [
      { to: '/account', label: 'Account', roles: ['USER', 'TRADER', 'FUND', 'ADMIN'] },
      { to: '/exchange-keys', label: 'Exchange Keys', roles: ['TRADER', 'ADMIN'] },
    ]
  },
  {
    title: 'System',
    items: [
      { to: '/fund', label: 'Fund Panel', roles: ['FUND', 'ADMIN'] },
      { to: '/admin', label: 'Admin Panel', roles: ['ADMIN'] },
      { to: '/system', label: 'System status', roles: ['USER', 'TRADER', 'FUND', 'ADMIN'] },
      { to: '/docs', label: 'Docs', roles: ['USER', 'TRADER', 'FUND', 'ADMIN'] }
    ]
  },
  {
    title: 'Preview / Dev',
    items: [
      { to: '/fund', label: 'Fund Ops (Inst)', roles: ['TRADER', 'ADMIN', 'FUND'], previewOnly: true },
      { to: '/preview/surfaces', label: 'UI Gallery', roles: ['TRADER', 'ADMIN', 'FUND', 'USER'], previewOnly: true },
      { to: '/getting-started', label: 'Onboarding', roles: ['TRADER', 'ADMIN', 'FUND', 'USER'], previewOnly: true }
    ]
  }
];

export const Nav: React.FC = () => {
  const { role } = useAuth();
  const location = useLocation();
  const isPreview = isPreviewEnabled();

  return (
    <div className="sidebar">
      {/* Use a clear H3 or Logo here */}
      <h3 style={{
        padding: '0 1rem',
        marginBottom: '1.5rem',
        color: 'white',
        fontWeight: '700',
        fontSize: '1.1rem',
        letterSpacing: '-0.02em'
      }}>
        LUNIA <span style={{ color: 'var(--accent-primary)' }}>TERMINAL</span>
      </h3>

      <nav>
        {sections.map((section) => {
          let visibleItems = section.items.filter(item => {
            if (item.previewOnly && !isPreview) return false;
            // In Preview Mode, allow viewing if role matches OR if it's a generally accessible preview page
            if (isPreview && item.previewOnly) return true;
            return item.roles.includes(role);
          });

          if (visibleItems.length === 0) return null;

          return (
            <div key={section.title} className="nav-section">
              <div className="nav-section-title">{section.title}</div>
              {visibleItems.map(item => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`nav-link ${location.pathname === item.to ? 'active' : ''}`}
                >
                  {/* Icon placeholder could go here */}
                  {item.label}
                </Link>
              ))}
            </div>
          );
        })}
      </nav>
    </div>
  );
};
