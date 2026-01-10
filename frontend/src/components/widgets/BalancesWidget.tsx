
import React from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getBalances } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import { useAuth } from '../../hooks/useAuth';

export const BalancesWidget: React.FC = () => {
    const auth = useAuth();
    const { data, loading, error } = usePolledResource((signal) => getBalances(signal, { role: auth.role }), 10000, []);

    // Placeholder prices for USD estimation (Simulated logic)
    const PRICES: Record<string, number> = {
        'USDT': 1.0, 'USDC': 1.0, 'BTC': 64200, 'ETH': 3450, 'SOL': 145
    };

    const balances = data?.balances || [];
    const totalUsd = balances.reduce((sum, b) => sum + ((b.free + b.locked) * (PRICES[b.asset] || 0)), 0);

    return (
        <div className="card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header flex-between">
                <h3>Global Balances</h3>
                <span className="badge success">${totalUsd.toLocaleString()}</span>
            </div>

            <div style={{ flex: 1, overflow: 'auto' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Asset</th>
                            <th style={{ textAlign: 'right' }}>Free</th>
                            <th style={{ textAlign: 'right' }}>Locked</th>
                            <th style={{ textAlign: 'right' }}>Total USD</th>
                        </tr>
                    </thead>
                    <tbody>
                        {safeArray(balances).map(b => {
                            const total = b.free + b.locked;
                            const val = total * (PRICES[b.asset] || 0);
                            return (
                                <tr key={b.asset}>
                                    <td style={{ fontWeight: 600 }}>{b.asset}</td>
                                    <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>{b.free.toFixed(4)}</td>
                                    <td style={{ textAlign: 'right', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{b.locked.toFixed(4)}</td>
                                    <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>${val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</td>
                                </tr>
                            );
                        })}
                        {safeArray(balances).length === 0 && !loading && (
                            <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }} className="muted">No balances found or API unavailable</td></tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
