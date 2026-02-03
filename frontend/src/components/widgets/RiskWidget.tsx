import React from 'react';
import { WidgetBlocker } from '../common/WidgetBlocker';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getLimits, getRisk, setRiskLimits } from '../../api/adapter';
import { safeArray } from '../../utils/safe'; // Original imports for RiskWidget
import type { LimitEntry, SpotRiskConfig } from '../../api/types';
import { DataStatus } from '../common/DataStatus';
import { useDashboard } from '../../context/DashboardContext';

const thresholdPct = 0.8;

export const RiskWidget: React.FC = () => {
  const auth = useAuth();
  const { addToast } = useDashboard();
  const client = {
    role: auth.role,
    adminToken: auth.adminToken,
    opsToken: auth.opsToken,
    bearerToken: auth.bearerToken
  };
  const { data: riskData, error: riskError, refresh: riskRefresh } = usePoller<SpotRiskConfig>({
        key: 'risk_RiskWidget',
        endpoint: '/api/risk',
        fetcher: () => getRisk(new AbortController().signal, client),
        interval_ms: 7000,
        critical: false
    });
    const risk = { data: riskData, error: riskError, loading: false, refresh: riskRefresh };
  const { data: limitsData, error: limitsError, refresh: limitsRefresh } = usePoller<LimitEntry[]>({
        key: 'limits_RiskWidget',
        endpoint: '/api/limits',
        fetcher: () => getLimits(new AbortController().signal, client),
        interval_ms: 12000,
        critical: false
    });
    const limits = { data: limitsData, error: limitsError, loading: false, refresh: limitsRefresh };

  const warnings: string[] = [];
  if (risk.data?.max_positions && risk.data.max_positions < 1) {
    warnings.push('Max positions set to zero — trading halted.');
  }
  const limitWarnings: string[] = [];
  if (risk.data && limits.data) {
    limits.data.forEach((lim) => {
      const val = Number(lim.value);
      if (!Number.isFinite(val)) return;
      const current = (risk.data as Record<string, unknown>)[lim.key];
      if (typeof current === 'number' && current >= val * thresholdPct) {
        limitWarnings.push(`${lim.key} at ${current} / limit ${val}`);
      }
    });
  }

  // State for editing limits
  const [editing, setEditing] = React.useState(false);
  const [editValues, setEditValues] = React.useState<Record<string, string>>({});

  const startEdit = () => {
    const initial: Record<string, string> = {};
    limits.data?.forEach(l => initial[l.key] = String(l.value));
    setEditValues(initial);
    setEditing(true);
  };

  const saveLimits = async () => {
    if (!confirm("Confirm update to Risk Limits?")) return;
    try {

      const updates: Partial<SpotRiskConfig> = {};
      for (const [key, val] of Object.entries(editValues)) {
        // Parse value to number if possible, currently simple pass-through as string/number check
        // Ideally we cast based on key type
        const numVal = parseFloat(val);
        if (!isNaN(numVal)) {
          (updates as any)[key] = numVal;
        }
      }

      await setRiskLimits(updates, new AbortController().signal, client);
      setEditing(false);
      setEditing(false);
      limits.refresh(); // Fixed from mutate
    } catch (e) {
      addToast({ type: 'ERROR', message: "Failed to update limits" });
    }
  };

  const applyPreset = (type: 'SHIELD' | 'BALANCED' | 'ROCKET') => {
    let vals: Record<string, string> = {};
    if (type === 'SHIELD') {
      vals = {
        'max_positions': '3',
        'max_symbol_exposure_pct': '0.1',
        'max_daily_loss_pct': '0.02'
      };
    } else if (type === 'ROCKET') {
      vals = {
        'max_positions': '10',
        'max_symbol_exposure_pct': '0.35',
        'max_daily_loss_pct': '0.10'
      };
    } else {
      // Balanced
      vals = {
        'max_positions': '5',
        'max_symbol_exposure_pct': '0.2',
        'max_daily_loss_pct': '0.05'
      };
    }
    // Merge with existing editValues to preserve anything else, or overwrite specific keys
    setEditValues(prev => ({ ...prev, ...vals }));
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h3>Risk Engine</h3>
          <p className="small">Active Constraints & Vetoes</p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {/* Active Constraints Indicators */}
          <div className="flex-row gap-1" style={{ borderRight: '1px solid rgba(255,255,255,0.1)', paddingRight: '12px' }}>
            <span className="tiny px-1 bg-dark-2 rounded text-mono" title="Max Drawdown">DD:5%</span>
            <span className="tiny px-1 bg-dark-2 rounded text-mono" title="Max Leverage">LEV:3x</span>
          </div>

          {!editing ? (
            <button className="button small secondary" onClick={startEdit}>Limit Overview</button>
          ) : (
            <div style={{ display: 'flex', gap: '8px' }}>
              <div className="button-group small">
                <button className="button ghost" onClick={() => applyPreset('SHIELD')} title="Low Risk">🛡️ SHIELD</button>
                <button className="button ghost" onClick={() => applyPreset('BALANCED')} title="Balanced">⚖️ BALANCED</button>
                <button className="button ghost" onClick={() => applyPreset('ROCKET')} title="High Risk">🚀 ROCKET</button>
              </div>
              <button className="button small primary" onClick={saveLimits}>SAVE</button>
              <button className="button small" onClick={() => setEditing(false)}>CANCEL</button>
            </div>
          )}
          <DataStatus loading={risk.loading} error={risk.error} lastUpdated={risk.lastUpdated} staleAfterMs={12000} />
        </div>
      </div>
      {safeArray(warnings).length > 0 && (
        <div className="alert warn">
          {safeArray(warnings).map((w) => (
            <div key={w}>{w}</div>
          ))}
        </div>
      )}
      {safeArray(limitWarnings).length > 0 && (
        <div className="alert warn">
          {safeArray(limitWarnings).map((w) => (
            <div key={w}>{w}</div>
          ))}
        </div>
      )}
      {risk.error && (
        <div style={{ padding: '12px' }}>
          <WidgetBlocker
            reason="Risk Engine Offline"
            detail={risk.error.message}
            action="Verify Admin Token or Backend Status"
          />
        </div>
      )}
      {risk.data ? (
        <table className="table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Current</th>
              <th>Limit (Global)</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {[
              { key: 'max_positions', label: 'Max positions', value: risk.data.max_positions },
              { key: 'max_trade_pct', label: 'Max trade pct', value: risk.data.max_trade_pct },
              { key: 'risk_per_trade_pct', label: 'Risk per trade pct', value: risk.data.risk_per_trade_pct },
              { key: 'max_symbol_exposure_pct', label: 'Max symbol exp %', value: risk.data.max_symbol_exposure_pct },
            ].map((row) => {
              const valNum = typeof row.value === 'number' ? row.value : undefined;
              // Find matching limit value
              const limitEntry = limits.data?.find(l => l.key === row.key);
              const limitVal = limitEntry ? parseFloat(String(limitEntry.value)) : undefined;

              let status = '';
              if (limitVal !== undefined && valNum !== undefined) {
                if (valNum >= limitVal) status = 'VIOLATION';
                else if (valNum >= limitVal * thresholdPct) status = 'WARN';
                else status = 'OK';
              }

              return (
                <tr key={row.key} className={status === 'VIOLATION' || status === 'WARN' ? 'warn-row' : ''}>
                  <td>{row.label}</td>
                  <td>{row.value ?? 'n/a'}</td>
                  <td>
                    {editing ? (
                      <input
                        className="input small"
                        style={{ width: '80px' }}
                        value={String(editValues[row.key] || (limitEntry?.value ?? ''))}
                        onChange={e => setEditValues({ ...editValues, [row.key]: e.target.value })}
                      />
                    ) : (
                      String(limitEntry?.value ?? '-')
                    )}
                  </td>
                  <td><span className={`status-chip ${status === 'OK' ? 'ok' : status ? 'error' : 'muted'}`}>{status || '-'}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <div>No risk data yet.</div>
      )}
      {safeArray(limits.data).length > 0 && (
        <div className="small" style={{ marginTop: 8 }}>
          <p className="tiny muted">Raw Limits:</p>
          <ul>
            {safeArray(limits.data).map((lim) => (
              <li key={`${lim.scope}-${lim.subject}-${lim.key}`}>
                {lim.key}: {String(lim.value)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
