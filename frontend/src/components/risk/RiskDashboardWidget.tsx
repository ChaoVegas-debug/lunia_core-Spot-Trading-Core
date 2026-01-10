import React from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getRiskDashboard } from '../../api/adapter';
import { DataStatus } from '../common/DataStatus';

export const RiskDashboardWidget: React.FC = () => {
    const dashboard = usePolledResource(getRiskDashboard, 5000);

    const data = dashboard.data || {
        utilization_pct: 0,
        current_drawdown_pct: 0,
        effective_leverage: 0,
        top_exposures: []
    };

    const utilColor = data.utilization_pct > 0.8 ? 'text-danger' : (data.utilization_pct > 0.5 ? 'text-warning' : 'text-success');
    const ddColor = data.current_drawdown_pct > 0.04 ? 'text-danger' : (data.current_drawdown_pct > 0.02 ? 'text-warning' : 'text-success');

    return (
        <div className="card">
            <div className="card-header flex-between">
                <div>
                    <h3>Risk Overview</h3>
                    <p className="small muted">Real-time Exposure & Capital Metrics</p>
                </div>
                <DataStatus loading={dashboard.loading} error={dashboard.error} lastUpdated={dashboard.lastUpdated} staleAfterMs={10000} />
            </div>

            <div className="p-4 grid grid-cols-3 gap-4 border-b border-subtle">
                <div className="text-center p-4 bg-deep/50 rounded border border-subtle">
                    <div className="tiny muted uppercase mb-1">Capital Utilization</div>
                    <div className={`text-2xl font-mono ${utilColor}`}>{(data.utilization_pct * 100).toFixed(1)}%</div>
                    <div className="tiny muted mt-1">
                        ${((data.capital_usage?.used || 0) / 1000000).toFixed(2)}M / ${((data.capital_usage?.total || 0) / 1000000).toFixed(2)}M
                    </div>
                </div>
                <div className="text-center p-4 bg-deep/50 rounded border border-subtle">
                    <div className="tiny muted uppercase mb-1">Current Drawdown</div>
                    <div className={`text-2xl font-mono ${ddColor}`}>{(data.current_drawdown_pct * 100).toFixed(2)}%</div>
                    <div className="tiny muted mt-1">Limit: 5.00%</div>
                </div>
                <div className="text-center p-4 bg-deep/50 rounded border border-subtle">
                    <div className="tiny muted uppercase mb-1">Effective Leverage</div>
                    <div className="text-2xl font-mono text-primary">{data.effective_leverage}x</div>
                    <div className="tiny muted mt-1">Limit: 3.0x</div>
                </div>
            </div>

            <div className="p-4">
                <h4 className="tiny font-bold uppercase muted mb-3">Top Exposures</h4>
                <div className="space-y-2">
                    {data.top_exposures.length === 0 ? <div className="muted small">No exposures</div> :
                        data.top_exposures.map((item: any, idx: number) => (
                            <div key={idx} className="flex-between text-sm p-2 rounded bg-deep/30">
                                <div className="font-bold">{item.asset}</div>
                                <div className="flex items-center gap-4">
                                    <span className="font-mono text-muted">${(item.value_usd / 1000).toFixed(0)}k</span>
                                    <span className="font-mono w-12 text-right">{(item.pct * 100).toFixed(1)}%</span>
                                    <div className="w-16 h-1 bg-dark-3 rounded overflow-hidden">
                                        <div className="h-full bg-primary" style={{ width: `${item.pct * 100}%` }}></div>
                                    </div>
                                </div>
                            </div>
                        ))
                    }
                </div>
            </div>
        </div>
    );
};
