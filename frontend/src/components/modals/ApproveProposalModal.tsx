import React, { useState } from 'react';
import { Proposal, ProposalApprovalGates, DataFreshnessState } from '../../api/epoch_a_types';

interface ApproveProposalModalProps {
    proposal: Proposal;
    gates: ProposalApprovalGates;
    onClose: () => void;
    onConfirm: (proposal: Proposal) => void;
    isSimulated: boolean;
}

export const ApproveProposalModal: React.FC<ApproveProposalModalProps> = ({
    proposal,
    gates,
    onClose,
    onConfirm,
    isSimulated
}) => {
    const [step, setStep] = useState(1);
    const [adjustedSize, setAdjustedSize] = useState(100); // percentage

    const hasBlockers = !gates.canApprove;

    const renderGateCheck = () => {
        const checks = [
            {
                key: 'global_stop',
                passed: !gates.global_stop,
                label: 'Global Stop',
                message: gates.global_stop ? 'BLOCKED: Global Emergency Stop Active' : '✓ System Operational'
            },
            {
                key: 'system_mode',
                passed: gates.system_mode !== 'STOP',
                label: 'System Mode',
                message: gates.system_mode === 'STOP' ? 'BLOCKED: System in STOP mode' : `✓ Mode: ${gates.system_mode}`
            },
            {
                key: 'airlock',
                passed: gates.airlock_status === 'ARMED',
                label: 'Airlock',
                message: gates.airlock_status !== 'ARMED' ? `BLOCKED: Airlock ${gates.airlock_status}` : '✓ Airlock ARMED'
            },
            {
                key: 'live_allowed',
                passed: gates.live_allowed || gates.run_mode === 'dry',
                label: 'Server Arm',
                message: !gates.live_allowed && gates.run_mode === 'real'
                    ? 'BLOCKED: Server not armed for live trading'
                    : `✓ ${gates.live_allowed ? 'Server ARMED' : 'Server SAFE (DRY mode)'}`
            },
            {
                key: 'freshness',
                passed: gates.freshness === 'FRESH',
                label: 'Data Freshness',
                message: gates.freshness !== 'FRESH'
                    ? `BLOCKED: Data ${gates.freshness} - Real approvals require FRESH data`
                    : '✓ Data FRESH'
            },
            {
                key: 'drift',
                passed: !gates.drift_status || gates.drift_status === 'NONE',
                label: 'Drift Status',
                message: gates.drift_status && gates.drift_status !== 'NONE'
                    ? `WARNING: Drift detected - ${gates.drift_status}`
                    : '✓ No drift detected'
            }
        ];

        return (
            <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                    GOVERNANCE GATE CHECK
                </h4>
                {checks.map(check => (
                    <div
                        key={check.key}
                        style={{
                            marginBottom: '0.5rem',
                            padding: '0.5rem',
                            borderRadius: '4px',
                            background: check.passed ? 'rgba(34, 197, 94, 0.05)' : 'rgba(239, 68, 68, 0.05)',
                            border: `1px solid ${check.passed ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                            fontSize: '0.8125rem'
                        }}
                    >
                        <div style={{ fontWeight: '500', color: check.passed ? 'var(--accent-success)' : 'var(--accent-danger)' }}>
                            {check.message}
                        </div>
                    </div>
                ))}

                {gates.veto_reason && (
                    <div style={{
                        marginTop: '1rem',
                        padding: '0.75rem',
                        borderRadius: '4px',
                        background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid var(--accent-danger)'
                    }}>
                        <div style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--accent-danger)', marginBottom: '0.25rem' }}>
                            VETO REASON:
                        </div>
                        <div style={{ fontSize: '0.8125rem', color: 'var(--accent-danger)' }}>
                            {gates.veto_reason}
                        </div>
                    </div>
                )}
            </div>
        );
    };

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0, 0, 0, 0.7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
                padding: '1rem'
            }}
            onClick={onClose}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                style={{
                    background: 'var(--bg-primary)',
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)',
                    maxWidth: '600px',
                    width: '100%',
                    maxHeight: '90vh',
                    overflow: 'auto'
                }}
            >
                {/* Header */}
                <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                    <div>
                        <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: '600' }}>
                            Approve Proposal
                        </h3>
                        <div style={{ fontSize: '0.875rem', color: '#999', marginTop: '0.25rem' }}>
                            {proposal.asset} • {proposal.action} • Step {step}/2
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#999',
                            fontSize: '1.5rem',
                            cursor: 'pointer',
                            padding: '0',
                            lineHeight: 1
                        }}
                    >
                        ×
                    </button>
                </div>

                {/* Content */}
                <div style={{ padding: '1.5rem' }}>
                    {step === 1 && (
                        <>
                            <h4 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: '600' }}>Step 1: Review & Adjust</h4>

                            <div style={{ marginBottom: '1.5rem' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: '500' }}>
                                    Position Size Adjustment ({adjustedSize}%)
                                </label>
                                <input
                                    type="range"
                                    min="10"
                                    max="100"
                                    value={adjustedSize}
                                    onChange={(e) => setAdjustedSize(parseInt(e.target.value))}
                                    style={{ width: '100%' }}
                                />
                                <div style={{ fontSize: '0.75rem', color: '#999', marginTop: '0.25rem' }}>
                                    Adjust position size from recommended amount
                                </div>
                            </div>

                            <div style={{ padding: '1rem', background: 'var(--bg-darker)', borderRadius: '6px', fontSize: '0.875rem' }}>
                                <div style={{ marginBottom: '0.5rem' }}>
                                    <span style={{ color: '#999' }}>Confidence:</span> <span style={{ fontWeight: '500' }}>{proposal.confidence}%</span>
                                </div>
                                <div style={{ marginBottom: '0.5rem' }}>
                                    <span style={{ color: '#999' }}>Risk:Reward:</span> <span style={{ fontWeight: '500' }}>{proposal.riskRewardRatio.toFixed(1)}</span>
                                </div>
                                <div style={{ marginBottom: '0.5rem' }}>
                                    <span style={{ color: '#999' }}>Risk Label:</span> <span style={{ fontWeight: '500' }}>{proposal.riskLabel}</span>
                                </div>
                                <div>
                                    <span style={{ color: '#999' }}>Horizon:</span> <span style={{ fontWeight: '500' }}>{proposal.horizon}</span>
                                </div>
                            </div>

                            <div style={{ padding: '1rem', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '6px', marginTop: '1rem', fontSize: '0.8125rem', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                                <div style={{ fontWeight: '600', color: 'var(--accent-warning)', marginBottom: '0.5rem' }}>
                                    ⚠️ EPOCH A Limitation
                                </div>
                                <div style={{ color: '#999' }}>
                                    Advanced features (conflict detection, liquidity check, execution plan simulation) require backend integration (EPOCH B/C).
                                    Plan preview currently shows basic configuration only.
                                </div>
                            </div>
                        </>
                    )}

                    {step === 2 && (
                        <>
                            <h4 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: '600' }}>Step 2: Gate Check & Confirm</h4>

                            {isSimulated && (
                                <div style={{
                                    padding: '1rem',
                                    background: 'rgba(245, 158, 11, 0.1)',
                                    borderRadius: '6px',
                                    marginBottom: '1.5rem',
                                    border: '1px solid var(--accent-warning)'
                                }}>
                                    <div style={{ fontWeight: '600', color: 'var(--accent-warning)', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                                        🔬 SIMULATION MODE
                                    </div>
                                    <div style={{ fontSize: '0.8125rem', color: '#999' }}>
                                        This is simulated data. No real execution will occur. Approval will create UI state only.
                                    </div>
                                </div>
                            )}

                            {renderGateCheck()}

                            {gates.run_mode === 'dry' && !hasBlockers && (
                                <div style={{
                                    padding: '1rem',
                                    background: 'rgba(100, 116, 139, 0.1)',
                                    borderRadius: '6px',
                                    marginBottom: '1rem',
                                    fontSize: '0.8125rem',
                                    border: '1px solid #64748b'
                                }}>
                                    <div style={{ fontWeight: '600', color: '#94a3b8', marginBottom: '0.25rem' }}>
                                        DRY RUN MODE
                                    </div>
                                    <div style={{ color: '#999' }}>
                                        System is in DRY mode. Approval will create intent but no real orders will execute.
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer */}
                <div style={{ padding: '1.5rem', borderTop: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between' }}>
                    <button
                        onClick={() => step === 1 ? onClose() : setStep(1)}
                        style={{
                            padding: '0.75rem 1.5rem',
                            borderRadius: '6px',
                            border: '1px solid var(--border-color)',
                            background: 'transparent',
                            color: 'var(--text-secondary)',
                            fontWeight: '500',
                            cursor: 'pointer',
                            fontSize: '0.875rem'
                        }}
                    >
                        {step === 1 ? 'Cancel' : 'Back'}
                    </button>
                    {step === 1 ? (
                        <button
                            onClick={() => setStep(2)}
                            style={{
                                padding: '0.75rem 1.5rem',
                                borderRadius: '6px',
                                border: '1px solid var(--accent-primary)',
                                background: 'var(--accent-primary)',
                                color: 'white',
                                fontWeight: '500',
                                cursor: 'pointer',
                                fontSize: '0.875rem'
                            }}
                        >
                            Next: Gate Check →
                        </button>
                    ) : (
                        <button
                            onClick={() => onConfirm(proposal)}
                            disabled={hasBlockers}
                            title={hasBlockers ? gates.blockReasons.join('; ') : ''}
                            style={{
                                padding: '0.75rem 1.5rem',
                                borderRadius: '6px',
                                border: hasBlockers ? '1px solid #666' : '1px solid var(--accent-success)',
                                background: hasBlockers ? '#333' : 'var(--accent-success)',
                                color: hasBlockers ? '#999' : 'white',
                                fontWeight: '500',
                                cursor: hasBlockers ? 'not-allowed' : 'pointer',
                                fontSize: '0.875rem',
                                opacity: hasBlockers ? 0.5 : 1
                            }}
                        >
                            {hasBlockers ? 'Blocked - See Reasons Above' : 'Confirm Approve'}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};
