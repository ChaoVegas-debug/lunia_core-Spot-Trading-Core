/**
 * STRATEGIES BOARD WIDGET
 * 
 * Live strategy status monitor with governance controls.
 * Actions (Pause/Resume/Halt) MUST route through AirlockModalV3.
 * 
 * Dense list: [NAME] [STATUS] [Actions]
 * 
 * Single Gate Law enforcement: All dangerous controls use openAirlock().
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON, isHttpError } from '../../lib/api/normalizeResponse';
import { endpoints } from '../../lib/runtime/endpoints';
import { WidgetShell } from '../cockpit/WidgetShell';
import { getStatusDot } from '../../lib/runtime/provenance';
import { useAirlock } from '../../hooks/useAirlock';
import type { ProvenanceMeta } from '../../lib/runtime/provenance';

type StrategyStatus = 'RUNNING' | 'PAUSED' | 'HALTED';

interface Strategy {
    id: string;
    name: string;
    status: StrategyStatus;
}

interface StrategiesResponse {
    strategies: Strategy[];
    request_id?: string;
    latency_ms?: number;
}

// MOCK PROTOCOL: Sample strategies
const generateMockStrategies = (): StrategiesResponse => {
    return {
        strategies: [
            { id: 'strat_001', name: 'momentum_trend_v2', status: 'RUNNING' },
            { id: 'strat_002', name: 'range_scalper_btc', status: 'PAUSED' },
            { id: 'strat_003', name: 'breakout_eth', status: 'RUNNING' },
        ],
        request_id: 'mock-strategies',
        latency_ms: 0,
    };
};

const getStrategies = async (): Promise<StrategiesResponse> => {
    try {
        return await fetchJSON<StrategiesResponse>(endpoints.strategies);
    } catch (err) {
        if (isHttpError(err) && err.http_status === 404) {
            return generateMockStrategies();
        }
        throw err;
    }
};

export const StrategiesBoardWidget: React.FC = () => {
    const { openAirlock } = useAirlock();

    const { data, error, meta, isStale, lastGood } = usePoller<StrategiesResponse>({
        key: 'strategies',
        endpoint: endpoints.strategies,
        fetcher: getStrategies,
        interval_ms: 5000,
        stale_threshold_s: 10,
    });

    const strategies = data?.strategies || [];
    const statusDot = getStatusDot(error, isStale);

    const isMocked = data?.request_id === 'mock-strategies';
    const mockMeta: ProvenanceMeta = isMocked
        ? { ...meta, source: 'sim' }
        : meta;

    // Action handlers (routed through Airlock)
    const handlePause = (strategy: Strategy) => {
        openAirlock({
            actionType: 'PAUSE_STRATEGY',
            severity: 'HIGH',
            state_before: { strategy_id: strategy.id, status: strategy.status },
            state_after: { strategy_id: strategy.id, status: 'PAUSED' },
            dependencies: [strategy.name, 'PortfolioRebalancer'],
            entry_exit_plan: {
                entry: `Pause strategy ${strategy.name}`,
                exit_plan: 'Open positions will remain, no new orders',
                success_trigger: 'Strategy status = PAUSED',
                back_out_plan: 'Resume via manual action',
            },
            executor: async () => {
                // TODO: Call actual backend endpoint
                if (isMocked) {
                    throw new Error('DATA_NOT_CONNECTED: Cannot execute on mocked data');
                }
                console.log(`[EXECUTOR] Pausing strategy ${strategy.id}`);
            },
        });
    };

    const handleResume = (strategy: Strategy) => {
        openAirlock({
            actionType: 'RESUME_STRATEGY',
            severity: 'HIGH',
            state_before: { strategy_id: strategy.id, status: strategy.status },
            state_after: { strategy_id: strategy.id, status: 'RUNNING' },
            dependencies: [strategy.name, 'RiskEngine'],
            entry_exit_plan: {
                entry: `Resume strategy ${strategy.name}`,
                exit_plan: 'Strategy will generate new signals',
                success_trigger: 'Strategy status = RUNNING',
                back_out_plan: 'Pause via manual action',
            },
            executor: async () => {
                if (isMocked) {
                    throw new Error('DATA_NOT_CONNECTED: Cannot execute on mocked data');
                }
                console.log(`[EXECUTOR] Resuming strategy ${strategy.id}`);
            },
        });
    };

    const handleHalt = (strategy: Strategy) => {
        openAirlock({
            actionType: 'HALT_STRATEGY',
            severity: 'CRITICAL',
            state_before: { strategy_id: strategy.id, status: strategy.status },
            state_after: { strategy_id: strategy.id, status: 'HALTED' },
            dependencies: [strategy.name, 'AllPositions', 'ActiveOrders'],
            entry_exit_plan: {
                entry: `HALT strategy ${strategy.name}`,
                exit_plan: 'Cancel all orders, close all positions',
                success_trigger: 'Strategy status = HALTED, positions = 0',
                back_out_plan: 'Manual recovery required',
            },
            executor: async () => {
                if (isMocked) {
                    throw new Error('DATA_NOT_CONNECTED: Cannot execute on mocked data');
                }
                console.log(`[EXECUTOR] Halting strategy ${strategy.id}`);
            },
        });
    };

    return (
        <WidgetShell
            title="Strategies"
            badgeType={isMocked ? 'MOCKED' : 'LIVE'}
            statusDot={statusDot}
            meta={mockMeta}
            error={error}
            lastGood={lastGood}
            isStale={isStale}
        >
            {strategies.length === 0 ? (
                <div style={{ padding: '1rem', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                    No strategies configured
                </div>
            ) : (
                <div>
                    {strategies.map(strat => {
                        const statusColor =
                            strat.status === 'RUNNING' ? '#10b981' :
                                strat.status === 'PAUSED' ? '#f59e0b' :
                                    '#666';

                        return (
                            <div
                                key={strat.id}
                                style={{
                                    padding: '8px 4px',
                                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                }}
                            >
                                {/* Name + Status */}
                                <div style={{ flex: 1 }}>
                                    <div style={{
                                        fontSize: '10px',
                                        fontFamily: 'monospace',
                                        color: '#fff',
                                        marginBottom: '2px',
                                    }}>
                                        {strat.name}
                                    </div>
                                    <div style={{
                                        fontSize: '9px',
                                        fontWeight: 'bold',
                                        color: statusColor,
                                    }}>
                                        [{strat.status}]
                                    </div>
                                </div>

                                {/* Actions */}
                                <div style={{ display: 'flex', gap: '4px' }}>
                                    {strat.status === 'RUNNING' && (
                                        <>
                                            <button
                                                onClick={() => handlePause(strat)}
                                                style={{
                                                    fontSize: '9px',
                                                    padding: '4px 8px',
                                                    background: '#f59e0b',
                                                    border: 'none',
                                                    borderRadius: '2px',
                                                    color: '#000',
                                                    cursor: 'pointer',
                                                    fontWeight: 'bold',
                                                }}
                                            >
                                                Pause
                                            </button>
                                            <button
                                                onClick={() => handleHalt(strat)}
                                                style={{
                                                    fontSize: '9px',
                                                    padding: '4px 8px',
                                                    background: '#dc2626',
                                                    border: 'none',
                                                    borderRadius: '2px',
                                                    color: '#fff',
                                                    cursor: 'pointer',
                                                    fontWeight: 'bold',
                                                }}
                                            >
                                                Halt
                                            </button>
                                        </>
                                    )}
                                    {strat.status === 'PAUSED' && (
                                        <>
                                            <button
                                                onClick={() => handleResume(strat)}
                                                style={{
                                                    fontSize: '9px',
                                                    padding: '4px 8px',
                                                    background: '#10b981',
                                                    border: 'none',
                                                    borderRadius: '2px',
                                                    color: '#fff',
                                                    cursor: 'pointer',
                                                    fontWeight: 'bold',
                                                }}
                                            >
                                                Resume
                                            </button>
                                            <button
                                                onClick={() => handleHalt(strat)}
                                                style={{
                                                    fontSize: '9px',
                                                    padding: '4px 8px',
                                                    background: '#dc2626',
                                                    border: 'none',
                                                    borderRadius: '2px',
                                                    color: '#fff',
                                                    cursor: 'pointer',
                                                    fontWeight: 'bold',
                                                }}
                                            >
                                                Halt
                                            </button>
                                        </>
                                    )}
                                    {strat.status === 'HALTED' && (
                                        <div style={{
                                            fontSize: '9px',
                                            color: '#666',
                                            fontStyle: 'italic',
                                        }}>
                                            manual recovery
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </WidgetShell>
    );
};
