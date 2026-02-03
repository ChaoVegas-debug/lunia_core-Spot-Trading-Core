import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getHealth, getOpsState } from '../../api/adapter';
import { DataStatus } from '../common/DataStatus';
import { useWidgetRegistry } from '../../context/WidgetRegistryContext';

export const DiagnosticsPanel: React.FC = () => {
    const auth = useAuth();
    const { widgets } = useWidgetRegistry();
    const client = { role: auth.role, opsToken: auth.opsToken };
    const { data: healthData, error: healthError, refresh: healthRefresh } = usePoller({
        key: 'health_DiagnosticsPanel',
        endpoint: '/api/health',
        fetcher: () => getHealth(new AbortController().signal, client),
        interval_ms: 5000,
        critical: true
    });
    const health = { data: healthData, error: healthError, loading: false, refresh: healthRefresh };
    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller({
        key: 'ops_DiagnosticsPanel',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 5000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

    const debugInfo = (health.data as any)?.debug || {};
    const binanceState = debugInfo.binance || {};

    return (
        <div className="card" style={{ background: '#1a0505', border: '1px solid #421' }}>
            <div className="card-header">
                <h3>🐞 UI Surface Diagnostics</h3>
                <DataStatus loading={health.loading} error={health.error} lastUpdated={health.lastUpdated} />
            </div>

            <div className="grid cols-3 gap-4" style={{ padding: '16px', fontSize: '11px', fontFamily: 'monospace' }}>
                {/* 1. AUTH PROVEN STATE */}
                <div>
                    <h4 style={{ color: '#aaa', marginBottom: '8px' }}>AUTH STATE</h4>
                    <div style={{
                        padding: '8px',
                        background: binanceState.auth_proven === 'VERIFIED' ? '#0f3311' : '#330f0f',
                        border: '1px solid currentColor',
                        color: binanceState.auth_proven === 'VERIFIED' ? '#4f4' : '#f44',
                        fontWeight: 'bold'
                    }}>
                        {binanceState.auth_proven || "UNKNOWN"}
                    </div>
                </div>

                {/* 2. MODE STATE */}
                <div>
                    <h4 style={{ color: '#aaa', marginBottom: '8px' }}>SYSTEM MODE</h4>
                    <div>MOCK: {String(binanceState.mock)}</div>
                    <div>NET : {binanceState.is_testnet ? "TESTNET" : "MAINNET"}</div>
                    <div>ROLE: {auth.role}</div>
                </div>

                {/* 3. KEY STATUS */}
                <div>
                    <h4 style={{ color: '#aaa', marginBottom: '8px' }}>KEY FORENSICS</h4>
                    <div>Key Len: {binanceState.key_len}</div>
                    <div>Sec Len: {binanceState.secret_len}</div>
                    <div>Source: {debugInfo.credentials_source || "?"}</div>
                </div>
            </div>

            <div style={{ padding: '16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                <h4 style={{ color: '#aaa', margin: '0 0 8px 0' }}>WIDGET VISIBILITY MAP</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '8px' }}>
                    {Object.values(widgets).map(w => (
                        <div key={w.id} className={`status-chip ${w.status === 'OK' ? 'ok' : w.status === 'BLOCKED' ? 'danger' : 'warn'}`}
                            title={w.reason}
                        >
                            <span style={{ fontWeight: 'bold' }}>{w.id}</span>
                            <span style={{ marginLeft: '4px', fontSize: '0.8em', opacity: 0.7 }}>
                                {w.status}
                            </span>
                        </div>
                    ))}
                    {Object.keys(widgets).length === 0 && (
                        <div className="tiny muted">No widgets registered yet.</div>
                    )}
                </div>
            </div>
        </div>
    );
};
