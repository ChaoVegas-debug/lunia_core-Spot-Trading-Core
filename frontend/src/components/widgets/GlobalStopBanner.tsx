import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getOpsState } from '../../api/adapter';
import type { OpsState } from '../../api/types';

export const GlobalStopBanner: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };
    const ops = usePolledResource<OpsState>((signal) => getOpsState(signal, client), 2000, [auth.role]);

    if (!ops.data?.global_stop) return null;

    return (
        <div style={{
            background: 'var(--accent-danger)',
            color: '#fff',
            padding: '12px 24px',
            textAlign: 'center',
            fontWeight: 'bold',
            fontSize: '1.2em',
            letterSpacing: '1px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
            animation: 'pulse 2s infinite',
            marginBottom: '16px',
            border: '2px solid #fff'
        }}>
            ⚠️ GLOBAL STOP ENGAGED — EXECUTION HALTED ⚠️
        </div>
    );
};
