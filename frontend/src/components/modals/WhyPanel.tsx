import React from 'react';
import { getRule } from '../../governance/rulebook';

interface WhyPanelProps {
    isOpen: boolean;
    onClose: () => void;
    ruleId?: string;
    context?: string; // e.g., "Trade Vetoed", "Auto Blocked"
}

export const WhyPanel: React.FC<WhyPanelProps> = ({ isOpen, onClose, ruleId, context }) => {
    if (!isOpen) return null;

    const rule = getRule(ruleId || 'UNKNOWN');
    const color = rule.severity === 'FATAL' ? 'var(--accent-danger)' : (rule.severity === 'CRITICAL' ? 'var(--accent-warning)' : 'var(--text-primary)');

    return (
        <div style={{
            position: 'fixed',
            top: 0, right: 0, bottom: 0,
            width: '400px',
            background: 'var(--bg-card)',
            borderLeft: '1px solid var(--border-color)',
            boxShadow: '-10px 0 30px rgba(0,0,0,0.5)',
            zIndex: 10000,
            padding: '2rem',
            display: 'flex',
            flexDirection: 'column',
            transform: isOpen ? 'translateX(0)' : 'translateX(100%)', // Simple visibility toggle for now
            transition: 'transform 0.3s ease'
        }}>
            <button
                onClick={onClose}
                style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.5rem' }}
            >
                ×
            </button>

            <div style={{ marginBottom: '2rem' }}>
                <div className="tiny font-bold uppercase tracking-widest muted mb-2">EXPLAINABILITY LAYER</div>
                <h2 style={{ color }}>{context || "Governance Interventions"}</h2>
            </div>

            <div className="card" style={{ borderLeft: `4px solid ${color}`, marginBottom: '2rem' }}>
                <div className="flex-between mb-2">
                    <h3 style={{ margin: 0 }}>{rule.title}</h3>
                    <span className="badge" style={{ background: color, color: '#000' }}>{rule.id}</span>
                </div>
                <p>{rule.description}</p>
            </div>

            <div>
                <h4 className="mb-4">Recovery Protocol</h4>
                <ul className="list-disc pl-4" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {rule.recoverySteps.map((step, i) => (
                        <li key={i} className="small">{step}</li>
                    ))}
                </ul>
            </div>

            <div style={{ marginTop: 'auto' }}>
                <div className="alert info small">
                    <strong>Institutional Audit Trail:</strong> This event has been logged to the immutable ledger.
                </div>
                <button className="button full-width mt-4" onClick={onClose}>Acknowledge</button>
            </div>
        </div>
    );
};
