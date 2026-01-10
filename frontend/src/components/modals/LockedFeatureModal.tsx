import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { PLANS, PlanTier, getPlan } from '../../domain/subscription/plans';
import { RequestUpgradeModal } from './RequestUpgradeModal';

interface LockedFeatureModalProps {
    onClose: () => void;
    title: string;
    reason: string;
    requiredTier?: PlanTier;
}

export const LockedFeatureModal: React.FC<LockedFeatureModalProps> = ({ onClose, title, reason, requiredTier }) => {
    const { user } = useAuth();
    const [showUpgrade, setShowUpgrade] = useState(false);
    const plan = getPlan(user?.tier);

    if (showUpgrade) {
        return <RequestUpgradeModal onClose={onClose} initialTier={requiredTier} />;
    }

    return (
        <div className="modal-backdrop">
            <div className="modal-content warning-modal" style={{ maxWidth: '400px', textAlign: 'center' }}>
                <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔒</div>
                <h3>{title}</h3>
                <p className="muted" style={{ lineHeight: '1.5' }}>
                    {reason}
                </p>
                {requiredTier && (
                    <div className="alert info small mt-2">
                        Required: <strong>{PLANS[requiredTier].name.toUpperCase()}</strong> Plan<br />
                        Current: {plan.name.toUpperCase()}
                    </div>
                )}
                <div className="flex-col gap-2 mt-4">
                    <button className="button primary full-width" onClick={() => setShowUpgrade(true)}>REQUEST UPGRADE</button>
                    <button className="button ghost full-width" onClick={onClose}>CLOSE</button>
                </div>
            </div>
        </div>
    );
};
