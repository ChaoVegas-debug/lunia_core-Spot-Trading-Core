import React, { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getSystemEvents } from '../../api/adapter';
import type { SystemEvent } from '../../api/types';

export const SystemFeedWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken, bearerToken: auth.bearerToken };
    const { data, error, refresh } = usePoller<{ items: SystemEvent[] }>({
        key: 'data_SystemFeedWidget',
        endpoint: '/api/events/system',
        fetcher: () => getSystemEvents(new AbortController().signal, client),
        interval_ms: 3000,
        critical: false
    });
    const loading = false;
    const lastUpdated = undefined;

    const messages = data?.items?.slice().reverse().slice(0, 5) || [];

    return (
        <div className="card subtle" style={{ padding: '12px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--accent-primary-dim)' }}>
            <div className="flex-between mb-2">
                <span className="tiny uppercase muted tracking-wide">System Feed (Real-time)</span>
                <span className={`status-dot pulse ${messages.length > 0 ? 'ok' : 'muted'}`}></span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minHeight: '80px' }}>
                {messages.length === 0 && (
                    <div className="tiny muted text-mono opacity-50">Waiting for live signals...</div>
                )}
                {messages.map((evt, idx) => (
                    <div key={evt.id || idx} className="tiny text-mono" style={{
                        opacity: 1 - (idx * 0.15),
                        color: idx === 0 ? 'var(--text-primary)' : 'var(--text-muted)',
                        borderLeft: idx === 0 ? '2px solid var(--accent-primary)' : '2px solid transparent',
                        paddingLeft: '8px'
                    }}>
                        <span className="muted">{new Date(evt.timestamp).toLocaleTimeString()}</span>{' '}
                        <span className="text-accent">{evt.type}</span>{' '}
                        {JSON.stringify(evt.payload).substring(0, 40)}...
                    </div>
                ))}
            </div>
        </div>
    );
};
