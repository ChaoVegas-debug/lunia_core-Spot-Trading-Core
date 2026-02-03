import React, { useState, useMemo } from 'react';
import { Proposal, ProposalStatus, ProposalPriority, ProposalRiskLabel, ProposalHorizon } from '../../api/epoch_a_types';

interface ProposalInboxProps {
    proposals: Proposal[];
    isSimulated: boolean;
    onSelectProposal: (proposal: Proposal) => void;
    selectedProposalId?: string;
}

interface Filters {
    asset: string;
    status: ProposalStatus | 'ALL';
    priority: ProposalPriority | 'ALL';
    riskLabel: ProposalRiskLabel | 'ALL';
    horizon: ProposalHorizon | 'ALL';
}

type SortKey = 'priority' | 'expiration' | 'confidence';

export const ProposalInbox: React.FC<ProposalInboxProps> = ({
    proposals,
    isSimulated,
    onSelectProposal,
    selectedProposalId
}) => {
    const [filters, setFilters] = useState<Filters>({
        asset: '',
        status: 'ALL',
        priority: 'ALL',
        riskLabel: 'ALL',
        horizon: 'ALL'
    });
    const [sortBy, setSortBy] = useState<SortKey>('priority');
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

    // Filter and sort proposals
    const filteredProposals = useMemo(() => {
        let filtered = proposals.filter(p => {
            if (filters.asset && !p.asset.toLowerCase().includes(filters.asset.toLowerCase())) return false;
            if (filters.status !== 'ALL' && p.status !== filters.status) return false;
            if (filters.priority !== 'ALL' && p.priority !== filters.priority) return false;
            if (filters.riskLabel !== 'ALL' && p.riskLabel !== filters.riskLabel) return false;
            if (filters.horizon !== 'ALL' && p.horizon !== filters.horizon) return false;
            return true;
        });

        // Sort
        filtered.sort((a, b) => {
            switch (sortBy) {
                case 'priority':
                    const priorityOrder = { 'URGENT': 3, 'HIGH': 2, 'MEDIUM': 1, 'LOW': 0 };
                    return (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0);
                case 'expiration':
                    if (!a.expiresAt) return 1;
                    if (!b.expiresAt) return -1;
                    return new Date(a.expiresAt).getTime() - new Date(b.expiresAt).getTime();
                case 'confidence':
                    return b.confidence - a.confidence;
                default:
                    return 0;
            }
        });

        return filtered;
    }, [proposals, filters, sortBy]);

    const getPriorityColor = (priority: ProposalPriority) => {
        switch (priority) {
            case 'URGENT': return 'var(--accent-danger)';
            case 'HIGH': return 'var(--accent-warning)';
            case 'MEDIUM': return 'var(--accent-info)';
            case 'LOW': return '#999';
            default: return '#666';
        }
    };

    const getStatusColor = (status: ProposalStatus) => {
        switch (status) {
            case 'APPROVED': return 'var(--accent-success)';
            case 'REJECTED': return 'var(--accent-danger)';
            case 'EXPIRED': return '#666';
            case 'PENDING_USER': return 'var(--accent-warning)';
            default: return 'var(--accent-info)';
        }
    };

    const handleBulkAcknowledge = () => {
        console.log('[ProposalInbox] Bulk acknowledge:', Array.from(selectedIds));
        setSelectedIds(new Set());
    };

    const handleBulkReject = () => {
        console.log('[ProposalInbox] Bulk reject:', Array.from(selectedIds));
        setSelectedIds(new Set());
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-primary)', borderRight: '1px solid var(--border-color)' }}>
            {/* Header */}
            <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h3 style={{ margin: 0, fontSize: '1.125rem', fontWeight: '600' }}>Proposal Inbox</h3>
                    {isSimulated && (
                        <span style={{
                            background: 'rgba(245, 158, 11, 0.2)',
                            color: 'var(--accent-warning)',
                            padding: '0.25rem 0.5rem',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: '500',
                            border: '1px solid var(--accent-warning)'
                        }}>
                            SIMULATED DATA
                        </span>
                    )}
                </div>

                {/* Filters */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <input
                        type="text"
                        placeholder="Filter by asset..."
                        value={filters.asset}
                        onChange={(e) => setFilters({ ...filters, asset: e.target.value })}
                        style={{
                            padding: '0.5rem',
                            borderRadius: '4px',
                            border: '1px solid var(--border-color)',
                            background: 'var(--bg-darker)',
                            color: 'var(--text-primary)',
                            fontSize: '0.875rem'
                        }}
                    />
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                        <select
                            value={filters.status}
                            onChange={(e) => setFilters({ ...filters, status: e.target.value as any })}
                            style={{
                                padding: '0.5rem',
                                borderRadius: '4px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--bg-darker)',
                                color: 'var(--text-primary)',
                                fontSize: '0.875rem'
                            }}
                        >
                            <option value="ALL">All Status</option>
                            <option value="PENDING_USER">Pending</option>
                            <option value="APPROVED">Approved</option>
                            <option value="REJECTED">Rejected</option>
                        </select>
                        <select
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value as SortKey)}
                            style={{
                                padding: '0.5rem',
                                borderRadius: '4px',
                                border: '1px solid var(--border-color)',
                                background: 'var(--bg-darker)',
                                color: 'var(--text-primary)',
                                fontSize: '0.875rem'
                            }}
                        >
                            <option value="priority">Sort: Priority</option>
                            <option value="expiration">Sort: Expiration</option>
                            <option value="confidence">Sort: Confidence</option>
                        </select>
                    </div>
                </div>

                {/* Bulk Actions */}
                {selectedIds.size > 0 && (
                    <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
                        <button
                            onClick={handleBulkAcknowledge}
                            style={{
                                padding: '0.4rem 0.75rem',
                                borderRadius: '4px',
                                border: '1px solid var(--accent-success)',
                                background: 'rgba(34, 197, 94, 0.1)',
                                color: 'var(--accent-success)',
                                fontSize: '0.75rem',
                                fontWeight: '500',
                                cursor: 'pointer'
                            }}
                        >
                            ACK ({selectedIds.size})
                        </button>
                        <button
                            onClick={handleBulkReject}
                            style={{
                                padding: '0.4rem 0.75rem',
                                borderRadius: '4px',
                                border: '1px solid var(--accent-danger)',
                                background: 'rgba(239, 68, 68, 0.1)',
                                color: 'var(--accent-danger)',
                                fontSize: '0.75rem',
                                fontWeight: '500',
                                cursor: 'pointer'
                            }}
                        >
                            REJECT ({selectedIds.size})
                        </button>
                        <button
                            onClick={() => setSelectedIds(new Set())}
                            style={{
                                padding: '0.4rem 0.75rem',
                                borderRadius: '4px',
                                border: '1px solid var(--border-color)',
                                background: 'transparent',
                                color: 'var(--text-secondary)',
                                fontSize: '0.75rem',
                                cursor: 'pointer'
                            }}
                        >
                            Clear
                        </button>
                    </div>
                )}
            </div>

            {/* Proposal List */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
                {filteredProposals.length === 0 ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
                        <p>No proposals match criteria</p>
                    </div>
                ) : (
                    filteredProposals.map(proposal => {
                        const isSelected = selectedIds.has(proposal.id);
                        const isActive = selectedProposalId === proposal.id;

                        return (
                            <div
                                key={proposal.id}
                                onClick={() => onSelectProposal(proposal)}
                                style={{
                                    padding: '0.75rem',
                                    marginBottom: '0.5rem',
                                    borderRadius: '6px',
                                    border: `1px solid ${isActive ? 'var(--accent-primary)' : 'var(--border-color)'}`,
                                    background: isActive ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-secondary)',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s ease'
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '0.5rem' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={(e) => {
                                                e.stopPropagation();
                                                const newSelected = new Set(selectedIds);
                                                if (isSelected) newSelected.delete(proposal.id);
                                                else newSelected.add(proposal.id);
                                                setSelectedIds(newSelected);
                                            }}
                                            onClick={(e) => e.stopPropagation()}
                                        />
                                        <span style={{ fontWeight: '600', fontSize: '0.875rem' }}>{proposal.asset}</span>
                                        <span style={{
                                            fontSize: '0.75rem',
                                            fontWeight: '500',
                                            color: proposal.action === 'BUY' ? 'var(--accent-success)' : 'var(--accent-danger)'
                                        }}>
                                            {proposal.action}
                                        </span>
                                    </div>
                                    <span style={{
                                        fontSize: '0.75rem',
                                        fontWeight: '500',
                                        color: getPriorityColor(proposal.priority)
                                    }}>
                                        {proposal.priority}
                                    </span>
                                </div>

                                <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.75rem', marginBottom: '0.5rem' }}>
                                    <span style={{ color: '#999' }}>Confidence:</span>
                                    <span style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{proposal.confidence}%</span>
                                    <span style={{ color: '#999' }}>•</span>
                                    <span style={{ color: '#999' }}>R:R:</span>
                                    <span style={{ color: 'var(--text-primary)', fontWeight: '500' }}>{proposal.riskRewardRatio.toFixed(1)}</span>
                                </div>

                                <div style={{ fontSize: '0.75rem', color: '#999', marginBottom: '0.5rem', lineHeight: '1.4' }}>
                                    {proposal.thesisSummary.substring(0, 80)}...
                                </div>

                                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                    <span style={{
                                        fontSize: '0.65rem',
                                        padding: '0.125rem 0.375rem',
                                        borderRadius: '3px',
                                        background: 'rgba(100, 116, 139, 0.2)',
                                        color: '#94a3b8'
                                    }}>
                                        {proposal.horizon}
                                    </span>
                                    <span style={{
                                        fontSize: '0.65rem',
                                        padding: '0.125rem 0.375rem',
                                        borderRadius: '3px',
                                        background: getStatusColor(proposal.status) + '20',
                                        color: getStatusColor(proposal.status)
                                    }}>
                                        {proposal.status}
                                    </span>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};
