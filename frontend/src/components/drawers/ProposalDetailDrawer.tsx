import React, { useState } from 'react';
import { Proposal, ProposalApprovalGates } from '../../api/epoch_a_types';

interface ProposalDetailDrawerProps {
    proposal: Proposal | null;
    gates: ProposalApprovalGates | null;
    onClose: () => void;
}

type TabKey = 'summary' | 'analysis' | 'ghost' | 'risk' | 'execution' | 'governance' | 'models' | 'audit';

export const ProposalDetailDrawer: React.FC<ProposalDetailDrawerProps> = ({
    proposal,
    gates,
    onClose
}) => {
    const [activeTab, setActiveTab] = useState<TabKey>('summary');

    if (!proposal || !gates) return null;

    const tabs: Array<{ key: TabKey; label: string; functional: boolean }> = [
        { key: 'summary', label: 'Summary', functional: true },
        { key: 'analysis', label: 'Analysis', functional: false },
        { key: 'ghost', label: 'Ghost Test', functional: false },
        { key: 'risk', label: 'Risk', functional: false },
        { key: 'execution', label: 'Execution', functional: false },
        { key: 'governance', label: 'Governance', functional: true },
        { key: 'models', label: 'Models', functional: false },
        { key: 'audit', label: 'Audit', functional: true }
    ];

    const renderTabContent = () => {
        switch (activeTab) {
            case 'summary':
                return renderSummaryTab();
            case 'governance':
                return renderGovernanceTab();
            case 'audit':
                return renderAuditTab();
            default:
                return renderStubTab(activeTab);
        }
    };

    const renderSummaryTab = () => (
        <div style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1.5rem', color: '#f1f5f9', fontSize: '1.25rem' }}>
                {proposal.asset} {proposal.action} Proposal
            </h3>

            <div style={{ marginBottom: '1.5rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.5rem', fontWeight: '600', letterSpacing: '0.05em' }}>
                    THESIS
                </div>
                <div style={{ color: '#cbd5e1', fontSize: '1rem', lineHeight: '1.6' }}>
                    {proposal.thesisSummary}
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                {[
                    { label: 'Confidence', value: `${proposal.confidence}%`, color: '#3b82f6' },
                    { label: 'R:R', value: proposal.riskRewardRatio.toFixed(1), color: '#10b981' },
                    { label: 'Risk Label', value: proposal.riskLabel.replace('_', ' '), color: '#f59e0b' },
                    { label: 'Horizon', value: proposal.horizon, color: '#8b5cf6' },
                    { label: 'Priority', value: proposal.priority, color: '#ef4444' },
                    { label: 'Status', value: proposal.status.replace('_', ' '), color: '#64748b' }
                ].map(metric => (
                    <div key={metric.label} style={{ padding: '0.75rem', background: '#1e293b', borderRadius: '6px' }}>
                        <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>
                            {metric.label}
                        </div>
                        <div style={{ fontSize: '1.125rem', fontWeight: '600', color: metric.color }}>
                            {metric.value}
                        </div>
                    </div>
                ))}
            </div>

            <div>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem', fontWeight: '600', letterSpacing: '0.05em' }}>
                    FACTOR BREAKDOWN
                </div>
                {proposal.factorAttribution.map((factor, idx) => (
                    <div key={idx} style={{ marginBottom: '0.75rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                            <span style={{ fontSize: '0.875rem', color: '#94a3b8' }}>{factor.factor}</span>
                            <span style={{ fontSize: '0.875rem', color: '#f1f5f9', fontWeight: '500' }}>
                                {factor.weight}% (conf: {factor.confidence}%)
                            </span>
                        </div>
                        <div style={{ height: '6px', background: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{
                                width: `${factor.weight}%`,
                                height: '100%',
                                background: `hsl(${idx * 60}, 70%, 50%)`,
                                boxShadow: `0 0 8px hsl(${idx * 60}, 70%, 50%)`
                            }} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );

    const renderGovernanceTab = () => (
        <div style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1.5rem', color: '#f1f5f9', fontSize: '1.25rem' }}>
                Governance Gate Snapshot
            </h3>

            <div style={{
                padding: '1rem',
                background: '#1e293b',
                borderRadius: '8px',
                marginBottom: '1.5rem',
                border: '1px solid #334155'
            }}>
                <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.75rem', fontWeight: '600' }}>
                    SNAPSHOT TIMESTAMP
                </div>
                <div style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                    {new Date().toISOString()}
                </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {[
                    { label: 'Global Stop', value: gates.global_stop ? 'ACTIVE' : 'OFF', passed: !gates.global_stop },
                    { label: 'System Mode', value: gates.system_mode, passed: gates.system_mode !== 'STOP' },
                    { label: 'Run Mode', value: gates.run_mode.toUpperCase(), passed: true },
                    { label: 'Airlock Status', value: gates.airlock_status, passed: gates.airlock_status === 'ARMED' },
                    { label: 'Data Freshness', value: gates.freshness, passed: gates.freshness === 'FRESH' },
                    { label: 'Live Allowed', value: gates.live_allowed ? 'YES' : 'NO', passed: gates.live_allowed || gates.run_mode === 'dry' },
                    { label: 'Drift Status', value: gates.drift_status || 'NONE', passed: !gates.drift_status || gates.drift_status === 'NONE' }
                ].map(gate => (
                    <div
                        key={gate.label}
                        style={{
                            padding: '0.75rem',
                            background: gate.passed ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                            border: `1px solid ${gate.passed ? '#10b981' : '#ef4444'}`,
                            borderRadius: '6px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                        }}
                    >
                        <span style={{ color: '#94a3b8', fontSize: '0.875rem', fontWeight: '500' }}>{gate.label}</span>
                        <span style={{
                            color: gate.passed ? '#10b981' : '#ef4444',
                            fontSize: '0.875rem',
                            fontWeight: '600'
                        }}>
                            {gate.value}
                        </span>
                    </div>
                ))}
            </div>

            {gates.veto_reason && (
                <div style={{
                    marginTop: '1.5rem',
                    padding: '1rem',
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid #ef4444',
                    borderRadius: '8px'
                }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#ef4444', marginBottom: '0.5rem' }}>
                        VETO REASON
                    </div>
                    <div style={{ color: '#fca5a5', fontSize: '0.875rem' }}>
                        {gates.veto_reason}
                    </div>
                </div>
            )}

            <div style={{
                marginTop: '1.5rem',
                padding: '1rem',
                background: gates.canApprove ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${gates.canApprove ? '#10b981' : '#ef4444'}`,
                borderRadius: '8px'
            }}>
                <div style={{ fontSize: '0.875rem', fontWeight: '600', color: gates.canApprove ? '#10b981' : '#ef4444', marginBottom: '0.5rem' }}>
                    {gates.canApprove ? '✓ APPROVAL ALLOWED' : '✗ APPROVAL BLOCKED'}
                </div>
                {!gates.canApprove && gates.blockReasons.length > 0 && (
                    <div style={{ fontSize: '0.8125rem', color: '#fca5a5' }}>
                        {gates.blockReasons.join('; ')}
                    </div>
                )}
            </div>
        </div>
    );

    const renderAuditTab = () => {
        // Simulated audit trail
        const auditEvents = [
            { ts: proposal.createdAt, action: 'CREATED', user: 'AI_ENGINE', details: 'Proposal generated from signal fusion' },
            { ts: proposal.createdAt, action: 'VALIDATED', user: 'RISK_ENGINE', details: 'Risk parameters validated' },
            { ts: proposal.updatedAt, action: 'REVIEWED', user: 'SYSTEM', details: 'Gate checks executed' },
            ...(proposal.approvedAt ? [{ ts: proposal.approvedAt, action: 'APPROVED', user: 'TRADER', details: 'Manual approval granted' }] : []),
            ...(proposal.rejectedAt ? [{ ts: proposal.rejectedAt, action: 'REJECTED', user: 'TRADER', details: proposal.rejectionReason || 'Manual rejection' }] : [])
        ];

        return (
            <div style={{ padding: '1.5rem' }}>
                <div style={{
                    padding: '1rem',
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid #f59e0b',
                    borderRadius: '8px',
                    marginBottom: '1.5rem'
                }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#f59e0b', marginBottom: '0.25rem' }}>
                        ⚠️ UI-Level Event Buffer
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        Not connected to immutable audit chain. EPOCH C will integrate tamper-proof audit backend.
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {auditEvents.map((event, idx) => (
                        <div
                            key={idx}
                            style={{
                                padding: '0.75rem',
                                background: '#1e293b',
                                border: '1px solid #334155',
                                borderRadius: '6px'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                                <span style={{ fontSize: '0.75rem', fontWeight: '600', color: '#3b82f6' }}>
                                    {event.action}
                                </span>
                                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                    {new Date(event.ts).toLocaleString()}
                                </span>
                            </div>
                            <div style={{ fontSize: '0.8125rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                                User: {event.user}
                            </div>
                            <div style={{ fontSize: '0.8125rem', color: '#cbd5e1' }}>
                                {event.details}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    const renderStubTab = (tab: TabKey) => {
        const stubs: Record<string, { epoch: string; api: string; bullets: string[] }> = {
            analysis: {
                epoch: 'EPOCH B',
                api: 'Evidence Payload API',
                bullets: [
                    'Factor deep-dive with source attribution',
                    'Competitive landscape positioning',
                    'Historical performance of similar signals',
                    'Real-time news / sentiment integration',
                    'Technical + fundamental correlation matrix'
                ]
            },
            ghost: {
                epoch: 'EPOCH B',
                api: 'Ghost Test Engine',
                bullets: [
                    'Simulate execution across liquidity pools',
                    'Estimate slippage and execution quality',
                    'Identify potential conflicts with active positions',
                    'Test different size scenarios (10% / 50% / 100%)',
                    'Real-time market impact simulation'
                ]
            },
            risk: {
                epoch: 'EPOCH B/C',
                api: 'Risk Engine + Portfolio Analytics',
                bullets: [
                    'Portfolio-level VAR / CVaR impact',
                    'Correlation with existing positions',
                    'Margin / leverage impact analysis',
                    'Worst-case drawdown scenarios',
                    'Compliance with risk limits and mandates'
                ]
            },
            execution: {
                epoch: 'EPOCH C',
                api: 'Execution Planner + Orchestrator',
                bullets: [
                    'Execution plan with time slicing',
                    'Multi-venue routing options',
                    'TWAP / VWAP / Adaptive algo selection',
                    'Expected vs. actual execution tracking',
                    'Kill switches and safety stops'
                ]
            },
            models: {
                epoch: 'EPOCH D',
                api: 'Model Registry + Biological Governance',
                bullets: [
                    'Model lineage and provenance',
                    'Model health and degradation metrics',
                    'Feature importance and drift tracking',
                    'Ensemble composition and weighting',
                    'Live performance vs. backtest comparison'
                ]
            }
        };

        const stub = stubs[tab];

        return (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📊</div>
                <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#f59e0b', marginBottom: '0.5rem' }}>
                    {stub.epoch}: {stub.api}
                </div>
                <div style={{ fontSize: '0.875rem', color: '#94a3b8', marginBottom: '2rem' }}>
                    This tab will be functional once backend integration is complete
                </div>

                <div style={{
                    maxWidth: '500px',
                    margin: '0 auto',
                    textAlign: 'left',
                    padding: '1.5rem',
                    background: '#1e293b',
                    borderRadius: '8px',
                    border: '1px solid #334155'
                }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#cbd5e1', marginBottom: '1rem' }}>
                        What will appear here:
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.5rem', color: '#94a3b8', fontSize: '0.8125rem', lineHeight: '1.8' }}>
                        {stub.bullets.map((bullet, idx) => (
                            <li key={idx}>{bullet}</li>
                        ))}
                    </ul>
                </div>

                <div style={{
                    marginTop: '1.5rem',
                    padding: '1rem',
                    background: 'rgba(59, 130, 246, 0.1)',
                    border: '1px solid #3b82f6',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    color: '#93c5fd'
                }}>
                    💡 UI structure is ready - backend contract needed
                </div>
            </div>
        );
    };

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                right: 0,
                bottom: 0,
                width: '600px',
                maxWidth: '90vw',
                background: '#0f172a',
                borderLeft: '1px solid #1e293b',
                boxShadow: '-4px 0 12px rgba(0, 0, 0, 0.5)',
                zIndex: 100,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden'
            }}
        >
            {/* Header */}
            <div style={{
                padding: '1.5rem',
                borderBottom: '1px solid #1e293b',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)'
            }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: '700', color: '#f1f5f9' }}>
                        Proposal Details
                    </h2>
                    <div style={{ fontSize: '0.875rem', color: '#64748b', marginTop: '0.25rem' }}>
                        {proposal.asset} • {proposal.action}
                    </div>
                </div>
                <button
                    onClick={onClose}
                    style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#94a3b8',
                        fontSize: '2rem',
                        cursor: 'pointer',
                        padding: '0',
                        lineHeight: 1
                    }}
                >
                    ×
                </button>
            </div>

            {/* Tabs */}
            <div style={{
                display: 'flex',
                gap: '0.25rem',
                padding: '0.5rem 1rem',
                borderBottom: '1px solid #1e293b',
                background: '#0a0f1a',
                overflowX: 'auto'
            }}>
                {tabs.map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        style={{
                            padding: '0.5rem 1rem',
                            borderRadius: '6px 6px 0 0',
                            border: 'none',
                            background: activeTab === tab.key ? '#1e293b' : 'transparent',
                            color: activeTab === tab.key ? '#f1f5f9' : '#64748b',
                            fontWeight: activeTab === tab.key ? '600' : '400',
                            fontSize: '0.8125rem',
                            cursor: 'pointer',
                            position: 'relative',
                            whiteSpace: 'nowrap'
                        }}
                    >
                        {tab.label}
                        {!tab.functional && (
                            <span style={{
                                marginLeft: '0.25rem',
                                fontSize: '0.65rem',
                                color: '#f59e0b',
                                fontWeight: '500'
                            }}>
                                ⏸
                            </span>
                        )}
                    </button>
                ))}
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflowY: 'auto' }}>
                {renderTabContent()}
            </div>
        </div>
    );
};
