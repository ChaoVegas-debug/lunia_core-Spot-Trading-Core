/**
 * ALLOCATION CONTROLS WIDGET
 * 
 * Capital allocation sliders per strategy.
 * Changes route through Airlock (capital distribution affects risk).
 * 
 * If backend missing: Allow draft UI but show DATA_NOT_CONNECTED on commit.
 */

import React, { useState } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import { useAirlock } from '../../hooks/useAirlock';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

interface Allocation {
    strategy_id: string;
    strategy_name: string;
    allocation_pct: number;
}

interface AllocationsResponse {
    allocations: Allocation[];
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL
const generateMockAllocations = (): AllocationsResponse => {
    return {
        allocations: [
            { strategy_id: 'strat_001', strategy_name: 'momentum_trend_v2', allocation_pct: 40 },
            { strategy_id: 'strat_002', strategy_name: 'range_scalper_btc', allocation_pct: 35 },
            { strategy_id: 'strat_003', strategy_name: 'breakout_eth', allocation_pct: 25 },
        ],
        request_id: 'mock-allocations',
        latency_ms: 0,
    };
};

const getAllocations = async (): Promise<AllocationsResponse> => {
    try {
        return await fetchJSON<AllocationsResponse>(endpoints.allocations);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockAllocations();
        }
        throw err;
    }
};

export const AllocationControlsWidget: React.FC = () => {
    const { openAirlock } = useAirlock();

    const { data, error, meta, isStale, lastGood } = usePoller<AllocationsResponse>({
        key: 'allocations',
        endpoint: endpoints.allocations,
        fetcher: getAllocations,
        interval_ms: 10000,
        stale_threshold_s: 20,
    });

    const allocations = data?.allocations || [];
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-allocations';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    // Local draft state (allows UI changes before commit)
    const [draftAllocations, setDraftAllocations] = useState<Record<string, number>>({});

    const handleSliderChange = (strategyId: string, value: number) => {
        setDraftAllocations(prev => ({
            ...prev,
            [strategyId]: value,
        }));
    };

    const handleCommit = () => {
        const newAllocations = allocations.map(alloc => ({
            ...alloc,
            allocation_pct: draftAllocations[alloc.strategy_id] ?? alloc.allocation_pct,
        }));

        const totalPct = newAllocations.reduce((sum, a) => sum + a.allocation_pct, 0);

        if (Math.abs(totalPct - 100) > 0.1) {
            alert('Error: Total allocation must equal 100%');
            return;
        }

        openAirlock({
            actionType: 'SET_ALLOCATION',
            severity: 'HIGH',
            state_before: { allocations },
            state_after: { allocations: newAllocations },
            dependencies: ['AllStrategies', 'RiskEngine', 'CapitalPool'],
            entry_exit_plan: {
                entry: 'Update capital allocation distribution',
                exit_plan: 'Strategies will rebalance to new allocation',
                success_trigger: 'Allocation percentages updated',
                back_out_plan: 'Revert to previous allocation via manual action',
            },
            executor: async () => {
                if (isMocked) {
                    throw new Error('DATA_NOT_CONNECTED: Cannot commit allocation changes on mocked data');
                }
                console.log('[EXECUTOR] Committing allocation changes', newAllocations);
            },
        });
    };

    const hasChanges = Object.keys(draftAllocations).length > 0;

    return (
        <WidgetShell
            title="Allocations"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {allocations.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No allocation data
                </div>
            ) : (
                <div style={{ padding: '4px' }}>
                    {/* Sliders */}
                    {allocations.map(alloc => {
                        const currentValue = draftAllocations[alloc.strategy_id] ?? alloc.allocation_pct;

                        return (
                            <div key={alloc.strategy_id} style={{ marginBottom: '12px' }}>
                                <div style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    marginBottom: '4px',
                                    fontSize: '10px',
                                }}>
                                    <span style={{ color: '#ccc' }}>{alloc.strategy_name}</span>
                                    <span style={{ fontFamily: 'monospace', color: '#fff', fontWeight: 'bold' }}>
                                        {currentValue.toFixed(0)}%
                                    </span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={currentValue}
                                    onChange={(e) => handleSliderChange(alloc.strategy_id, parseInt(e.target.value))}
                                    style={{
                                        width: '100%',
                                        height: '6px',
                                        appearance: 'none',
                                        background: '#1a1a1a',
                                        borderRadius: '3px',
                                        outline: 'none',
                                    }}
                                />
                            </div>
                        );
                    })}

                    {/* Commit Button */}
                    {hasChanges && (
                        <button
                            onClick={handleCommit}
                            style={{
                                width: '100%',
                                marginTop: '8px',
                                fontSize: '10px',
                                padding: '8px',
                                background: '#10b981',
                                border: 'none',
                                borderRadius: '3px',
                                color: '#fff',
                                cursor: 'pointer',
                                fontWeight: 'bold',
                            }}
                        >
                            Commit Changes
                        </button>
                    )}

                    {/* Total Check */}
                    <div style={{
                        marginTop: '8px',
                        fontSize: '9px',
                        color: '#888',
                        textAlign: 'center',
                    }}>
                        Total: {allocations.reduce((sum, a) =>
                            sum + (draftAllocations[a.strategy_id] ?? a.allocation_pct), 0
                        ).toFixed(0)}% (must = 100%)
                    </div>
                </div>
            )}
        </WidgetShell>
    );
};
