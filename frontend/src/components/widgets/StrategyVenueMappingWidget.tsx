import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getStrategies, getExchanges, getOpsCapital } from '../../api/adapter';
import type { StrategyConfig, ExchangeConfig, OpsCapital } from '../../api/types';
import { WidgetWrapper } from '../common/WidgetWrapper';

export const StrategyVenueMappingWidget: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };

    const { data: strategiesData, error: strategiesError, refresh: strategiesRefresh } = usePoller<StrategyConfig[]>({
        key: 'strategies_StrategyVenueMappingWidget',
        endpoint: '/api/strategies',
        fetcher: () => getStrategies(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const strategies = { data: strategiesData, error: strategiesError, loading: false, refresh: strategiesRefresh };
    const { data: exchangesData, error: exchangesError, refresh: exchangesRefresh } = usePoller<ExchangeConfig[]>({
        key: 'exchanges_StrategyVenueMappingWidget',
        endpoint: '/api/exchanges',
        fetcher: () => getExchanges(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const exchanges = { data: exchangesData, error: exchangesError, loading: false, refresh: exchangesRefresh };
    const { data: capitalData, error: capitalError, refresh: capitalRefresh } = usePoller<OpsCapital>({
        key: 'capital_StrategyVenueMappingWidget',
        endpoint: '/api/capital',
        fetcher: () => getOpsCapital(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const capital = { data: capitalData, error: capitalError, loading: false, refresh: capitalRefresh };

    const combinedError = strategies.error || exchanges.error || capital.error;
    const combinedLoading = strategies.loading && exchanges.loading && capital.loading;

    // Matrix Calculation
    const matrix = React.useMemo(() => {
        if (!strategies.data || !exchanges.data || !capital.data) return null;

        const totalEquity = capital.data.equity_total_usd || 100000;
        const activeStrats = strategies.data.filter(s => s.enabled);
        const activeExchanges = exchanges.data.filter(e => e.enabled);

        const rows = activeStrats.map(strat => {
            const stratAllocUsd = totalEquity * strat.weight;
            const cols = activeExchanges.map(exch => {
                const exchWeight = exch.allocation || 0;
                const val = stratAllocUsd * exchWeight;
                return { exchId: exch.id, val };
            });
            return { strat: strat.name, cols, total: stratAllocUsd };
        });

        return { rows, exchangeNames: activeExchanges.map(e => ({ id: e.id, name: e.name })) };

    }, [strategies.data, exchanges.data, capital.data]);

    return (
        <WidgetWrapper
            id="StrategyVenueMappingWidget"
            title="Capital Flow & Routing"
            loading={combinedLoading}
            error={combinedError}
            rightElem={<span className="tiny muted">STRATEGY ↔ VENUE</span>}
        >
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
        </WidgetWrapper>
    );
};
