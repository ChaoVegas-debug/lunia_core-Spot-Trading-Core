import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getPortfolioSnapshot } from '../../api/endpoints';
import type { PortfolioAggregate } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const PortfolioWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };

  const snapshot = usePolledResource<PortfolioAggregate>((signal) => getPortfolioSnapshot(signal, client), 8000, [auth.role]);

  const hasMismatch = snapshot.data && snapshot.data.tradable_equity_usd && snapshot.data.equity_total_usd
    ? Math.abs(snapshot.data.tradable_equity_usd - snapshot.data.equity_total_usd) > snapshot.data.equity_total_usd * 0.1
    : false;

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Portfolio Snapshot</h3>
          <p className="small">Combined view of balances, equity, reserves, and positions.</p>
        </div>
        <DataStatus loading={snapshot.loading} error={snapshot.error} lastUpdated={snapshot.lastUpdated} staleAfterMs={15000} />
      </div>
      {snapshot.error && <div className="alert">Portfolio load failed: {snapshot.error.message}</div>}
      {snapshot.data && (
        <>
          <div className="grid cols-2">
            <div>
              <div className="metric">Equity: {snapshot.data.equity_total_usd.toFixed(2)} USD</div>
              {snapshot.data.tradable_equity_usd !== undefined && (
                <div className="metric">Tradable: {snapshot.data.tradable_equity_usd.toFixed(2)} USD</div>
              )}
            </div>
            <div>
              {snapshot.data.cap_pct !== undefined && <div className="small">Cap %: {(snapshot.data.cap_pct * 100).toFixed(1)}%</div>}
              {snapshot.data.reserves && (
                <div className="small">Reserves: portfolio {snapshot.data.reserves.portfolio ?? 0} • arbitrage {snapshot.data.reserves.arbitrage ?? 0}</div>
              )}
            </div>
          </div>
          {hasMismatch && <div className="alert warn">Equity vs tradable equity differ by &gt;10%. Verify allocator inputs.</div>}
          <div className="grid cols-2" style={{ marginTop: 12 }}>
            <div className="card subtle">
              <h4>Positions</h4>
              <table className="table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Qty</th>
                    <th>Avg Price</th>
                    <th>Unrealized</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.data.positions.length === 0 && (
                    <tr>
                      <td colSpan={4} className="small">
                        No open positions
                      </td>
                    </tr>
                  )}
                  {snapshot.data.positions.map((pos) => (
                    <tr key={pos.symbol}>
                      <td>{pos.symbol}</td>
                      <td>{pos.quantity}</td>
                      <td>{pos.average_price}</td>
                      <td>{pos.unrealized_pnl}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="card subtle">
              <h4>Balances</h4>
              <table className="table">
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Free</th>
                    <th>Locked</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.data.balances.length === 0 && (
                    <tr>
                      <td colSpan={3} className="small">
                        No balances reported
                      </td>
                    </tr>
                  )}
                  {snapshot.data.balances.map((bal) => (
                    <tr key={bal.asset}>
                      <td>{bal.asset}</td>
                      <td>{bal.free}</td>
                      <td>{bal.locked}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
      {!snapshot.data && !snapshot.error && <div>Loading portfolio...</div>}
    </div>
  );
};
