import React from 'react';

interface MarketStrategy {
    id: string;
    title: string;
    description: string;
    tags: string[];
    risk: 'LOW' | 'MEDIUM' | 'HIGH';
    author: string;
    installs: number;
}

const STRATEGIES: MarketStrategy[] = [
    {
        id: 'm-1',
        title: 'Delta Neutral Yield Farm',
        description: 'Harvests funding rates on perp exchanges while hedging spot exposure. Market neutral.',
        tags: ['YIELD', 'NEUTRAL', 'DEFI'],
        risk: 'LOW',
        author: 'Lunia Labs',
        installs: 1240
    },
    {
        id: 'm-2',
        title: 'Volatility Crusher (Iron Condor)',
        description: 'Profits from range-bound markets using options strategies on Deribit.',
        tags: ['OPTIONS', 'VOL', 'COMPLEX'],
        risk: 'MEDIUM',
        author: 'Quant_X',
        installs: 850
    },
    {
        id: 'm-3',
        title: 'Meme Coin Sniper',
        description: 'Aggressive momentum strategies on new Solana launches. High risk, high reward.',
        tags: ['DEGEN', 'MOMENTUM', 'SOL'],
        risk: 'HIGH',
        author: 'SpeedBot',
        installs: 3200
    },
    {
        id: 'm-4',
        title: 'Institutional TWAP',
        description: 'Time-weighted average price execution for large order blocks to minimize slippage.',
        tags: ['EXECUTION', 'INSTITUTIONAL'],
        risk: 'LOW',
        author: 'Lunia Core',
        installs: 500
    }
];

export const StrategyMarketplace: React.FC = () => {
    return (
        <div className="p-4">
            <header className="mb-6">
                <h1 className="text-2xl font-bold mb-1">Strategy Marketplace</h1>
                <p className="text-muted">Discover and install verified algorithmic strategies</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {STRATEGIES.map(strat => (
                    <div key={strat.id} className="card flex flex-col justify-between h-full">
                        <div>
                            <div className="flex-between mb-3">
                                <div className={`badge ${strat.risk === 'LOW' ? 'success' : strat.risk === 'HIGH' ? 'danger' : 'warning'}`}>
                                    {strat.risk} RISK
                                </div>
                                <div className="tiny text-muted">{strat.installs} Installs</div>
                            </div>
                            <h3 className="text-lg font-bold mb-2">{strat.title}</h3>
                            <p className="text-sm text-muted mb-4">{strat.description}</p>
                            <div className="flex flex-wrap gap-2 mb-4">
                                {strat.tags.map(tag => (
                                    <span key={tag} className="badge" style={{ fontSize: '0.7em' }}>{tag}</span>
                                ))}
                            </div>
                        </div>
                        <div className="mt-4 pt-4 border-t border-[var(--border-color)] flex-between items-center">
                            <span className="tiny text-muted">By {strat.author}</span>
                            <button className="button primary small">INSTALL</button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
