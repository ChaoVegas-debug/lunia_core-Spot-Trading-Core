import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHealth, getOpsState, getStatus, postSpotMode, setSystemMode, undoAction } from '../../api/adapter';
import type { OpsState, StatusSnapshot } from '../../api/types';
import { DataStatus } from '../common/DataStatus';
import { AirlockModal } from '../modals/AirlockModal';
import { useSemiAuto } from '../../hooks/useSemiAuto';
import { FlattenPortfolioModal } from '../modals/FlattenPortfolioModal';
import { getPlan } from '../../domain/subscription/plans';
import { LockedFeatureModal } from '../modals/LockedFeatureModal';

// REAL Feature Flag from Env
const FEATURE_AUTO_BETA = import.meta.env.VITE_FRONTEND_FEATURE_AUTO_BETA_FOR_ALL === '1';

export const SystemStateWidget: React.FC = () => {
  const auth = useAuth();
  const client = { role: auth.role, adminToken: auth.adminToken, opsToken: auth.opsToken };
  const ops = usePolledResource<OpsState>((signal) => getOpsState(signal, client), 2000, [auth.role]);
  const status = usePolledResource<StatusSnapshot>((signal) => getStatus(signal, client), 4000, [auth.role]);
  const health = usePolledResource((signal) => getHealth(signal, client), 7000, [auth.role]);

  const [undoToken, setUndoToken] = useState<string | null>(null);
  const [showAirlock, setShowAirlock] = useState(false);
  const [showFlattenModal, setShowFlattenModal] = React.useState(false);

  // Undo Timer logic could be added here (useEffect) to auto-clear after 60s

  const handleUndo = async () => {
    if (!undoToken) return;
    try {
      await undoAction(undoToken, new AbortController().signal, client);
      setUndoToken(null);
      ops.refresh(); // immediate refresh
    } catch (e: any) {
      alert("Undo Failed: " + (e.message || "Unknown error"));
    }
  };

  const executeModeChange = async (mode: 'MANUAL' | 'SEMI' | 'AUTO' | 'STOP') => {
    const controller = new AbortController();
    try {
      let token: string | undefined;

      if (mode === 'STOP') {
        const res = await setSystemMode(mode, controller.signal, client);
      } else {
        const res = await postSpotMode({ mode }, controller.signal, client);
        if (res.undo_token) {
          setUndoToken(res.undo_token);
          setTimeout(() => setUndoToken(null), (res.undo_ttl || 60) * 1000);
        }
      }

      ops.refresh();

    } catch (err: any) {
      console.error(err);
      alert(`Mode Switch Failed: ${err.message || 'Check logs'}`);
    }
  };

  const handleModeRequest = (requestMode: 'MANUAL' | 'SEMI' | 'AUTO' | 'STOP') => {
    if (requestMode === 'STOP') {
      if (window.confirm("ENGAGE GLOBAL STOP? TRADING WILL HALT IMMEDIATELY.")) {
        executeModeChange('STOP');
      }
      return;
    }

    if (requestMode === 'AUTO') {
      const plan = getPlan(auth.user?.tier);
      const allowedByPlan = plan.auto_allowed;

      // Strict Governance Gating
      if (allowedByPlan) {
        setShowAirlock(true); // Allowed naturally
        return;
      }

      if (FEATURE_AUTO_BETA) {
        // Beta Override
        setShowAirlock(true);
        return;
      }

      // Fallback or Gated
      setLockModal({
        title: "Algorithmic Trading Locked",
        reason: `AUTO Mode is locked for the ${plan.name} Plan. Upgrade to unlock autonomous execution.`,
        tier: 'ADV_RETAIL'
      });
      return;
    }

    // Default for Manual/Semi
    executeModeChange(requestMode);
  };

  const handleAirlockConfirm = async () => {
    await executeModeChange('AUTO');
    setShowAirlock(false);
  };

  // Authoritative Mode Derivation
  let derivedMode = 'MANUAL';
  if (ops.data?.global_stop) {
    derivedMode = 'STOP';
  } else if (ops.data?.auto_mode) {
    derivedMode = 'AUTO';
  } else if (ops.data?.manual_strategy || ops.data?.exec_mode === 'SEMI') {
    derivedMode = 'SEMI';
  }

  // Check if we are in Beta Override State (Auto On but Plan doesn't allow)
  const isBetaOverride = derivedMode === 'AUTO' && !getPlan(auth.user?.tier).auto_allowed && FEATURE_AUTO_BETA;

  const [lockModal, setLockModal] = useState<{ title: string, reason: string, tier?: any } | null>(null);

  if (ops.loading && !ops.data) return <div className="card">Loading system state...</div>;

  return (
    <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
      {lockModal && (
        <LockedFeatureModal
          title={lockModal.title}
          reason={lockModal.reason}
          requiredTier={lockModal.tier}
          onClose={() => setLockModal(null)}
        />
      )}

      {/* API OFFLINE OVERLAY */}
      {health.data?.status?.toLowerCase() !== 'ok' && health.data?.status?.toLowerCase() !== 'healthy' && !health.loading && (
        <div style={{
          position: 'absolute',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(2px)',
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          padding: '1rem'
        }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🔌</div>
          <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>SYSTEM UNREACHABLE</h3>
          <p className="small muted">Command Uplink Offline</p>
        </div>
      )}

      {/* RISK VETO OVERLAY (Partial) */}
      {(ops.data?.global_stop || (ops.data?.veto_reason && ops.data.veto_reason !== 'NONE')) && (
        <div style={{
          marginBottom: '1rem',
          padding: '0.75rem',
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid var(--accent-danger)',
          borderLeft: '4px solid var(--accent-danger)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem'
        }}>
          <span style={{ fontSize: '1.25rem' }}>🛡</span>
          <div>
            <strong style={{ color: 'var(--accent-danger)', textTransform: 'uppercase', fontSize: '0.85rem' }}>
              {ops.data?.global_stop ? 'Risk Engine Veto Active' : 'Governance Warning'}
            </strong>
            <div className="tiny muted">
              {ops.data?.veto_reason || "All trading automation hard-stopped. Resolve via Governance Panel."}
            </div>
          </div>
        </div>
      )}

      {/* BETA OVERRIDE BANNER (P2.2) */}
      {/* Show whenever Flag is ON but Plan is Restrictive, regardless of current mode. Honest visibility. */}
      {FEATURE_AUTO_BETA && !getPlan(auth.user?.tier).auto_allowed && (
        <div className="alert warning tiny" style={{ marginBottom: '1rem' }}>
          <strong>BETA OVERRIDE ACTIVE:</strong> AUTO Mode is temporarily unlocked by global beta flag. Your plan ({getPlan(auth.user?.tier).name}) normally restricts this feature.
        </div>
      )}

      <AirlockModal
        isOpen={showAirlock}
        onCancel={() => setShowAirlock(false)}
        onConfirm={handleAirlockConfirm}
      />

      {showFlattenModal && (
        <FlattenPortfolioModal
          onClose={() => setShowFlattenModal(false)}
        />
      )}

      <div className="card-header">
        <div>
          <h3>System State</h3>
          <p className="small">Global Mode & Health</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {undoToken && (
            <button
              className="button tiny warning"
              onClick={handleUndo}
              title={`Undo last action`}
              style={{ animation: 'pulse 2s infinite' }}
            >
              ↩ UNDO
            </button>
          )}

          {/* P1.1: Nuclear Option - Only if NOT in AUTO */}
          {derivedMode !== 'AUTO' && (
            <button
              className="button tiny danger outline"
              style={{ marginLeft: 'auto', fontSize: '0.65rem', borderColor: 'rgba(239, 68, 68, 0.4)' }}
              onClick={() => setShowFlattenModal(true)}
              title="Emergency: Convert all to stablecoin"
            >
              ☢️ FLATTEN
            </button>
          )}
          <DataStatus loading={ops.loading} error={ops.error} lastUpdated={ops.lastUpdated} staleAfterMs={8000} />
        </div>
      </div>

      <div className="mode-selector dense-grid" style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gap: '4px',
        marginBottom: '12px',
        opacity: ops.data?.global_stop ? 0.4 : 1,
        pointerEvents: ops.data?.global_stop ? 'none' : 'auto'
      }}>
        <button
          className={derivedMode === 'MANUAL' ? 'active-mode' : ''}
          onClick={() => handleModeRequest('MANUAL')}
        >
          MANUAL
        </button>
        <button
          className={derivedMode === 'SEMI' ? 'active-mode' : ''}
          style={{ opacity: 1 }}
          onClick={() => handleModeRequest('SEMI')}
        >
          SEMI-AUTO
        </button>
        <button
          className={derivedMode === 'AUTO' ? 'active-mode' : ''}
          onClick={() => handleModeRequest('AUTO')}
          style={{
            // If Plan Allows OR Beta Override => Fully accessible visually
            // If neither => Dimmed
            opacity: (getPlan(auth.user?.tier).auto_allowed || FEATURE_AUTO_BETA) ? 1 : 0.5,
            cursor: (getPlan(auth.user?.tier).auto_allowed || FEATURE_AUTO_BETA) ? 'pointer' : 'not-allowed',
            position: 'relative'
          }}
          title={(getPlan(auth.user?.tier).auto_allowed)
            ? "Fully Autonomous Trading"
            : (FEATURE_AUTO_BETA ? "Global Beta Override enabled — click to open Airlock" : "Locked by Trust Level - Upgrade Required")}
        >
          {derivedMode === 'AUTO' ? 'AUTO (ON)' : 'AUTO'}
          {!(getPlan(auth.user?.tier).auto_allowed || FEATURE_AUTO_BETA) && <span style={{ position: 'absolute', top: 2, right: 4, fontSize: '0.6rem' }}>🔒</span>}
        </button>
      </div>

      <div className="kill-switch-container" style={{ marginBottom: '16px' }}>
        <button
          className={`button full-width ${derivedMode === 'STOP' ? 'active-danger' : 'outline-danger'}`}
          style={{
            height: '40px',
            fontSize: '14px',
            letterSpacing: '0.1em',
            fontWeight: 800,
            border: '1px solid var(--accent-danger)',
            background: derivedMode === 'STOP' ? 'var(--accent-danger)' : 'rgba(255, 0, 0, 0.05)',
            color: derivedMode === 'STOP' ? '#000' : 'var(--accent-danger)',
            boxShadow: derivedMode === 'STOP' ? '0 0 15px var(--accent-danger)' : 'none'
          }}
          onClick={() => handleModeRequest('STOP')}
        >
          {derivedMode === 'STOP' ? '⚠ SYSTEM HALTED ⚠' : '☢ GLOBAL KILL SWITCH'}
        </button>
      </div>

      <div className="grid cols-2">
        <div className="card subtle small">
          <div className="flex-between">
            <span className="muted">Trading Engine</span>
            <span className={`status-chip ${ops.data?.trading_on ? 'ok' : 'error'}`} title="Master Engine Switch">
              {ops.data?.trading_on ? 'ONLINE' : 'PAUSED'}
            </span>
          </div>
          <div className="flex-between" style={{ marginTop: '0.5rem' }}>
            <span className="muted">Uptime</span>
            <span className="text-cyan">{status.data ? `${(status.data.uptime / 60).toFixed(1)}m` : 'n/a'}</span>
          </div>
        </div>
        <div className="card subtle small">
          <div className="flex-between">
            <span className="muted">Global Stop</span>
            <span className={`status-chip ${ops.data?.global_stop ? 'error' : 'ok'}`} title={ops.data?.veto_reason || "Emergency Kill Switch Status"}>
              {ops.data?.global_stop ? 'ENGAGED' : 'DISENGAGED'}
            </span>
          </div>
          <div className="flex-between" style={{ marginTop: '0.5rem' }}>
            <span className="muted">API Health</span>
            <span
              className={`status-chip ${health.data?.status === 'ok' ? 'ok' : 'warn'}`}
              title={`Last check: ${new Date().toLocaleTimeString()} - Latency: ${health.data?.latency_ms || '?'}ms`}
            >
              {health.data?.status?.toUpperCase() ?? 'UNKNOWN'}
            </span>
          </div>
          {ops.data?.airlock_status && (
            <div className="flex-between" style={{ marginTop: '0.5rem' }}>
              <span className="muted">Airlock</span>
              <span
                className={`status-chip ${ops.data.airlock_status === 'ARMED' ? 'ok' : 'warn'}`}
                title="Double-Confirmation Status for Autonomous Actions"
              >
                {ops.data.airlock_status}
              </span>
            </div>
          )}
          {ops.data?.last_drift_check && (
            <div className="flex-between" style={{ marginTop: '0.5rem' }}>
              <span className="muted">Last Drift Check</span>
              <span className="text-mono tiny muted" title="Last State Consistency Verification">
                {new Date(ops.data.last_drift_check).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
