import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { usePoller } from '../hooks/usePoller';
import { getHealth, getOpsState } from '../api/adapter';
import { usePreview } from '../context/PreviewModeContext';
import { OpsState } from '../api/types';
import { Proposal } from '../api/epoch_a_types';
import { computeProposalGates } from '../api/gateUtils';
import { generateRichProposals } from '../utils/proposalGenerator';

// EPOCH A Components
import { GovernanceStatusStrip } from '../components/widgets/GovernanceStatusStrip';
import { ProposalInbox } from '../components/widgets/ProposalInbox';
import { ProposalCard } from '../components/widgets/ProposalCard';
import { ProposalFeed } from '../components/widgets/ProposalFeed';
import { ProposalDetailDrawer } from '../components/drawers/ProposalDetailDrawer';
import { ActiveThesesMonitor } from '../components/widgets/ActiveThesesMonitor';

export const TraderPanelV2: React.FC = () => {
    const auth = useAuth();
    const { isPreview, isSimulation } = usePreview();
    const client = { role: auth.role, opsToken: auth.opsToken };

    // State polling
    const { data: healthData, error: healthError, refresh: healthRefresh } = usePoller({
        key: 'health_TraderPanelV2',
        endpoint: '/api/health',
        fetcher: () => getHealth(new AbortController().signal, client),
        interval_ms: 10000,
        critical: true
    });
    const health = { data: healthData, error: healthError, loading: false, refresh: healthRefresh };
    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'ops_TraderPanelV2',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 5000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

    // Use sim data if in preview and backend unreachable
    const useSimData = isPreview && isSimulation && (health.error || health.data?.status !== 'ok');
    const effectiveOps = useSimData ? { ...ops.data, global_stop: false, airlock_status: 'ARMED' } : ops.data;
    const effectiveHealth = useSimData ? { status: 'ok' } : health.data;

    // Proposal state
    const [proposals] = useState<Proposal[]>(generateRichProposals());
    const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
    const [showDetailDrawer, setShowDetailDrawer] = useState(false);

    // Compute gates
    const gates = computeProposalGates(effectiveOps, effectiveHealth?.status);

    // Handlers
    const handleSelectProposal = (proposal: Proposal) => {
        setSelectedProposal(proposal);
        setShowDetailDrawer(false);
    };

    const handleOpenDetails = (proposal: Proposal) => {
        setSelectedProposal(proposal);
        setShowDetailDrawer(true);
    };

    const handleApprove = (proposal: Proposal) => {
        console.log('[EPOCH A] Approve proposal:', proposal.id);
        // In EPOCH A, this is UI-only. EPOCH C will wire to backend.
    };

    const handleReject = (proposal: Proposal, reason: string) => {
        console.log('[EPOCH A] Reject proposal:', proposal.id, reason);
        // In EPOCH A, this is UI-only.
    };

    const handleSimulate = (proposal: Proposal) => {
        alert(`🧪 EPOCH B: Ghost Test Engine Not Connected\n\nSimulation for ${proposal.asset} ${proposal.action} would test:\n- Execution across liquidity pools\n- Slippage estimation\n- Portfolio conflicts\n- Market impact\n\nRequires Ghost Test API integration.`);
    };

    return (
        <div style={{
            minHeight: '100vh',
            background: '#0a0f1a',
            display: 'flex',
            flexDirection: 'column'
        }}>
            {/* Persistent Governance Strip */}
            <GovernanceStatusStrip
                ops={effectiveOps}
                healthStatus={effectiveHealth?.status}
                isSimulation={useSimData}
            />

            {/* 3-Pane Layout */}
            <div style={{
                flex: 1,
                display: 'flex',
                gap: '1px',
                background: '#1e293b',
                overflow: 'hidden'
            }}>
                {/* LEFT: Proposal Inbox */}
                <div style={{ width: '350px', background: '#0f172a', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <ProposalInbox
                        proposals={proposals}
                        isSimulated={useSimData}
                        onSelectProposal={handleSelectProposal}
                        selectedProposalId={selectedProposal?.id}
                    />
                </div>

                {/* CENTER: Proposal Feed */}
                <ProposalFeed selectedProposal={selectedProposal}>
                    {selectedProposal && (
                        <ProposalCard
                            proposal={selectedProposal}
                            gates={gates}
                            isSimulated={useSimData}
                            onOpenDetails={handleOpenDetails}
                            onApprove={handleApprove}
                            onReject={handleReject}
                            onSimulate={handleSimulate}
                        />
                    )}
                </ProposalFeed>

                {/* RIGHT: Active Theses Monitor (EPOCH D stub) */}
                <div style={{ width: '300px', background: '#0f172a', padding: '1rem' }}>
                    <ActiveThesesMonitor />
                </div>
            </div>

            {/* Detail Drawer (overlay) */}
            {showDetailDrawer && selectedProposal && (
                <ProposalDetailDrawer
                    proposal={selectedProposal}
                    gates={gates}
                    onClose={() => setShowDetailDrawer(false)}
                />
            )}
        </div>
    );
};
