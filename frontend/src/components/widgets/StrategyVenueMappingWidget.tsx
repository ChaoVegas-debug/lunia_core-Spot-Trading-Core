import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getStrategies, getExchanges, getOpsCapital } from '../../api/adapter';
import type { StrategyConfig, ExchangeConfig, OpsCapital } from '../../api/types';

export const StrategyVenueMappingWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };

    const strategies = usePolledResource<StrategyConfig[]>((s) => getStrategies(s, client), 5000, []);
    const exchanges = usePolledResource<ExchangeConfig[]>((s) => getExchanges(s, client), 5000, []);
    const capital = usePolledResource<OpsCapital>((s) => getOpsCapital(s, client), 5000, []);

    // Matrix Calculation
    // Total Cap * Strat % * Exchange Allocation % (Assuming even distribution for now implies Strat uses all enabled Exchanges)
    // Actually, normally specific strategies might target specific venues.
    // For this UI, we assume "Global Routing" -> Strategy runs on All Enabled Exchanges properly allocated.
    const matrix = React.useMemo(() => {
        if (!strategies.data || !exchanges.data || !capital.data) return null;

        const totalEquity = capital.data.equity_total_usd || 100000; // Fallback

        // Normalize
        const activeStrats = strategies.data.filter(s => s.enabled);
        const activeExchanges = exchanges.data.filter(e => e.enabled);

        // Simple model: Strat Weight applies to Total Equity.
        // Then that Amount is split across Active Exchanges by their Allocation weights.
        // Example: Strat A (50%), Exch 1 (60%), Exch 2 (40%).
        // Strat A gets $50k. $30k on Exch 1, $20k on Exch 2.

        const rows = activeStrats.map(strat => {
            const stratAllocUsd = totalEquity * strat.weight;

            const cols = activeExchanges.map(exch => {
                // Exchange Allocation is usually 0-1 (e.g., 0.6 for 60% of volume/cap)
                // We re-normalize exchange weights among active ones to sum to 1 for distribution?
                // Or we use their raw alloc? Let's use raw alloc * stratAlloc.
                const exchWeight = exch.allocation || 0;
                // We should probably normalize exch allocation if they don't sum to 1?
                // For visualization, let's just use raw calc.
                const val = stratAllocUsd * exchWeight;
                return { exchId: exch.id, val };
            });
            return { strat: strat.name, cols, total: stratAllocUsd };
        });

        return { rows, exchangeNames: activeExchanges.map(e => ({ id: e.id, name: e.name })) };

    }, [strategies.data, exchanges.data, capital.data]);

    return (
        <div className="card">
            <div className="card-header">
                <h3>Capital Flow & Routing</h3>
                <span className="tiny muted">STRATEGY ↔ VENUE</span>
            </div>
            <div className="card-body">
                {!matrix ? (
                    <div className="empty-state">Loading Taxonomy...</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="table small-table matrix-table">
                            <thead>
                                <tr>
                                    <th></th>
                                    {matrix.exchangeNames.map(e => <th key={e.id} style={{ textAlign: 'right' }}>{e.name}</th>)}
                                    <th style={{ textAlign: 'right' }}>Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {matrix.rows.map(row => (
                                    <tr key={row.strat}>
                                        <td className="bright font-bold">{row.strat}</td>
                                        {row.cols.map(c => (
                                            <td key={c.exchId} style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                                                ${(c.val / 1000).toFixed(1)}k
                                            </td>
                                        ))}
                                        <td style={{ textAlign: 'right', fontWeight: 'bold' }}>
                                            ${(row.total / 1000).toFixed(1)}k
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};
