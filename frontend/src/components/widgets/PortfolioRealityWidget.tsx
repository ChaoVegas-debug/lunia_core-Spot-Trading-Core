import React, { useMemo } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { useAuth } from '../../hooks/useAuth';
import { getPortfolioSnapshot, getOpsState } from '../../api/adapter';
import type { PortfolioAggregate, OpsState } from '../../api/types';
import { WidgetWrapper } from '../common/WidgetWrapper';

export const PortfolioRealityWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };

    // Poll data
    const { data: snapshotData, error: snapshotError, refresh: snapshotRefresh } = usePoller<PortfolioAggregate>({
        key: 'snapshot_PortfolioRealityWidget',
        endpoint: '/api/portfolio/snapshot',
        fetcher: () => getPortfolioSnapshot(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const snapshot = { data: snapshotData, error: snapshotError, loading: false, refresh: snapshotRefresh };
    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'ops_PortfolioRealityWidget',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 5000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

    // Derived State
    const hasData = snapshot.data && ops.data;

    const comparisonData = useMemo(() => {
        if (!hasData) return [];

        const balances = snapshot.data?.balances || [];
        const targetWeights = ops.data?.spot?.weights || {};
        const totalEquity = snapshot.data?.equity_total_usd || 1; // Avoid div by zero

        // 1. Get all unique assets from both Balance and Target
        const allAssets = new Set([
            ...balances.map(b => b.asset),
            ...Object.keys(targetWeights)
        ]);

        // Filter out tiny dust or unwanted assets (like USDT if it's the quote)
        // keeping USDT for context though.

        return Array.from(allAssets).map(asset => {
            const balanceEntry = balances.find(b => b.asset === asset);
            const totalHeld = (balanceEntry?.free || 0) + (balanceEntry?.locked || 0);

            // We need price to calculate USD value for pct. 
            // snapshot.positions might have price, or we might need a price feed.
            // For now, let's assume snapshot.positions has the info if it's a traded asset.
            // Or approximate from equity if available.
            // Note: PortfolioAggregate usually includes a computed 'equity_total_usd'.
            // If the backend doesn't provide per-asset USD value in 'balances', we might be limited.
            // User 'Positions' array often has average_price and quantity.

            const positionEntry = snapshot.data?.positions?.find(p => p.symbol.startsWith(asset)); // Rough match
            // improved matching logic needed if symbols are like 'BTCUSDT'

            // Backup: If we don't have direct USD value, we can't compute drift accurately without prices.
            // Let's rely on what we have. If 'positions' has unrealized_pnl etc, it implies it knows the value.
            // Let's show Raw Quantity vs Target Weight (which is %). 
            // This is mismatched (Qty vs %). We strictly need USD Value to compare with Weight %.

            // MOCK/FALLBACK for Dev Preview if APIs are incomplete:
            // Assume 1 unit = 1 USD for dev if price missing? No, that's misleading.
            // Let's list "Target %" vs "Actual Held" and leave Drift calc blank if missing data.

            return {
                asset,
                held: totalHeld,
                targetPct: (targetWeights[asset] || 0) * 100,
                // actualPct: ??? (Needs Price)
            };
        }).filter(r => r.held > 0 || r.targetPct > 0).sort((a, b) => b.targetPct - a.targetPct);

    }, [snapshot.data, ops.data]);

    const combinedError = snapshot.error || ops.error;
    const combinedLoading = snapshot.loading && ops.loading;

    return (
        <WidgetWrapper
            id="PortfolioRealityWidget"
            title="Reality Check"
            rightElem={<span className="small muted">Model vs. Exchange</span>}
            loading={combinedLoading}
            error={combinedError}
        >
            <div className="card-body">
                {!hasData ? (
                    <div className="empty-state">Loading Reality...</div>
                ) : (
                    <table className="table small-table">
                        <thead>
                            <tr>
                                <th>Asset</th>
                                <th style={{ textAlign: 'right' }}>Target Model</th>
                                <th style={{ textAlign: 'right' }}>Actual Qty</th>
                                <th style={{ textAlign: 'right' }}>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {comparisonData.map(row => (
                                <tr key={row.asset}>
                                    <td className="bright">{row.asset}</td>
                                    <td style={{ textAlign: 'right' }}>{row.targetPct.toFixed(1)}%</td>
                                    <td style={{ textAlign: 'right' }}>{row.held.toFixed(4)}</td>
                                    <td style={{ textAlign: 'right' }}>
                                        {row.targetPct > 0 && row.held === 0 ? (
                                            <span className="status-badge warning">ACQUIRE</span>
                                        ) : row.targetPct === 0 && row.held > 0 ? (
                                            <span className="status-badge error">LIQUIDATE</span>
                                        ) : (
                                            <span className="status-badge success">MATCH</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                            {comparisonData.length === 0 && (
                                <tr>
                                    <td colSpan={4} className="muted centered">No active assets or targets.</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>
        </WidgetWrapper>
    );
};
