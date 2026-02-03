import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { usePoller } from '../hooks/usePoller';
import { getHealth, getOpsState } from '../api/adapter';

// OPERATOR OVERRIDE: Check if current user bypasses governance UI gating
const OPERATOR_OVERRIDE_EMAILS = (import.meta.env.VITE_OPERATOR_OVERRIDE_EMAILS || '').split(',').map((s: string) => s.trim().toLowerCase()).filter(Boolean);
import { OpsState } from '../api/types';
import { SystemStateWidget } from '../components/widgets/SystemStateWidget';
import { PortfolioStructureWidget } from '../components/widgets/PortfolioStructureWidget';
import { CapitalControlsWidget } from '../components/widgets/CapitalControlsWidget';
import { ExchangeControlsWidget } from '../components/widgets/ExchangeControlsWidget';
import { StrategyControlsWidget } from '../components/widgets/StrategyControlsWidget';
import { PortfolioRealityWidget } from '../components/widgets/PortfolioRealityWidget';
import { AIProposalsWidget } from '../components/widgets/AIProposalsWidget';
import { SystemFeedWidget } from '../components/widgets/SystemFeedWidget';
import { LogsWidget } from '../components/widgets/LogsWidget';
import { ExecutionTimelineWidget } from '../components/widgets/ExecutionTimelineWidget';
import { RiskWidget } from '../components/widgets/RiskWidget';
import { ManualTradeWidget } from '../components/widgets/ManualTradeWidget';
import { IntelligenceWidget } from '../components/widgets/IntelligenceWidget';
import { SignalsWidget } from '../components/widgets/SignalsWidget';
import { StrategyVenueMappingWidget } from '../components/widgets/StrategyVenueMappingWidget';
import { StrategyHealthWidget } from '../components/widgets/StrategyHealthWidget';
import { RiskBudgetDashboardWidget } from '../components/widgets/RiskBudgetDashboardWidget';
import { RiskVetoExplanationPanel } from '../components/widgets/RiskVetoExplanationPanel';
import { CreatePortfolioModal } from '../components/modals/CreatePortfolioModal';
import { SystemHaltedOverlay } from '../components/overlays/SystemHaltedOverlay';
import { GovernanceBanners } from '../components/widgets/GovernanceBanners';
import { DriftWarningBanner } from '../components/widgets/DriftWarningBanner';
import { ExecutionCommandStrip } from '../components/widgets/ExecutionCommandStrip';
import { HumanInterventionDecisionPanel } from '../components/overlays/HumanInterventionDecisionPanel';
import { BalancesWidget } from '../components/widgets/BalancesWidget';
import { TradingBlotterWidget } from '../components/widgets/TradingBlotterWidget';
import { HedgingPanel } from '../components/widgets/HedgingPanel';
import { StrategyAllocationWidget } from '../components/widgets/StrategyAllocationWidget';
import { ExchangeAllocationWidget } from '../components/widgets/ExchangeAllocationWidget';
import { ActiveSymbolsWidget } from '../components/widgets/ActiveSymbolsWidget';
import { SystemActionsFeedWidget } from '../components/widgets/SystemActionsFeedWidget';


import { usePreview } from '../context/PreviewModeContext';

export const TraderPanel: React.FC = () => {
  const [showPortfolioModal, setShowPortfolioModal] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const location = useLocation();
  const auth = useAuth();
  const { isPreview, isSimulation, simHealth, simOps } = usePreview();

  // OPERATOR OVERRIDE: Check if current user has full UI freedom
  const userEmail = auth.user?.email?.toLowerCase() || '';
  const isOperatorOverride = OPERATOR_OVERRIDE_EMAILS.includes(userEmail) || OPERATOR_OVERRIDE_EMAILS.includes('*');

  // Real Heartbeat & Ops State
  const client = { role: auth.role, opsToken: auth.opsToken };

  // Polling with safety for undefined
  const { data: healthData, error: healthError, refresh: healthRefresh } = usePoller({
        key: 'health_TraderPanel',
        endpoint: '/api/health',
        fetcher: () => getHealth(new AbortController().signal, client),
        interval_ms: 10000,
        critical: true
    });
    const health = { data: healthData, error: healthError, loading: false, refresh: healthRefresh };
  const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'ops_TraderPanel',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 5000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

  // SIMULATION FALLBACK
  // If backend is unreachable AND we are in preview simulation => use sim data
  const useSimData = isPreview && isSimulation && (health.error || health.data?.status !== 'ok');

  const effectiveHealth = useSimData ? simHealth : health.data;
  const effectiveOps = useSimData ? simOps : ops.data;

  const isLinkActive = effectiveHealth?.status === 'ok';

  // Deterministic Ready Signal for Playwright
  React.useEffect(() => {
    if (effectiveHealth && effectiveOps && (window as any).__LUNIA_READY__?.hydrated !== true) {
      (window as any).__LUNIA_READY__ = {
        route: "/trader",
        hydrated: true,
        ts: Date.now()
      };
      console.info("[READY]/trader");
    }
  }, [effectiveHealth, effectiveOps]);

  // P1.1: Hard Block Condition
  // VARIANT A: Use system_mode for halt detection
  const systemMode = effectiveOps?.system_mode || (effectiveOps?.global_stop ? 'STOP' : 'MANUAL');
  const isHalted = effectiveOps?.global_stop || systemMode === 'STOP';
  const haltReason = effectiveOps?.veto_reason || (systemMode === 'STOP' ? "Manual Emergency Stop Active" : undefined);

  // In Preview Mode, we don't want the overlay to be "blocking" if it's just offline/simulated.
  // However, if the simulated state itself is STOPPED, we still show the halted overlay (but soft blocked due to preview).
  // OPERATOR OVERRIDE: Never fully block the dashboard UI for operators, just show warnings
  const showOverlay = (!isLinkActive || isHalted) && !isOperatorOverride;
  const overlayBlocking = !isPreview && !isOperatorOverride;

  // Dashboard Render State for diagnostics
  const dashboardRenderState = {
    mounted: true,
    operatorOverride: isOperatorOverride,
    isHalted,
    isLinkActive,
    showOverlay,
    overlayBlocking,
    healthStatus: effectiveHealth?.status,
    authRole: auth.role,
    userEmail,
  };

  // Log render state for debugging
  React.useEffect(() => {
    console.info('[TraderPanel] Render State:', dashboardRenderState);
  }, [isHalted, isLinkActive, showOverlay]);

  return (
    <div className="trader-cockpit" style={{ position: 'relative', minHeight: '100vh', paddingBottom: '2rem' }}>
      {/* RENDER ANCHOR: Always visible indicator that page is mounted */}
      <div
        id="trader-panel-render-anchor"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 10000,
          background: isOperatorOverride ? 'rgba(16, 185, 129, 0.9)' : '#111',
          color: '#fff',
          padding: '4px 12px',
          fontSize: '10px',
          fontFamily: 'monospace',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}
      >
        <span>🔧 DASHBOARD MOUNTED | Override: {isOperatorOverride ? 'YES' : 'NO'} | Health: {effectiveHealth?.status || 'LOADING'}</span>
        <span>Role: {auth.role} | Halted: {isHalted ? 'YES' : 'NO'} | ts: {Date.now()}</span>
      </div>

      {/* Operator Override Warning Banner */}
      {isOperatorOverride && (isHalted || !isLinkActive) && (
        <div
          style={{
            margin: '32px 12px 0',
            padding: '12px',
            background: 'rgba(245, 158, 11, 0.2)',
            border: '1px solid var(--accent-warning)',
            borderRadius: '4px',
            color: 'var(--accent-warning)',
            fontWeight: 'bold'
          }}
        >
          ⚠️ OPERATOR OVERRIDE ACTIVE: {!isLinkActive ? 'System Offline' : `System Halted: ${haltReason || 'Unknown'}`} — Dashboard visible for diagnostics only
        </div>
      )}

      {showOverlay && (
        <SystemHaltedOverlay
          isOffline={!isLinkActive}
          reason={!isLinkActive ? undefined : haltReason}
          blocking={overlayBlocking}
        />
      )}
      <HumanInterventionDecisionPanel />

      {/* Governance Banners Layer */}
      <GovernanceBanners />
      <DriftWarningBanner status={ops.data?.drift_status} />

      {/* P4: Unified Command Strip */}
      <div style={{ padding: '0 12px', marginTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <ExecutionCommandStrip />
        </div>

        {/* DIAGNOSTICS TOGGLE (Always Available) */}
        {true && (
          <div style={{ marginLeft: '12px' }}>
            <button
              className={`button tiny ${showDiagnostics ? 'active' : 'subtle'}`}
              onClick={() => setShowDiagnostics(!showDiagnostics)}
              title="Inspect Raw System State"
            >
              🐞 DIAGNOSTICS
            </button>
          </div>
        )}
      </div>

      {/* MODALS */}
      {showPortfolioModal && (
        <CreatePortfolioModal
          onClose={() => setShowPortfolioModal(false)}
          onDeploy={() => setShowPortfolioModal(false)}
        />
      )}

      {/* DIAGNOSTICS VIEW */}
      {/* DIAGNOSTICS VIEW */}
      {showDiagnostics && (
        <div className="card" style={{ margin: '12px', padding: '16px', background: '#111', fontFamily: 'monospace' }}>
          <h3>System Diagnostics</h3>
          <div className="grid cols-2 gap-4">
            <div>
              <h4>OpsState (Raw)</h4>
              <pre style={{ fontSize: '10px', overflow: 'auto', maxHeight: '500px' }}>
                {JSON.stringify(effectiveOps, null, 2)}
              </pre>
            </div>
            <div>
              <h4>Health & Status</h4>
              <pre style={{ fontSize: '10px', overflow: 'auto', maxHeight: '500px' }}>
                {JSON.stringify({ health: effectiveHealth, sim: { isPreview, isSimulation, simHealth } }, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* MAIN LAYOUT GRID */}
      <div className="three-lane-layout" style={{
        display: 'grid',
        gridTemplateColumns: '320px 1fr 320px',
        gap: '12px',
        padding: '12px',
        alignItems: 'start'
      }}>

        {/* LEFT LANE: MARKET & INPUTS */}
        <div className="lane control-lane" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <ActiveSymbolsWidget />
          <SystemActionsFeedWidget />
          <HedgingPanel />
          <ManualTradeWidget />
        </div>

        {/* CENTER LANE: PORTFOLIO & EXECUTION */}
        <div className="lane execution-lane" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* P3.1: Reality Check First */}
          <PortfolioRealityWidget />
          <AIProposalsWidget />
          <PortfolioStructureWidget />
          <StrategyAllocationWidget />
          <TradingBlotterWidget />
          <LogsWidget />
        </div>

        {/* RIGHT LANE: INTEL, RISK, TIMELINE */}
        <div className="lane intel-lane" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <ExchangeAllocationWidget />
          <RiskWidget />
          <BalancesWidget />
          <ExecutionTimelineWidget />
          <RiskVetoExplanationPanel />
          <StrategyHealthWidget />
          <IntelligenceWidget />
          <SignalsWidget />
        </div>

      </div>


      {/* NEW: Blotter Logic (Below Main Grid or embedded? Let's clean up layout) */}
      {/* Actually inserting Blotter into Decision Lane (Center) at bottom */}
      {/* But I can't reach Center Lane easily from here with Replace, so let's check snippet context carefully. */}
      {/* I will add Blotter to the Center Lane in a separate Edit or try to grab the whole return block if small enough. */}
      {/* Easier: Add Blotter to bottom of Center Lane in next step. */}
    </div >
  );
};
