/**
 * SIGNALS WIDGET - INSTITUTIONAL STANDARD (F1 Refactored)
 * 
 * Implements UI Constitution compliance:
 * - LAW 3: Fail-closed with FailClosedPanel + forensic diagnostics
 * - LAW 4: Provenance footer (REQ/LAT/AGE/TS/SRC)
 * - LAW 5: Stale data awareness (>10s)
 * - Smart diagnostics via normalizeResponse (NON_JSON_RESPONSE details)
 * - Institutional polling via usePoller (pause/resume, lastGood snapshot)
 * 
 * SIGNALS WIDGET (Phase F0+F1 Spec)
 * 
 * Polls /api/signals/active with fail-closed overlay + provenance.
 * Displays confident signals with confidence bars.
 * 
 * LAW 3: Fail-Closed (FailClosedPanel via usePoller)
 * LAW 4: Provenance (ProvenanceFooter via usePoller meta)
 * LAW 13: Evidence Pack (each signal has internal ref_id for tracing)
 */

import React from 'react';
import { usePoller } from '../../hooks/usePoller';
import { fetchJSON } from '../../lib/api/normalizeResponse';
import { formatProvenance } from '../../lib/runtime/provenance';
import { endpoints } from '../../lib/runtime/endpoints';
import { FailClosedPanel } from '../common/FailClosedPanel';
import { ProvenanceFooter } from '../common/ProvenanceFooter';

interface Signal {
  signal_id: string;
  strategy_id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  confidence: number;
  reason: string;
  created_at_ms: number;
}

interface SignalsResponse {
  signals: Signal[];
  count: number;
  generated_at_ms: number;
}

const getActiveSignals = async (): Promise<SignalsResponse> => {
  const now_ms = Date.now();
  return await fetchJSON<SignalsResponse>(`${endpoints.signals_active}?now_ms=${now_ms}`);
};

export const SignalsWidget: React.FC = () => {
  const { data, error, meta, isStale, lastGood } = usePoller<SignalsResponse>({
    key: 'signals_active',
    endpoint: endpoints.signals_active,
    fetcher: getActiveSignals,
    interval_ms: 5000,
    stale_threshold_s: 10,
    pause_when_hidden: true,
    force_refresh_on_focus: true,
  });

  const signals = data?.signals || [];
  const statusDot = error ? '🔴' : isStale ? '⚪' : '🟢';

  // Check for debug mode
  const debugMode = import.meta.env.VITE_SIGNAL_DEBUG_INGEST === '1';

  const handleInjectSignal = () => {
    alert('[MOCKED] Inject signal functionality - wire to real endpoint');
  };

  const now = Date.now();

  return (
    <div style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: '4px',
      padding: '0.5rem',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* HEADER */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0.5rem',
        paddingBottom: '0.5rem',
        borderBottom: '1px solid var(--border-color)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '12px' }}>{statusDot}</span>
          <span style={{ fontWeight: 'bold', fontSize: '12px', textTransform: 'uppercase' }}>
            SIGNALS INTELLIGENCE
          </span>
          {isStale && (
            <span style={{
              fontSize: '9px',
              padding: '2px 4px',
              background: '#f59e0b',
              color: '#000',
              borderRadius: '2px',
              fontWeight: 'bold'
            }}>
              STALE
            </span>
          )}
        </div>
        {debugMode && (
          <button
            onClick={handleInjectSignal}
            style={{
              fontSize: '9px',
              padding: '3px 6px',
              background: '#f59e0b',
              color: '#000',
              border: 'none',
              borderRadius: '2px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            INJECT (MOCKED)
          </button>
        )}
      </div>

      {/* FAIL-CLOSED PANEL WRAPPER */}
      <FailClosedPanel
        title="Signals Intelligence"
        error={error}
        meta={meta}
        lastGoodTs={lastGood?.meta.ts}
      >
        {/* COMPACT SIGNAL CARDS */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          opacity: isStale ? 0.6 : 1,
          filter: isStale ? 'grayscale(50%)' : 'none'
        }}>
          {signals.length === 0 ? (
            <div style={{
              padding: '1rem',
              textAlign: 'center',
              color: '#666',
              fontSize: '11px'
            }}>
              No active signals
            </div>
          ) : (
            signals.map(sig => {
              const age = Math.floor((now - sig.emitted_at_ms) / 1000);
              const ttl = Math.floor(sig.ttl_ms / 1000);
              const time = new Date(sig.emitted_at_ms).toLocaleTimeString();

              return (
                <div
                  key={sig.signal_id}
                  style={{
                    background: '#1a1a1a',
                    border: '1px solid #333',
                    borderRadius: '3px',
                    padding: '0.5rem',
                    fontSize: '11px',
                    fontFamily: 'monospace'
                  }}
                >
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginBottom: '0.25rem',
                    fontSize: '10px',
                    color: '#888'
                  }}>
                    <span>[{time}] [{sig.source}]</span>
                    <span>TTL: {ttl}s</span>
                  </div>
                  <div style={{
                    marginBottom: '0.25rem',
                    fontWeight: 'bold',
                    fontSize: '11px'
                  }}>
                    {sig.headline}
                  </div>
                  <div style={{
                    width: '100%',
                    height: '6px',
                    background: '#333',
                    borderRadius: '3px',
                    overflow: 'hidden'
                  }}>
                    <div style={{
                      width: `${sig.confidence * 100}%`,
                      height: '100%',
                      background: sig.confidence > 0.7 ? '#10b981' : sig.confidence > 0.4 ? '#f59e0b' : '#dc2626'
                    }} />
                  </div>
                  <div style={{ fontSize: '9px', color: '#666', marginTop: '0.25rem' }}>
                    {sig.symbol} • {(sig.confidence * 100).toFixed(1)}% confidence
                  </div>
                </div>
              );
            })
          )}
        </div>
      </FailClosedPanel>

      {/* PROVENANCE FOOTER */}
      <ProvenanceFooter meta={meta} showEndpoint={true} />
    </div>
  );
};
