
import React, { useEffect, useState } from 'react';
import { getFundRisk } from '../../../api/endpoints';
import { FundRisk } from '../../../api/types';

export const RiskAggregationWidget: React.FC = () => {
    const [risk, setRisk] = useState<FundRisk | null>(null);

    useEffect(() => {
        const controller = new AbortController();
        getFundRisk(controller.signal)
            .then((res) => res && setRisk(res));
        return () => controller.abort();
    }, []);

    if (!risk) return <div className="widget loading">Loading Risk Data...</div>;

    return (
        <div className="widget risk-aggregation state-danger">
            <h3>Global Risk Matrix</h3>

            <div className="metrics-row" style={{ display: 'flex', gap: '20px', margin: '15px 0' }}>
                <div className="stat">
                    <label>Max Drawdown</label>
                    <div className="value header-font" style={{ color: 'var(--red-400)' }}>-{risk.max_drawdown_pct}%</div>
                </div>

                <div className="stat">
                    <label>Concentration</label>
                    <div className="value header-font">{risk.concentration_risk}</div>
                </div>

                <div className="stat">
                    <label>Leverage</label>
                    <div className="value header-font">{risk.leverage_ratio}x</div>
                </div>
            </div>

            <div className="alerts-list">
                <h4>Active Alerts</h4>
                <ul>
                    {risk.alerts.map((a, i) => (
                        <li key={i} style={{ color: a.level === 'WARN' ? 'orange' : 'inherit' }}>
                            [{a.level}] {a.msg}
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
};
