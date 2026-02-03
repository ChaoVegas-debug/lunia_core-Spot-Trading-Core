import React, { useEffect, useMemo, useCallback } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getExchangeAllocations, updateExchangeRiskLimit, updateExchangeEnabled } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';
import { ExchangeAllocationRow } from '../../api/types';
import { WidgetWrapper } from '../common/WidgetWrapper';
import { useOptimisticSlider } from '../../hooks/useOptimisticSlider';
import { useOptimisticToggle } from '../../hooks/useOptimisticToggle';
import { useDashboard } from '../../context/DashboardContext';

// Individual exchange card with optimistic controls
const ExchangeCard: React.FC<{
    exch: ExchangeAllocationRow;
    onRiskUpdate: (id: string, val: number) => Promise<void>;
    onToggle: (id: string, enabled: boolean) => Promise<void>;
    onError: (msg: string) => void;
}> = ({ exch, onRiskUpdate, onToggle, onError }) => {
    // Optimistic slider for risk limit
    const slider = useOptimisticSlider({
        initialValue: exch.risk_limit_pct,
        onCommit: async (val) => {
            await onRiskUpdate(exch.id, val);
        }
    });

    // Optimistic toggle for enabled state
    const toggle = useOptimisticToggle({
        initialValue: exch.enabled,
        onToggle: async (enabled) => {
            await onToggle(exch.id, enabled);
        },
        onError: (err) => onError(`Failed to toggle ${exch.name}: ${err.message}`)
    });

    // Sync with polling updates when not actively editing
    useEffect(() => {
        slider.syncValue(exch.risk_limit_pct);
        toggle.syncValue(exch.enabled);
    }, [exch.risk_limit_pct, exch.enabled, slider.syncValue, toggle.syncValue]);

    return (
        <div style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.05)',
            padding: '12px',
            borderRadius: '4px'
        }}>
            <div className="flex-between mb-2">
                <div style={{ fontWeight: 'bold' }}>{exch.name}</div>
                <span className={`tiny badge ${exch.connected ? 'success' : 'danger'}`}>
                    {exch.connected ? 'CONN' : 'ERR'}
                </span>
            </div>

            <div className="flex-between tiny muted mb-1">
                <span>Balance</span>
                <span className="font-mono text-white">${exch.total_balance_usd.toLocaleString()}</span>
            </div>

            <div className="flex-between tiny muted mb-1">
                <span>Risk Limit {slider.isSaving && <span style={{ color: 'var(--accent-warning)' }}>(Saving…)</span>}</span>
                <span className="font-mono text-warning">{(slider.localValue * 100).toFixed(0)}%</span>
            </div>
            <input
                type="range"
                min="0" max="100"
                value={slider.localValue * 100}
                className="slider-institutional"
                style={{ width: '100%', marginBottom: '8px' }}
                onChange={(e) => slider.handleChange(parseInt(e.target.value) / 100)}
                onMouseUp={slider.handleCommit}
                onTouchEnd={slider.handleCommit}
            />

            <div style={{ marginTop: '8px' }}>
                <div className="tiny muted mb-1">Usage {(exch.usage_pct * 100).toFixed(0)}%</div>
                <div style={{ height: '4px', background: '#222', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{
                        width: `${(exch.usage_pct / exch.risk_limit_pct) * 100}%`,
                        height: '100%',
                        background: exch.usage_pct > exch.risk_limit_pct ? 'var(--accent-danger)' : 'var(--accent-primary)'
                    }} />
                </div>
            </div>

            <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '8px' }}>
                {toggle.isPending && <span className="tiny muted">Saving…</span>}
                <label className="switch tiny-switch">
                    <input
                        type="checkbox"
                        checked={toggle.value}
                        onChange={toggle.handleToggle}
                    />
                    <span className="slider"></span>
                </label>
            </div>
        </div>
    );
};

export const ExchangeAllocationWidget: React.FC = () => {
    const auth = useAuth();
    const { addToast } = useDashboard();
    const { data, error } = usePoller({
        key: 'exchange_allocations',
        endpoint: '/api/exchange/allocations',
        fetcher: () => getExchangeAllocations(),
        interval_ms: 5000,
        critical: false
    });
    const loading = false;

    // Memoized handlers to prevent re-renders
    const handleRiskUpdate = useCallback(async (id: string, val: number) => {
        await updateExchangeRiskLimit(id, val);
    }, []);

    const handleToggle = useCallback(async (id: string, enabled: boolean) => {
        await updateExchangeEnabled(id, enabled);
    }, []);

    const handleError = useCallback((msg: string) => {
        addToast({ type: 'ERROR', message: msg });
    }, [addToast]);

    return (
        <WidgetWrapper
            id="ExchangeAllocationWidget"
            title="Exchange Risk & Capital"
            loading={loading}
            error={error}
        >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                {data?.map((exch: ExchangeAllocationRow) => (
                    <ExchangeCard
                        key={exch.id}
                        exch={exch}
                        onRiskUpdate={handleRiskUpdate}
                        onToggle={handleToggle}
                        onError={handleError}
                    />
                ))}
            </div>
        </WidgetWrapper>
    );
};
