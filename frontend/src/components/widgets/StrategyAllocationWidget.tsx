import React, { useEffect, useCallback } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getStrategyAllocations, updateStrategyAllocation, updateStrategies } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';
import { StrategyAllocationRow } from '../../api/types';
import { WidgetWrapper } from '../common/WidgetWrapper';
import { useOptimisticSlider } from '../../hooks/useOptimisticSlider';
import { useOptimisticToggle } from '../../hooks/useOptimisticToggle';
import { useDashboard } from '../../context/DashboardContext';

// Individual strategy row with optimistic controls
const StrategyRow: React.FC<{
    row: StrategyAllocationRow;
    onAllocUpdate: (id: string, pct: number) => Promise<void>;
    onToggle: (id: string, enabled: boolean) => Promise<void>;
    onError: (msg: string) => void;
}> = ({ row, onAllocUpdate, onToggle, onError }) => {
    // Optimistic slider for allocation %
    const slider = useOptimisticSlider({
        initialValue: row.target_alloc_pct,
        onCommit: async (val) => {
            await onAllocUpdate(row.id, val);
        }
    });

    // Optimistic toggle for enabled state
    const toggle = useOptimisticToggle({
        initialValue: row.enabled,
        onToggle: async (enabled) => {
            await onToggle(row.id, enabled);
        },
        onError: (err) => onError(`Failed to toggle ${row.name}: ${err.message}`)
    });

    // Sync with polling updates when not actively editing
    useEffect(() => {
        slider.syncValue(row.target_alloc_pct);
        toggle.syncValue(row.enabled);
    }, [row.target_alloc_pct, row.enabled, slider.syncValue, toggle.syncValue]);

    return (
        <tr style={{ borderBottom: '1px solid #222', opacity: toggle.value ? 1 : 0.5 }}>
            <td style={{ padding: '8px' }}>
                <div style={{ fontWeight: 600 }}>{row.name}</div>
                <div className="tiny muted">{row.core} • {row.horizon}</div>
            </td>
            <td>
                <span className="tiny font-mono" style={{
                    color: row.control_mode === 'AI' ? 'var(--accent-primary)' : '#fff'
                }}>{row.control_mode}</span>
            </td>
            <td style={{ textAlign: 'center' }}>
                <span className={`badge tiny ${row.priority === 'HIGH' ? 'danger' : 'secondary'}`}>
                    {row.priority}
                </span>
            </td>
            <td style={{ textAlign: 'center', width: '25%' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                        type="range"
                        min="0" max="100"
                        value={slider.localValue * 100}
                        className="slider-institutional"
                        style={{ flex: 1 }}
                        onChange={(e) => slider.handleChange(parseInt(e.target.value) / 100)}
                        onMouseUp={slider.handleCommit}
                        onTouchEnd={slider.handleCommit}
                    />
                    <span className="tiny font-mono" style={{ minWidth: '40px' }}>
                        {slider.isSaving ? '…' : `${(slider.localValue * 100).toFixed(0)}%`}
                    </span>
                </div>
            </td>
            <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                ${(row.current_alloc_pct * 1000000).toLocaleString()}
            </td>
            <td style={{ textAlign: 'right' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px' }}>
                    {toggle.isPending && <span className="tiny muted">…</span>}
                    <label className="switch">
                        <input
                            type="checkbox"
                            checked={toggle.value}
                            onChange={toggle.handleToggle}
                        />
                        <span className="slider"></span>
                    </label>
                </div>
            </td>
        </tr>
    );
};

export const StrategyAllocationWidget: React.FC = () => {
    const auth = useAuth();
    const { addToast } = useDashboard();
    const { data, error } = usePoller({
        key: 'strategy_allocations',
        endpoint: '/api/strategy/allocations',
        fetcher: () => getStrategyAllocations(new AbortController().signal),
        interval_ms: 3000,
        critical: false
    });
    const loading = false;

    // Memoized handlers to prevent re-renders
    const handleAllocUpdate = useCallback(async (id: string, pct: number) => {
        await updateStrategyAllocation(id, pct);
    }, []);

    const handleToggle = useCallback(async (id: string, enabled: boolean) => {
        await updateStrategies([{ id, enabled }], new AbortController().signal);
    }, []);

    const handleError = useCallback((msg: string) => {
        addToast({ type: 'ERROR', message: msg });
    }, [addToast]);

    // Defensive guard: ensure data is always an array
    const safeData = Array.isArray(data) ? data : [];

    return (
        <WidgetWrapper
            id="StrategyAllocationWidget"
            title="Strategy Allocation"
            rightElem={<div className="small muted">Global Risk Budget</div>}
            loading={loading}
            error={error}
        >
            <div className="table-container institutional-table">
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                        <tr style={{ borderBottom: '1px solid #333', color: '#888' }}>
                            <th style={{ textAlign: 'left', padding: '8px' }}>Strategy Core</th>
                            <th style={{ textAlign: 'left' }}>Mode</th>
                            <th style={{ textAlign: 'center' }}>Priority</th>
                            <th style={{ textAlign: 'center' }}>% Alloc</th>
                            <th style={{ textAlign: 'right' }}>Active Cap</th>
                            <th style={{ textAlign: 'right' }}>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {safeData.length === 0 && !loading && !error ? (
                            <tr>
                                <td colSpan={6} style={{ padding: '1rem', textAlign: 'center', color: '#666' }}>
                                    No strategy allocations configured
                                </td>
                            </tr>
                        ) : (
                            safeData.map((row: StrategyAllocationRow) => (
                                <StrategyRow
                                    key={row.id}
                                    row={row}
                                    onAllocUpdate={handleAllocUpdate}
                                    onToggle={handleToggle}
                                    onError={handleError}
                                />
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </WidgetWrapper>
    );
};
