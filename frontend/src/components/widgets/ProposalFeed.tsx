import React from 'react';
import { Proposal } from '../../api/epoch_a_types';

interface ProposalFeedProps {
    selectedProposal: Proposal | null;
    children: React.ReactNode;
}

export const ProposalFeed: React.FC<ProposalFeedProps> = ({ selectedProposal, children }) => {
    if (!selectedProposal) {
        return (
            <div style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '3rem',
                background: '#0f172a',
                color: '#64748b'
            }}>
                <div style={{ fontSize: '4rem', marginBottom: '1rem', opacity: 0.3 }}>📋</div>
                <div style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                    No Proposal Selected
                </div>
                <div style={{ fontSize: '0.875rem', maxWidth: '400px', textAlign: 'center' }}>
                    Select a proposal from the inbox to view details and take action
                </div>
            </div>
        );
    }

    return (
        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', background: '#0a0f1a' }}>
            {children}
        </div>
    );
};
