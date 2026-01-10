import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { usePolledResource } from '../hooks/usePolledResource';
import { getHealth, getOpsState } from '../api/adapter';
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

  // Real Heartbeat & Ops State
  const client = { role: auth.role, opsToken: auth.opsToken };

  // Polling with safety for undefined
  const health = usePolledResource((s) => getHealth(s, client), 10000, []);
  const ops = usePolledResource<OpsState>((s) => getOpsState(s, client), 5000, []);

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
  const isHalted = effectiveOps?.global_stop || effectiveOps?.exec_mode === 'STOP';
  const haltReason = effectiveOps?.veto_reason || (effectiveOps?.exec_mode === 'STOP' ? "Manual Emergency Stop Active" : undefined);

  // In Preview Mode, we don't want the overlay to be "blocking" if it's just offline/simulated.
  // However, if the simulated state itself is STOPPED, we still show the halted overlay (but soft blocked due to preview).
  const showOverlay = !isLinkActive || isHalted; // Offline or Stopped

  return (
    <div className="trader-cockpit" style={{ position: 'relative', minHeight: '100vh', paddingBottom: '2rem' }}>
      {showOverlay && (
        <SystemHaltedOverlay
          isOffline={!isLinkActive}
          reason={!isLinkActive ? undefined : haltReason}
          blocking={!isPreview} // Soft block in preview
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

        {/* DIAGNOSTICS TOGGLE (Preview Only) */}
        {isPreview && (
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
