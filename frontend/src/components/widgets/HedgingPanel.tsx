import React, { useEffect } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getHedgingConfig, setHedgingConfig } from '../../api/adapter';
import { HedgingConfig } from '../../api/types';
import { WidgetWrapper } from '../common/WidgetWrapper';
import { useOptimisticToggle } from '../../hooks/useOptimisticToggle';
import { useDashboard } from '../../context/DashboardContext';

export const HedgingPanel: React.FC = () => {
    const { data, error } = usePoller({
        key: 'hedging_config',
        endpoint: '/api/hedging/config',
        fetcher: () => getHedgingConfig(),
        interval_ms: 5000,
        critical: false
    });
    const loading = false;
    const { addToast } = useDashboard();

    const config = data as HedgingConfig || { enabled: false, strategy_type: 'DELTA_NEUTRAL' };

    // Optimistic toggle for hedging enabled state
    const toggle = useOptimisticToggle({
        initialValue: config.enabled,
        onToggle: async (enabled) => {
            await setHedgingConfig({ enabled });
        },
        onError: (err) => addToast({ type: 'ERROR', message: `Failed to toggle hedging: ${err.message}` })
    });

    // Sync with polling updates
    useEffect(() => {
        toggle.syncValue(config.enabled);
    }, [config.enabled, toggle.syncValue]);

    return (
        <WidgetWrapper id="HedgingPanel" title="Hedging Core" loading={loading} error={error}
            rightElem={
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {toggle.isPending && <span className="tiny muted">Saving…</span>}
                    <label className="switch">
                        <input
                            type="checkbox"
                            checked={toggle.value}
                            onChange={toggle.handleToggle}
                        />
                        <span className="slider"></span>
                    </label>
                </div>
            }
        >
            <div style={{ opacity: toggle.value ? 1 : 0.5, transition: 'opacity 0.3s' }}>
                <div className="flex-between mb-2" style={{ padding: '8px', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
                    <span className="small muted">Mode</span>
                    <strong className="text-warning">{config.strategy_type.replace('_', ' ')}</strong>
                </div>

                <div className="mb-2">
                    <div className="flex-between tiny muted mb-1">
                        <span>Portfolio Coverage</span>
                        <span>{((config.coverage_pct || 0) * 100).toFixed(0)}%</span>
                    </div>
                    <input
                        type="range"
                        className="slider-institutional"
                        style={{ width: '100%' }}
                        value={(config.coverage_pct || 0) * 100}
                        readOnly
                    />
                </div>

                {config.recommended_action && toggle.value && (
                    <div style={{ marginTop: '12px', padding: '8px', border: '1px solid var(--accent-warning)', borderRadius: '4px', color: 'var(--accent-warning)' }}>
                        <div className="tiny uppercase" style={{ opacity: 0.8 }}>AI Recommendation</div>
                        <div style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{config.recommended_action}</div>
                    </div>
                )}
            </div>
        </WidgetWrapper>
    );
};
