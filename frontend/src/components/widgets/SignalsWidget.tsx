import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getArbOpps, getSignalsFeed } from '../../api/endpoints';
import type { ArbitrageOpportunities, SignalsFeed } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

export const SignalsWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken,
    tenantId: auth.tenantId
  };

  const signals = usePolledResource<SignalsFeed>((signal) => getSignalsFeed(signal, client), 12000, [auth.role, auth.tenantId]);
  const opps = usePolledResource<ArbitrageOpportunities>((signal) => getArbOpps(signal, client), 20000, [auth.role]);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>AI Signals</h3>
          <p className="small">Supervisor output aligned with the API contract.</p>
        </div>
        <DataStatus loading={signals.loading} error={signals.error} lastUpdated={signals.lastUpdated} staleAfterMs={20000} />
      </div>
      {signals.data && signals.data.items.length > 0 ? (
        <ul className="list">
          {signals.data.items.map((item) => (
            <li key={`${item.ts}-${item.symbol}-${item.strategy}`} className="list-row">
              <div>
                <div className="small">{new Date(item.ts).toLocaleTimeString()} • {item.strategy}</div>
                <div>
                  {item.symbol} {item.side} confidence {item.confidence.toFixed(3)}
                </div>
                {item.rationale && <div className="small muted">{item.rationale}</div>}
              </div>
              <span className="status-chip ok">{item.source}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="small">No AI signals returned. This surface will populate when supervisor emits signals.</div>
      )}

      <div className="card" style={{ marginTop: 12 }}>
        <div className="card-header">
          <div>
            <h4>Arbitrage Opportunities</h4>
            <p className="small">Shown separately to avoid conflating with AI signals.</p>
          </div>
          <DataStatus loading={opps.loading} error={opps.error} lastUpdated={opps.lastUpdated} staleAfterMs={30000} />
        </div>
        {opps.data && opps.data.opportunities.length > 0 ? (
          <ul className="list">
            {opps.data.opportunities.map((opp, idx) => (
              <li key={idx} className="list-row">
                <div className="small">{JSON.stringify(opp)}</div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="small">No arbitrage opportunities returned.</div>
        )}
      </div>
    </div>
  );
};
