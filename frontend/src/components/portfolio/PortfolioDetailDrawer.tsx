import React, { useMemo } from 'react';
import { usePoller } from '../../hooks/usePoller';
import { getPortfolioSnapshot, getStrategies, getExchanges } from '../../api/adapter';
import type { PortfolioDefinition, PortfolioAggregate, StrategyConfig, ExchangeConfig } from '../../api/types';

interface PortfolioDetailDrawerProps {
    portfolio: PortfolioDefinition;
    onClose: () => void;
    client: any;
}

export const PortfolioDetailDrawer: React.FC<PortfolioDetailDrawerProps> = ({ portfolio, onClose, client }) => {
    // Poll for real-time data
    const { data: snapshotData, error: snapshotError, refresh: snapshotRefresh } = usePoller<PortfolioAggregate>({
        key: 'snapshot_PortfolioDetailDrawer',
        endpoint: '/api/portfolio/snapshot',
        fetcher: () => getPortfolioSnapshot(new AbortController().signal, client),
        interval_ms: 3000,
        critical: false
    });
    const snapshot = { data: snapshotData, error: snapshotError, loading: false, refresh: snapshotRefresh };
    const { data: strategiesData, error: strategiesError, refresh: strategiesRefresh } = usePoller<StrategyConfig[]>({
        key: 'strategies_PortfolioDetailDrawer',
        endpoint: '/api/strategies',
        fetcher: () => getStrategies(new AbortController().signal, client),
        interval_ms: 10000,
        critical: false
    });
    const strategies = { data: strategiesData, error: strategiesError, loading: false, refresh: strategiesRefresh };
    const { data: exchangesData, error: exchangesError, refresh: exchangesRefresh } = usePoller<ExchangeConfig[]>({
        key: 'exchanges_PortfolioDetailDrawer',
        endpoint: '/api/exchanges',
        fetcher: () => getExchanges(new AbortController().signal, client),
        interval_ms: 10000,
        critical: false
    });
    const exchanges = { data: exchangesData, error: exchangesError, loading: false, refresh: exchangesRefresh };

    // Derived Data
    const positions = snapshot.data?.positions || [];
    const equity = snapshot.data?.equity_total_usd || 0;
    const pnl = snapshot.data?.unrealized_pnl || 0;
    const pnlPct = equity > 0 ? (pnl / equity) * 100 : 0;

    // Filter relevant strategies (Simulated Linkage: All enable strategies > 0 weight)
    const linkedStrategies = strategies.data?.filter(s => s.enabled && s.weight > 0) || [];

    // Filter relevant exchanges (Simulated Linkage: All connected exchanges > 0 allocation)
    const linkedExchanges = exchanges.data?.filter(e => e.connected && e.allocation > 0) || [];

    return (
        <div className="drawer-overlay" onClick={onClose} style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, left: 0,
            backgroundColor: 'rgba(0,0,0,0.7)', zIndex: 100, backdropFilter: 'blur(4px)',
            display: 'flex', justifyContent: 'flex-end'
        }}>
            <div className="drawer-content" onClick={e => e.stopPropagation()} style={{
                width: '600px', maxWidth: '90vw',
                backgroundColor: 'var(--bg-card)',
                borderLeft: '1px solid var(--border-color)',
                height: '100%', overflowY: 'auto',
                display: 'flex', flexDirection: 'column'
            }}>
                {/* Header */}
                <div className="drawer-header" style={{
                    padding: '1.5rem', borderBottom: '1px solid var(--border-color)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    backgroundColor: 'var(--bg-deep)'
                }}>
                    <div>
                        <div className="tiny muted uppercase tracking-wide">Portfolio Inspector</div>
                        <h2 style={{ margin: '4px 0 0' }}>{portfolio.id} <span className="badge small">{portfolio.type}</span></h2>
                    </div>
                    <button className="button secondary small" onClick={onClose}>Close [ESC]</button>
                </div>

                {/* Body */}
                <div style={{ padding: '1.5rem', flex: 1 }}>

                    {/* Top Stats */}
                    <div className="stats-grid" style={{
                        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem',
                        marginBottom: '2rem'
                    }}>
                        <div className="stat-card p-4 rounded bg-deep border border-subtle">
                            <label className="block text-xs muted uppercase">Total Equity</label>
                            <div className="text-xl font-mono">${equity.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
                        </div>
                        <div className="stat-card p-4 rounded bg-deep border border-subtle">
                            <label className="block text-xs muted uppercase">Unrealized PnL</label>
                            <div className={`text-xl font-mono ${pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                                {pnl >= 0 ? '+' : ''}{pnl.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                                <span className="text-sm ml-1">({pnlPct.toFixed(2)}%)</span>
                            </div>
                        </div>
                        <div className="stat-card p-4 rounded bg-deep border border-subtle">
                            <label className="block text-xs muted uppercase">Risk Profile</label>
                            <div className="text-xl">{portfolio.risk_profile}</div>
                        </div>
                    </div>

                    {/* Positions Section */}
                    <div className="section mb-8">
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <span>Open Positions</span>
                            <span className="badge tiny subtle">{positions.length}</span>
                        </h3>

                        {positions.length === 0 ? (
                            <div className="p-8 text-center muted border border-dashed rounded">No open positions.</div>
                        ) : (
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-left muted border-b border-subtle">
                                        <th className="pb-2">Asset</th>
                                        <th className="pb-2 text-right">Qty</th>
                                        <th className="pb-2 text-right">Avg Price</th>
                                        <th className="pb-2 text-right">PnL</th>
                                        <th className="pb-2 text-right">Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {positions.map(p => (
                                        <tr key={p.symbol} className="border-b border-subtle/20">
                                            <td className="py-2 font-bold">{p.symbol}</td>
                                            <td className="py-2 text-right font-mono">{p.quantity.toFixed(4)}</td>
                                            <td className="py-2 text-right font-mono">${p.average_price.toLocaleString()}</td>
                                            <td className={`py-2 text-right font-mono ${p.unrealized_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                                                {p.unrealized_pnl >= 0 ? '+' : ''}{p.unrealized_pnl.toFixed(2)}
                                            </td>
                                            <td className="py-2 text-right">
                                                <span className="badge tiny success">OPEN</span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>

                    {/* Infrastructure */}
                    <div className="grid grid-cols-2 gap-8 mb-8">
                        <div>
                            <h3 className="text-md font-bold mb-3">Allocated Venues</h3>
                            <div className="space-y-2">
                                {linkedExchanges.map(e => (
                                    <div key={e.id} className="flex justify-between items-center p-2 rounded bg-deep/50">
                                        <span>{e.name}</span>
                                        <div className="flex items-center gap-2">
                                            <span className="font-mono text-xs">{(e.allocation * 100).toFixed(0)}%</span>
                                            <div className={`w-2 h-2 rounded-full ${e.connected ? 'bg-success' : 'bg-danger'}`} />
                                        </div>
                                    </div>
                                ))}
                                {linkedExchanges.length === 0 && <div className="muted small">No venues allocated.</div>}
                            </div>
                        </div>

                        <div>
                            <h3 className="text-md font-bold mb-3">Active Strategies</h3>
                            <div className="space-y-2">
                                {linkedStrategies.map(s => (
                                    <div key={s.id} className="flex justify-between items-center p-2 rounded bg-deep/50">
                                        <span>{s.name}</span>
                                        <span className="badge tiny subtle">{s.core}</span>
                                    </div>
                                ))}
                                {linkedStrategies.length === 0 && <div className="muted small">No strategies attached.</div>}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="drawer-footer p-4 border-t border-subtle bg-deep flex justify-between items-center text-xs muted font-mono">
                    <div>LAST UPDATED: {snapshot.lastUpdated ? new Date(snapshot.lastUpdated).toLocaleTimeString() : 'NEVER'}</div>
                    {snapshot.loading && <div>SYNCING...</div>}
                </div>
            </div>
        </div>
    );
};
