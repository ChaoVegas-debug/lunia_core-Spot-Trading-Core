
import React, { useEffect, useState } from 'react';
import { getFundPortfolio } from '../../../api/endpoints';
import { FundPortfolio } from '../../../api/types';

export const PortfolioAggregationWidget: React.FC = () => {
    const [data, setData] = useState<FundPortfolio | null>(null);
    const [tab, setTab] = useState<'ASSET' | 'EXCHANGE'>('ASSET');

    useEffect(() => {
        const controller = new AbortController();
        getFundPortfolio(controller.signal)
            .then((res) => res && setData(res));
        return () => controller.abort();
    }, []);

    if (!data) return <div className="widget loading">Loading Portfolio...</div>;

    const items = tab === 'ASSET' ? data.by_asset : data.by_exchange;

    return (
        <div className="widget portfolio-aggregation">
            <div className="widget-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
                <h3>Portfolio Aggregation</h3>
                <div className="tabs">
                    <button className={tab === 'ASSET' ? 'active' : ''} onClick={() => setTab('ASSET')}>Asset</button>
                    <button className={tab === 'EXCHANGE' ? 'active' : ''} onClick={() => setTab('EXCHANGE')}>Exchange</button>
                </div>
            </div>

            <div className="list-container" style={{ marginTop: '12px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr>
                            <th style={{ textAlign: 'left' }}>Name</th>
                            <th style={{ textAlign: 'right' }}>Value (USD)</th>
                            <th style={{ textAlign: 'right' }}>%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items.map((item: any, idx) => (
                            <tr key={idx} style={{ borderBottom: '1px solid #333' }}>
                                <td style={{ padding: '8px 0' }}>{item.asset || item.exchange}</td>
                                <td style={{ textAlign: 'right' }}>${item.total_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                                <td style={{ textAlign: 'right' }}>{item.pct.toFixed(2)}%</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
