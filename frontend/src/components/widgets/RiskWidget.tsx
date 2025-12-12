import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getLimits, getRisk } from '../../api/endpoints';
import type { LimitEntry, SpotRiskConfig } from '../../api/types';
import { DataStatus } from '../common/DataStatus';

const thresholdPct = 0.8;

export const RiskWidget: React.FC = () => {
  const auth = useAuth();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };
  const risk = usePolledResource<SpotRiskConfig>((signal) => getRisk(signal, client), 7000, [auth.role]);
  const limits = usePolledResource<{ items: LimitEntry[] }>((signal) => getLimits(signal, client), 12000, [auth.role]);

  const warnings: string[] = [];
  if (risk.data?.max_positions && risk.data.max_positions < 1) {
    warnings.push('Max positions set to zero — trading halted.');
  }
  const limitWarnings: string[] = [];
  if (risk.data && limits.data) {
    limits.data.items.forEach((lim) => {
      const val = Number(lim.value);
      if (!Number.isFinite(val)) return;
      const current = (risk.data as Record<string, unknown>)[lim.key];
      if (typeof current === 'number' && current >= val * thresholdPct) {
        limitWarnings.push(`${lim.key} at ${current} / limit ${val}`);
      }
    });
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Risk</h3>
          <p className="small">Limits and thresholds with warning banner at 80% load.</p>
        </div>
        <DataStatus loading={risk.loading} error={risk.error} lastUpdated={risk.lastUpdated} staleAfterMs={12000} />
      </div>
      {warnings.length > 0 && (
        <div className="alert warn">
          {warnings.map((w) => (
            <div key={w}>{w}</div>
          ))}
        </div>
      )}
      {limitWarnings.length > 0 && (
        <div className="alert warn">
          {limitWarnings.map((w) => (
            <div key={w}>{w}</div>
          ))}
        </div>
      )}
      {risk.error && <div className="alert">Risk endpoint error: {risk.error.message}</div>}
      {risk.data ? (
        <table className="table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
              <th>Warning</th>
            </tr>
          </thead>
          <tbody>
            {[
              { label: 'Max positions', value: risk.data.max_positions },
              { label: 'Max trade pct', value: risk.data.max_trade_pct },
              { label: 'Risk per trade pct', value: risk.data.risk_per_trade_pct },
              { label: 'Max symbol exposure pct', value: risk.data.max_symbol_exposure_pct },
              { label: 'TP default pct', value: risk.data.tp_pct_default },
              { label: 'SL default pct', value: risk.data.sl_pct_default }
            ].map((row) => {
              const valNum = typeof row.value === 'number' ? row.value : undefined;
              const warn = valNum !== undefined && valNum >= thresholdPct;
              return (
                <tr key={row.label} className={warn ? 'warn-row' : ''}>
                  <td>{row.label}</td>
                  <td>{row.value ?? 'n/a'}</td>
                  <td>{warn ? '>=80% threshold' : ''}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <div>No risk data yet.</div>
      )}
      {limits.data && limits.data.items.length > 0 && (
        <div className="small" style={{ marginTop: 8 }}>
          Limits reference:
          <ul>
            {limits.data.items.map((lim) => (
              <li key={`${lim.scope}-${lim.subject}-${lim.key}`}>
                {lim.scope}/{lim.subject ?? 'any'} — {lim.key}: {String(lim.value)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
