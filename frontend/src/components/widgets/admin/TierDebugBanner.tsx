import React from 'react';
import { useAuth } from "../../../hooks/useAuth";
import { getPlan } from "../../../domain/subscription/plans";

const FEATURE_AUTO_BETA = import.meta.env.VITE_FRONTEND_FEATURE_AUTO_BETA_FOR_ALL === '1';

export const TierDebugBanner: React.FC = () => {
    const { user, role } = useAuth();

    // Only show for ADMIN/OPS or maybe just ADMIN
    if (role !== 'ADMIN') return null;

    const plan = getPlan(user?.tier);

    return (
        <div style={{
            background: '#1a1a1a',
            borderBottom: '1px solid #333',
            color: '#666',
            fontSize: '0.7rem',
            padding: '4px 12px',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            gap: '12px',
            fontFamily: 'monospace'
        }}>
            <span>ADMIN_DEBUG</span>
            <span style={{ color: '#888' }}>|</span>
            <span>TIER: <strong style={{ color: '#fff' }}>{plan.name.toUpperCase()}</strong> ({user?.tier})</span>
            <span style={{ color: '#888' }}>|</span>
            <span>AUTO_BETA: <strong style={{ color: FEATURE_AUTO_BETA ? '#4ade80' : '#f87171' }}>{FEATURE_AUTO_BETA ? 'ON' : 'OFF'}</strong></span>
            <span style={{ color: '#888' }}>|</span>
            <span>AUTO_ALLOWED: <strong style={{ color: plan.auto_allowed ? '#4ade80' : '#f87171' }}>{String(plan.auto_allowed).toUpperCase()}</strong></span>
        </div>
    );
};
