import React from 'react';

interface ProposalPreviewModalProps {
    proposal: any;
    onApply: () => void;
    onCancel: () => void;
}

export const ProposalPreviewModal: React.FC<ProposalPreviewModalProps> = ({ proposal, onApply, onCancel }) => {
    if (!proposal) return null;

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(11, 15, 26, 0.95)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, backdropFilter: 'blur(4px)'
        }}>
            <div className="card" style={{ width: '500px', border: '1px solid var(--accent-primary)', padding: '24px' }}>
                <h3 style={{ color: 'var(--accent-primary)', marginBottom: '16px' }}>Proposal Preview: {proposal.id}</h3>

                <div style={{ marginBottom: '24px' }}>
                    <div className="tiny muted uppercase">Impact Analysis</div>
                    <div className="card subtle" style={{ marginTop: '8px' }}>
                        <div className="flex-row" style={{ justifyContent: 'space-between', marginBottom: '8px' }}>
                            <span>Strategies Modified</span>
                            <strong style={{ color: 'var(--accent-secondary)' }}>YES</strong>
                        </div>
                        <div className="flex-row" style={{ justifyContent: 'space-between' }}>
                            <span>Risk Confidence</span>
                            <strong style={{ color: 'var(--status-ok)' }}>{(proposal.confidence * 100).toFixed(0)}%</strong>
                        </div>
                    </div>
                </div>

                <div style={{ marginBottom: '24px' }}>
                    <div className="tiny muted uppercase">Constraints & Risks</div>
                    <ul className="list">
                        {proposal.risks.map((r: string, i: number) => (
                            <li key={i} className="tiny" style={{ color: 'var(--accent-warning)', marginTop: '4px' }}>⚠ {r}</li>
                        ))}
                    </ul>
                </div>

                <div className="flex-row" style={{ gap: '12px', justifyContent: 'flex-end', marginTop: '32px' }}>
                    <button className="button secondary" onClick={onCancel}>REJECT</button>
                    <button className="button primary" onClick={onApply}>APPLY (LOCK)</button>
                </div>
            </div>
        </div>
    );
};
