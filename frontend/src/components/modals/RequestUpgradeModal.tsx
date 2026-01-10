import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { PLANS, PlanTier } from '../../domain/subscription/plans';

interface RequestUpgradeModalProps {
    onClose: () => void;
    initialTier?: PlanTier;
}

export const RequestUpgradeModal: React.FC<RequestUpgradeModalProps> = ({ onClose, initialTier = 'ADV_RETAIL' }) => {
    const { user } = useAuth();
    const [tier, setTier] = useState<PlanTier>(initialTier);
    const [message, setMessage] = useState('');
    const [sent, setSent] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        // Honest UI: No backend endpoint exists yet, so we log and show mailto.
        console.log("Upgrade Request:", {
            user_id: user?.id,
            current_tier: user?.tier,
            requested_tier: tier,
            message
        });
        setSent(true);
    };

    const handleMailto = () => {
        const subject = `Upgrade Request: ${user?.email}`;
        const body = `I would like to upgrade to ${PLANS[tier].name}.\n\nMessage: ${message}\n\nUser ID: ${user?.id}`;
        window.location.href = `mailto:sales@lunia.fi?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    };

    if (sent) {
        return (
            <div className="modal-backdrop">
                <div className="modal-content" style={{ maxWidth: '450px', textAlign: 'center' }}>
                    <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📫</div>
                    <h3>Request Logged</h3>
                    <p className="muted">
                        Our institution team has been notified.
                        To speed up the process, please email us directly.
                    </p>
                    <div className="flex-col gap-2 mt-4">
                        <button className="button primary full-width" onClick={handleMailto}>OPEN EMAIL CLIENT</button>
                        <button className="button ghost full-width" onClick={onClose}>CLOSE</button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="modal-backdrop">
            <div className="modal-content" style={{ width: '500px' }}>
                <div className="card-header">
                    <h3>Request Upgrade</h3>
                    <button className="button text-only" onClick={onClose}>×</button>
                </div>
                <form onSubmit={handleSubmit} style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div>
                        <label className="small muted uppercase">Current Plan</label>
                        <div className="font-mono">{PLANS[user?.tier || 'BEGINNER'].name}</div>
                    </div>

                    <div>
                        <label className="small muted uppercase">Requested Plan</label>
                        <select
                            className="input full-width"
                            value={tier}
                            onChange={(e) => setTier(e.target.value as PlanTier)}
                        >
                            {Object.values(PLANS).map(p => (
                                <option key={p.id} value={p.id} disabled={p.id === user?.tier}>
                                    {p.name.toUpperCase()} {p.id === user?.tier ? '(Current)' : ''}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="small muted uppercase">Use Case / Message</label>
                        <textarea
                            className="input full-width"
                            rows={4}
                            placeholder="I need higher limits for..."
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                        />
                    </div>

                    <div className="alert info small">
                        <strong>Governance Note:</strong> Upgrading increases limits but does not remove Risk Engine vetoes.
                    </div>

                    <div className="flex-end gap-2 mt-2">
                        <button type="button" className="button ghost" onClick={onClose}>CANCEL</button>
                        <button type="submit" className="button primary">SEND REQUEST</button>
                    </div>
                </form>
            </div>
        </div>
    );
};
