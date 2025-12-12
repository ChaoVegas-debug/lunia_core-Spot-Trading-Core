import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getCapital } from '../../api/endpoints';
import type { CapitalSnapshot } from '../../api/types';

export const CapitalWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };

  const { data, error, loading } = usePolledResource<CapitalSnapshot>((signal) => getCapital(signal, client), 9000, [auth]);

  return (
    <div className="card">
      <div className="section-header">
        <h3>Capital / Reserves</h3>
        <span className="small">polled every 9s</span>
      </div>
      {loading && !data && <div>Loading capital snapshot...</div>}
      {error && <div className="alert">Capital endpoint error: {error.message}</div>}
      {data && (
        <>
          <div className="small">Equity: {data.equity.toFixed(2)} | Cap %: {(data.cap_pct * 100).toFixed(2)}%</div>
          <h4>Allocation</h4>
          <ul>
            {Object.entries(data.allocation || {}).map(([k, v]) => (
              <li key={k} className="small">
                {k}: {v}
              </li>
            ))}
            {Object.keys(data.allocation || {}).length === 0 && <li className="small">No allocation data</li>}
          </ul>
          <div className="small">
            Reserves — portfolio: {data.reserves?.portfolio ?? 'n/a'} | arbitrage: {data.reserves?.arbitrage ?? 'n/a'}
          </div>
        </>
      )}
    </div>
  );
};
