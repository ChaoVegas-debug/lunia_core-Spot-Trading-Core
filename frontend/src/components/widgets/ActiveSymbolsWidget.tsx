import React from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getActiveSymbols } from '../../api/adapter';
import { ActiveSymbol } from '../../api/types';

export const ActiveSymbolsWidget: React.FC = () => {
    const { data } = usePolledResource(getActiveSymbols, 2000);

    return (
        <div className="card">
            <div className="card-header flex-between">
                <h3>Active Symbols</h3>
                <span className="tiny badge secondary">LIVE</span>
            </div>
            <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ color: '#666', fontSize: '0.7rem', textTransform: 'uppercase' }}>
                            <th style={{ textAlign: 'left', padding: '4px' }}>Symbol</th>
                            <th style={{ textAlign: 'right' }}>Side</th>
                            <th style={{ textAlign: 'right' }}>PnL</th>
                            <th style={{ textAlign: 'right' }}>Venue</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data?.map((s: ActiveSymbol, i: number) => (
                            <tr key={i} style={{ borderBottom: '1px solid #111' }}>
                                <td style={{ padding: '6px 4px', fontWeight: 'bold' }}>{s.symbol}</td>
                                <td style={{ textAlign: 'right' }}>
                                    <span style={{
                                        color: s.side === 'LONG' ? 'var(--accent-success)' : 'var(--accent-danger)'
                                    }}>{s.side}</span>
                                </td>
                                <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                                    <span style={{ color: s.pnl_24h >= 0 ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                                        {s.pnl_24h > 0 ? '+' : ''}{s.pnl_24h}%
                                    </span>
                                </td>
                                <td style={{ textAlign: 'right', color: '#888' }}>{s.venue}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
