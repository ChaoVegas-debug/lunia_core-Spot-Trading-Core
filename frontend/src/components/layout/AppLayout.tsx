import React from 'react';
import { Outlet } from 'react-router-dom';
import { Nav } from './Nav';
import { StatusStrip } from './StatusStrip';
import { useAuth } from '../../hooks/useAuth';
import { apiBaseUrl } from '../../api/client';

const buildInfo = import.meta.env.VITE_APP_BUILD || 'dev';

export const AppLayout: React.FC = () => {
  const { logout, role } = useAuth();
  return (
    <div className="layout">
      <StatusStrip />
      <Nav />
      <div className="content">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <div className="small">Current role: {role}</div>
          <button className="button secondary" onClick={logout}>
            Logout
          </button>
        </div>
        <Outlet />
        <footer className="footer">
          <span className="small">Build: {buildInfo}</span>
          <span className="small">API: {apiBaseUrl()}</span>
        </footer>
      </div>
    </div>
  );
};
