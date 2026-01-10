
import React, { useEffect, useState } from 'react';
import { getFundStrategies } from '../../../api/endpoints';
import { FundStrategy } from '../../../api/types';

export const StrategyDistributionWidget: React.FC = () => {
    const [strategies, setStrategies] = useState<FundStrategy[]>([]);

    useEffect(() => {
        const controller = new AbortController();
        getFundStrategies(controller.signal)
            .then((res) => res && setStrategies(res));
        return () => controller.abort();
    }, []);

    return (
        <div className="widget strategy-dist">
            <h3>Active Strategies</h3>
            <div style={{ overflowX: 'auto', marginTop: '10px' }}>
                <table style={{ width: '100%' }}>
                    <thead>
                        <tr>
                            <th style={{ textAlign: 'left' }}>Strategy</th>
                            <th style={{ textAlign: 'right' }}>Allocated</th>
                            <th style={{ textAlign: 'right' }}>% AUM</th>
                            <th style={{ textAlign: 'center' }}>Accts</th>
                            <th style={{ textAlign: 'center' }}>Risk</th>
                        </tr>
                    </thead>
                    <tbody>
                        {strategies.map((s) => (
                            <tr key={s.name}>
                                <td>{s.name}</td>
                                <td style={{ textAlign: 'right' }}>${(s.allocation_usd / 1000).toFixed(0)}k</td>
                                <td style={{ textAlign: 'right' }}>{s.pct_aum.toFixed(2)}%</td>
                                <td style={{ textAlign: 'center' }}>{s.account_count}</td>
                                <td style={{ textAlign: 'center' }}>
                                    <span className={`tag ${s.risk_label === 'LOW' ? 'green' : s.risk_label === 'HIGH' ? 'red' : 'yellow'}`}>
                                        {s.risk_label}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
