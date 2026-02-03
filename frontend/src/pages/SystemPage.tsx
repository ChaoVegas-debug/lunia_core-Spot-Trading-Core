import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useDashboard } from '../context/DashboardContext';
import { usePoller } from '../hooks/usePoller';
import { getSystemEvents, setGlobalCapitalCap, getOpsCapital, getOpsState } from '../api/adapter';
import { SystemEvent, OpsState } from '../api/types';

export const SystemPage: React.FC = () => {
  const { role } = useAuth();
  const client = { role };

  // Poll events frequently for "live" feel
  const { data: eventsResData, error: eventsResError, refresh: eventsResRefresh } = usePoller<{ items: SystemEvent[] }>({
        key: 'eventsRes_SystemPage',
        endpoint: '/api/events/system',
        fetcher: () => getSystemEvents(new AbortController().signal, client),
        interval_ms: 2000,
        critical: false
    });
    const eventsRes = { data: eventsResData, error: eventsResError, loading: false, refresh: eventsResRefresh };
  const { data: capitalResData, error: capitalResError, refresh: capitalResRefresh } = usePoller({
        key: 'capitalRes_SystemPage',
        endpoint: '/api/capital',
        fetcher: () => getOpsCapital(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const capitalRes = { data: capitalResData, error: capitalResError, loading: false, refresh: capitalResRefresh };
  const { data: opsResData, error: opsResError, refresh: opsResRefresh } = usePoller<OpsState>({
        key: 'opsRes_SystemPage',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 3000,
        critical: true
    });
    const opsRes = { data: opsResData, error: opsResError, loading: false, refresh: opsResRefresh };

  const [globalCapInput, setGlobalCapInput] = useState<string>('5000000');
  const [isUpdating, setIsUpdating] = useState(false);

  const { addToast } = useDashboard();

  const handleSetCap = async () => {
    const amount = parseFloat(globalCapInput);
    if (isNaN(amount) || amount <= 0) {
      addToast({ type: 'ERROR', message: "Invalid Amount" });
      return;
    }
    // if (!confirm(`Warning: Setting Global Capital Deployment Cap to $${amount.toLocaleString()}? This will affect all strategies immediately.`)) return;

    setIsUpdating(true);
    try {
      await setGlobalCapitalCap(amount);
      addToast({ type: 'SUCCESS', message: `Global Cap Set: $${amount.toLocaleString()}` });
    } catch (e) {
      addToast({ type: 'ERROR', message: "Failed to update cap" });
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="page-container" style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>
      <header className="flex-between mb-8">
        <div>
          <h1 className="text-xl font-bold tracking-tight mb-2 text-danger">SYSTEM CONTROLS</h1>
          <p className="text-muted small">Global Risk Parameters & Event Forensics</p>
        </div>
      </header>

      <div className="layout-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>

        {/* LEFT: CONTROLS */}
        <div className="flex-col gap-6">
          <div className="card">
            <div className="card-header bg-dark-2 border-b border-danger/20">
              <h3 className="text-danger">Critical Capital Controls</h3>
            </div>
            <div className="p-4">
              <div className="mb-4">
                <label className="tiny muted uppercase block mb-2">Global Deployment Cap (USD)</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    className="input"
                    value={globalCapInput}
                    onChange={e => setGlobalCapInput(e.target.value)}
                  />
                  <button
                    className="button danger"
                    disabled={isUpdating}
                    onClick={handleSetCap}
                  >
                    APPLY
                  </button>
                </div>
                <p className="tiny muted mt-2">
                  Current Mock Usage: ${(capitalRes.data?.equity || 0).toLocaleString()} ({(capitalRes.data?.cap_pct || 0) * 100}%)
                </p>
              </div>

              <hr className="border-subtle/10 my-4" />

              <div className="alert warning flex gap-2 items-start">
                <span>⚠️</span>
                <div className="tiny">
                  <strong>Emergency Mode</strong>
                  <p className="m-0">Global Stop is available in the Operator Header. This panel is for parametric constraints.</p>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header flex justify-between items-center">
              <h3>System State Inspector</h3>
              <span className="badge tiny outline">DIAGNOSTICS</span>
            </div>
            <div className="p-0 overflow-hidden">
              <div className="bg-black/50 p-4 font-mono text-xs text-green-400 overflow-x-auto">
                {opsRes.loading ? 'loading state...' : (
                  <pre>{JSON.stringify(opsRes.data, null, 2)}</pre>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT: EVENT STREAM */}
        <div className="card flex-col h-[600px]">
          <div className="card-header flex-between">
            <h3>Live Event Stream</h3>
            <div className="flex gap-2">
              <span className="badge tiny outline">Info</span>
              <span className="badge tiny warning">Warning</span>
              <span className="badge tiny danger">Critical</span>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-0">
            <table className="table w-full">
              <thead className="sticky top-0 bg-dark-2 z-10">
                <tr className="text-left tiny muted uppercase">
                  <th className="p-3">Time</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Message</th>
                  <th className="p-3 text-right">ID</th>
                </tr>
              </thead>
              <tbody>
                {eventsRes.data?.items.map(evt => (
                  <tr key={evt.id} className="border-b border-subtle/10 text-sm font-mono">
                    <td className="p-3 muted whitespace-nowrap">
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="p-3">
                      <span className={`badge tiny ${evt.type === 'CRITICAL' || (evt as any).severity === 'CRITICAL' ? 'danger' :
                        evt.type === 'WARNING' || (evt as any).severity === 'WARNING' ? 'warning' : 'secondary'
                        }`}>
                        {evt.type || (evt as any).severity}
                      </span>
                    </td>
                    <td className="p-3">{evt.message}</td>
                    <td className="p-3 text-right tiny muted">{evt.id.split('-').pop()}</td>
                  </tr>
                ))}
                {(!eventsRes.data?.items || eventsRes.data.items.length === 0) && (
                  <tr><td colSpan={4} className="p-8 text-center muted">Waiting for events...</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
