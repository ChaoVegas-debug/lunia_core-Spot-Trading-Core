import React, { useState } from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHedgingConfig, setHedgingConfig } from '../../api/adapter';
import { HedgingConfig } from '../../api/types';

export const HedgingPanel: React.FC = () => {
    const { data, refresh } = usePolledResource(getHedgingConfig, 5000);
    const [updating, setUpdating] = useState(false);

    const handleToggle = async (enabled: boolean) => {
        setUpdating(true);
        await setHedgingConfig({ enabled });
        refresh();
        setUpdating(false);
    };

    const config = data as HedgingConfig || { enabled: false, strategy_type: 'DELTA_NEUTRAL' };

    return (
        <div className="card" style={{ borderLeft: '3px solid #f59e0b' }}>
            <div className="card-header flex-between">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '1.2rem' }}>🛡️</span>
                    <h3>Hedging Core</h3>
                </div>
                <label className="switch">
                    <input
                        type="checkbox"
                        checked={config.enabled}
                        onChange={(e) => handleToggle(e.target.checked)}
                        disabled={updating}
                    />
                    <span className="slider"></span>
                </label>
            </div>

            <div style={{ opacity: config.enabled ? 1 : 0.5, transition: 'opacity 0.3s' }}>
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

                {config.recommended_action && config.enabled && (
                    <div style={{ marginTop: '12px', padding: '8px', border: '1px solid var(--accent-warning)', borderRadius: '4px', color: 'var(--accent-warning)' }}>
                        <div className="tiny uppercase" style={{ opacity: 0.8 }}>AI Recommendation</div>
                        <div style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{config.recommended_action}</div>
                    </div>
                )}
            </div>
        </div>
    );
};
