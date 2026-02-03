import React, { useState } from 'react';
import { Proposal, ProposalApprovalGates, DataFreshnessState } from '../../api/epoch_a_types';
import { ApproveProposalModal } from '../modals/ApproveProposalModal';

interface ProposalCardProps {
    proposal: Proposal;
    gates: ProposalApprovalGates;
    isSimulated: boolean;
    onOpenDetails: (proposal: Proposal) => void;
    onApprove: (proposal: Proposal) => void;
    onReject: (proposal: Proposal, reason: string) => void;
    onSimulate: (proposal: Proposal) => void;
}

export const ProposalCard: React.FC<ProposalCardProps> = ({
    proposal,
    gates,
    isSimulated,
    onOpenDetails,
    onApprove,
    onReject,
    onSimulate
}) => {
    const [showApproveModal, setShowApproveModal] = useState(false);
    const [showRejectModal, setShowRejectModal] = useState(false);
    const [rejectReason, setRejectReason] = useState('');

    const isStale = gates.freshness !== 'FRESH';
    const canApprove = gates.canApprove && !isStale;

    // Color coding
    const getActionColor = (action: string) => {
        switch (action) {
            case 'BUY': return '#10b981'; // green-500
            case 'SELL': return '#ef4444'; // red-500
            case 'HEDGE': return '#f59e0b'; // amber-500
            case 'REBALANCE': return '#3b82f6'; // blue-500
            default: return '#6b7280';
        }
    };

    const getPriorityColor = (priority: string) => {
        switch (priority) {
            case 'URGENT': return '#ef4444';
            case 'HIGH': return '#f59e0b';
            case 'MEDIUM': return '#3b82f6';
            case 'LOW': return '#6b7280';
            default: return '#6b7280';
        }
    };

    const getRiskColor = (risk: string) => {
        switch (risk) {
            case 'EXTREME_RISK': return '#dc2626';
            case 'HIGH_RISK': return '#f59e0b';
            case 'MEDIUM_RISK': return '#3b82f6';
            case 'LOW_RISK': return '#10b981';
            default: return '#6b7280';
        }
    };

    const getGateBadgeColor = (passed: boolean) => passed ? '#10b981' : '#ef4444';

    // Calculate time remaining
    const getTimeRemaining = () => {
        if (!proposal.expiresAt) return null;
        const now = Date.now();
        const expires = new Date(proposal.expiresAt).getTime();
        const diff = expires - now;
        if (diff < 0) return 'EXPIRED';
        const hours = Math.floor(diff / 3600000);
        const minutes = Math.floor((diff % 3600000) / 60000);
        return `${hours}h ${minutes}m`;
    };

    const timeRemaining = getTimeRemaining();

    return (
        <>
            <div
                style={{
                    position: 'relative',
                    background: '#0f172a', // slate-900
                    border: '1px solid #1e293b', // slate-800
                    borderRadius: '12px',
                    overflow: 'hidden',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
                }}
            >
                {/* STALE = DEAD LOCKDOWN OVERLAY (NON-DISMISSIBLE) */}
                {isStale && (
                    <div
                        style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            background: 'rgba(0, 0, 0, 0.85)',
                            backdropFilter: 'blur(8px)',
                            zIndex: 50,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            padding: '2rem',
                            cursor: 'not-allowed'
                        }}
                    >
                        <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔒</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: '700', color: '#ef4444', marginBottom: '0.5rem', textAlign: 'center' }}>
                            DATA STALE — APPROVAL BLOCKED
                        </div>
                        <div style={{ fontSize: '1rem', color: '#94a3b8', textAlign: 'center', maxWidth: '400px' }}>
                            Data freshness is {gates.freshness}. Real approvals require FRESH data.
                            This lockdown is NON-DISMISSIBLE until data refreshes.
                        </div>
                        <div style={{
                            marginTop: '1.5rem',
                            padding: '0.75rem 1.5rem',
                            background: 'rgba(239, 68, 68, 0.2)',
                            border: '1px solid #ef4444',
                            borderRadius: '6px',
                            color: '#fca5a5',
                            fontWeight: '500',
                            fontSize: '0.875rem'
                        }}>
                            ⚠️ FAIL-CLOSED SAFETY ENGAGED
                        </div>
                    </div>
                )}

                {/* HEADER */}
                <div style={{
                    padding: '1.5rem',
                    borderBottom: '1px solid #1e293b',
                    background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)'
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            {/* Asset */}
                            <div style={{ fontSize: '1.75rem', fontWeight: '700', color: '#f1f5f9' }}>
                                {proposal.asset}
                            </div>
                            {/* Action Badge */}
                            <div style={{
                                padding: '0.375rem 0.75rem',
                                borderRadius: '6px',
                                background: getActionColor(proposal.action) + '20',
                                border: `2px solid ${getActionColor(proposal.action)}`,
                                color: getActionColor(proposal.action),
                                fontWeight: '700',
                                fontSize: '0.875rem',
                                boxShadow: `0 0 10px ${getActionColor(proposal.action)}40`
                            }}>
                                {proposal.action}
                            </div>
                        </div>

                        {/* Priority Badge */}
                        <div style={{
                            padding: '0.375rem 0.75rem',
                            borderRadius: '6px',
                            background: getPriorityColor(proposal.priority) + '20',
                            border: `1px solid ${getPriorityColor(proposal.priority)}`,
                            color: getPriorityColor(proposal.priority),
                            fontWeight: '600',
                            fontSize: '0.75rem'
                        }}>
                            {proposal.priority}
                        </div>
                    </div>

                    {/* Confidence & Metrics */}
                    <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem', fontWeight: '500' }}>
                                CONFIDENCE
                            </div>
                            <div style={{ fontSize: '2.5rem', fontWeight: '700', color: '#3b82f6', textShadow: '0 0 20px rgba(59, 130, 246, 0.5)' }}>
                                {proposal.confidence}%
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>R:R</div>
                            <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#10b981' }}>
                                {proposal.riskRewardRatio.toFixed(1)}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>RISK</div>
                            <div style={{
                                fontSize: '0.875rem',
                                fontWeight: '600',
                                color: getRiskColor(proposal.riskLabel),
                                textTransform: 'uppercase'
                            }}>
                                {proposal.riskLabel.replace('_', ' ')}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>HORIZON</div>
                            <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#94a3b8' }}>
                                {proposal.horizon}
                            </div>
                        </div>
                        {timeRemaining && (
                            <div>
                                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>TTL</div>
                                <div style={{
                                    fontSize: '0.875rem',
                                    fontWeight: '600',
                                    color: timeRemaining === 'EXPIRED' ? '#ef4444' : '#f59e0b'
                                }}>
                                    {timeRemaining}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* INTERNAL GOVERNANCE STRIP */}
                <div style={{
                    padding: '0.75rem 1.5rem',
                    background: '#0a0f1a',
                    borderBottom: '1px solid #1e293b',
                    display: 'flex',
                    gap: '0.75rem',
                    flexWrap: 'wrap'
                }}>
                    {[
                        { label: 'GLOBAL STOP', passed: !gates.global_stop },
                        { label: 'AIRLOCK', passed: gates.airlock_status === 'ARMED' },
                        { label: 'FRESHNESS', passed: gates.freshness === 'FRESH' },
                        { label: 'SERVER ARM', passed: gates.live_allowed || gates.run_mode === 'dry' },
                        { label: 'DRIFT', passed: !gates.drift_status || gates.drift_status === 'NONE' }
                    ].map(gate => (
                        <div
                            key={gate.label}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.5rem',
                                padding: '0.375rem 0.625rem',
                                borderRadius: '4px',
                                background: gate.passed ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                                border: `1px solid ${getGateBadgeColor(gate.passed)}`,
                                fontSize: '0.75rem',
                                fontWeight: '500'
                            }}
                        >
                            <span style={{ color: getGateBadgeColor(gate.passed) }}>
                                {gate.passed ? '✓' : '✗'}
                            </span>
                            <span style={{ color: '#94a3b8' }}>{gate.label}</span>
                        </div>
                    ))}
                </div>

                {/* BODY */}
                <div style={{ padding: '1.5rem' }}>
                    {/* Thesis Summary */}
                    <div style={{ marginBottom: '1.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.5rem', fontWeight: '600', letterSpacing: '0.05em' }}>
                            THESIS
                        </div>
                        <div style={{ fontSize: '0.9375rem', color: '#cbd5e1', lineHeight: '1.6' }}>
                            {proposal.thesisSummary}
                        </div>
                    </div>

                    {/* Factor Attribution */}
                    <div style={{ marginBottom: '1.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem', fontWeight: '600', letterSpacing: '0.05em' }}>
                            FACTOR ATTRIBUTION
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {proposal.factorAttribution.map((factor, idx) => (
                                <div key={idx}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                                        <span style={{ fontSize: '0.8125rem', color: '#94a3b8' }}>{factor.factor}</span>
                                        <span style={{ fontSize: '0.8125rem', color: '#f1f5f9', fontWeight: '500' }}>{factor.weight}%</span>
                                    </div>
                                    <div style={{
                                        height: '6px',
                                        background: '#1e293b',
                                        borderRadius: '3px',
                                        overflow: 'hidden'
                                    }}>
                                        <div style={{
                                            width: `${factor.weight}%`,
                                            height: '100%',
                                            background: `hsl(${idx * 60}, 70%, 50%)`,
                                            boxShadow: `0 0 8px hsl(${idx * 60}, 70%, 50%)`,
                                            transition: 'width 0.3s ease'
                                        }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Thesis Health (EPOCH D Preview) */}
                    <div style={{ marginBottom: '1.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem', fontWeight: '600', letterSpacing: '0.05em' }}>
                            THESIS HEALTH (PREVIEW)
                        </div>
                        <div style={{
                            padding: '1rem',
                            background: '#1e293b',
                            borderRadius: '8px',
                            border: '1px solid #334155'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.75rem' }}>
                                <div style={{ flex: 1, height: '8px', background: '#0f172a', borderRadius: '4px', overflow: 'hidden' }}>
                                    <div style={{
                                        width: '75%',
                                        height: '100%',
                                        background: 'linear-gradient(90deg, #10b981, #3b82f6)',
                                        boxShadow: '0 0 10px rgba(16, 185, 129, 0.5)'
                                    }} />
                                </div>
                                <span style={{ fontSize: '1rem', fontWeight: '600', color: '#10b981' }}>75%</span>
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#64748b', fontStyle: 'italic' }}>
                                Biological governance (watchdogs) will appear here in EPOCH D
                            </div>
                        </div>
                    </div>

                    {/* Mini Chart Stub */}
                    <div style={{ marginBottom: '1.5rem' }}>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem', fontWeight: '600', letterSpacing: '0.05em' }}>
                            ENTRY / TP / SL
                        </div>
                        <div style={{
                            padding: '1rem',
                            background: '#1e293b',
                            borderRadius: '8px',
                            border: '1px solid #f59e0b',
                            textAlign: 'center'
                        }}>
                            <div style={{ fontSize: '0.875rem', color: '#f59e0b', fontWeight: '600', marginBottom: '0.5rem' }}>
                                📊 EPOCH B: Real Chart Payload Not Connected
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                Live price data + technical levels will render here
                            </div>
                        </div>
                    </div>
                </div>

                {/* ACTIONS */}
                <div style={{
                    padding: '1.5rem',
                    borderTop: '1px solid #1e293b',
                    display: 'flex',
                    gap: '0.75rem',
                    flexWrap: 'wrap'
                }}>
                    <button
                        onClick={() => onOpenDetails(proposal)}
                        style={{
                            flex: '1 1 auto',
                            padding: '0.75rem 1.5rem',
                            borderRadius: '8px',
                            border: '1px solid #3b82f6',
                            background: 'rgba(59, 130, 246, 0.1)',
                            color: '#3b82f6',
                            fontWeight: '600',
                            fontSize: '0.875rem',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            boxShadow: '0 0 10px rgba(59, 130, 246, 0.2)'
                        }}
                    >
                        DETAILS
                    </button>
                    <button
                        onClick={() => onSimulate(proposal)}
                        style={{
                            flex: '1 1 auto',
                            padding: '0.75rem 1.5rem',
                            borderRadius: '8px',
                            border: '1px solid #8b5cf6',
                            background: 'rgba(139, 92, 246, 0.1)',
                            color: '#8b5cf6',
                            fontWeight: '600',
                            fontSize: '0.875rem',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            boxShadow: '0 0 10px rgba(139, 92, 246, 0.2)'
                        }}
                    >
                        SIMULATE
                    </button>
                    <button
                        onClick={() => setShowApproveModal(true)}
                        disabled={!canApprove}
                        title={!canApprove ? gates.blockReasons.join('; ') : ''}
                        style={{
                            flex: '1 1 auto',
                            padding: '0.75rem 1.5rem',
                            borderRadius: '8px',
                            border: canApprove ? '2px solid #10b981' : '1px solid #475569',
                            background: canApprove ? 'rgba(16, 185, 129, 0.2)' : '#1e293b',
                            color: canApprove ? '#10b981' : '#64748b',
                            fontWeight: '700',
                            fontSize: '0.875rem',
                            cursor: canApprove ? 'pointer' : 'not-allowed',
                            transition: 'all 0.2s ease',
                            boxShadow: canApprove ? '0 0 15px rgba(16, 185, 129, 0.3)' : 'none',
                            opacity: canApprove ? 1 : 0.5
                        }}
                    >
                        {canApprove ? '✓ APPROVE' : '🔒 BLOCKED'}
                    </button>
                    <button
                        onClick={() => setShowRejectModal(true)}
                        style={{
                            flex: '1 1 auto',
                            padding: '0.75rem 1.5rem',
                            borderRadius: '8px',
                            border: '1px solid #ef4444',
                            background: 'rgba(239, 68, 68, 0.1)',
                            color: '#ef4444',
                            fontWeight: '600',
                            fontSize: '0.875rem',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                            boxShadow: '0 0 10px rgba(239, 68, 68, 0.2)'
                        }}
                    >
                        REJECT
                    </button>
                </div>
            </div>

            {/* Approve Modal */}
            {showApproveModal && (
                <ApproveProposalModal
                    proposal={proposal}
                    gates={gates}
                    isSimulated={isSimulated}
                    onClose={() => setShowApproveModal(false)}
                    onConfirm={(p) => {
                        onApprove(p);
                        setShowApproveModal(false);
                    }}
                />
            )}

            {/* Reject Modal */}
            {showRejectModal && (
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
                        zIndex: 1000
                    }}
                    onClick={() => setShowRejectModal(false)}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            background: '#0f172a',
                            borderRadius: '12px',
                            border: '1px solid #1e293b',
                            padding: '2rem',
                            maxWidth: '500px',
                            width: '90%'
                        }}
                    >
                        <h3 style={{ margin: '0 0 1rem 0', color: '#f1f5f9' }}>Reject Proposal</h3>
                        <select
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            style={{
                                width: '100%',
                                padding: '0.75rem',
                                borderRadius: '6px',
                                border: '1px solid #334155',
                                background: '#1e293b',
                                color: '#f1f5f9',
                                fontSize: '0.875rem',
                                marginBottom: '1rem'
                            }}
                        >
                            <option value="">Select reason...</option>
                            <option value="RISK_TOO_HIGH">Risk Too High</option>
                            <option value="INSUFFICIENT_CONFIDENCE">Insufficient Confidence</option>
                            <option value="PORTFOLIO_CONFLICT">Portfolio Conflict</option>
                            <option value="TIMING_POOR">Poor Timing</option>
                            <option value="OTHER">Other</option>
                        </select>
                        <div style={{ display: 'flex', gap: '0.75rem' }}>
                            <button
                                onClick={() => setShowRejectModal(false)}
                                style={{
                                    flex: 1,
                                    padding: '0.75rem',
                                    borderRadius: '6px',
                                    border: '1px solid #334155',
                                    background: 'transparent',
                                    color: '#94a3b8',
                                    fontWeight: '500',
                                    cursor: 'pointer'
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => {
                                    if (rejectReason) {
                                        onReject(proposal, rejectReason);
                                        setShowRejectModal(false);
                                        setRejectReason('');
                                    }
                                }}
                                disabled={!rejectReason}
                                style={{
                                    flex: 1,
                                    padding: '0.75rem',
                                    borderRadius: '6px',
                                    border: '1px solid #ef4444',
                                    background: rejectReason ? 'rgba(239, 68, 68, 0.2)' : '#1e293b',
                                    color: rejectReason ? '#ef4444' : '#64748b',
                                    fontWeight: '600',
                                    cursor: rejectReason ? 'pointer' : 'not-allowed',
                                    opacity: rejectReason ? 1 : 0.5
                                }}
                            >
                                Confirm Reject
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
