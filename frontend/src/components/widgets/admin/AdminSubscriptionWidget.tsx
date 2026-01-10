import React, { useState } from 'react';
import { useAuth } from '../../../hooks/useAuth';
import { PLANS, PlanTier, getPlan } from '../../../domain/subscription/plans';
import { ConfirmDialog } from '../../common/ConfirmDialog';

export const AdminSubscriptionWidget: React.FC = () => {
    const { user, setAuth } = useAuth();
    // Hack: For simulation, we might need to patch the localstorage or use a dev-hook.
    // Since useAuth pulls from localStorage on mount, we can update localStorage and force a reload.

    const currentTier = user?.tier || 'BEGINNER';
    const [targetTier, setTargetTier] = useState<PlanTier | null>(null);

    const handleSimulate = (tier: PlanTier) => {
        setTargetTier(tier);
    };

    const confirmSimulate = () => {
        if (!targetTier) return;

        // 1. Update Auth State via setAuth (Hot-Swap)
        if (user) {
            const updatedUser = { ...user, tier: targetTier };
            // Update Context
            setAuth((prev) => ({ ...prev, user: updatedUser }));
            // Persist (so reload keeps it)
            const stored = localStorage.getItem('lunia-auth-state');
            if (stored) {
                const auth = JSON.parse(stored);
                if (auth.user) {
                    auth.user.tier = targetTier;
                    localStorage.setItem('lunia-auth-state', JSON.stringify(auth));
                }
            }
            setTargetTier(null);
        }
    };

    return (
        <div className="card" style={{ border: '1px dashed var(--accent-warning)' }}>
            <div className="card-header">
                <h3>Subscription Simulator</h3>
                <span className="badge warning">DEV TOOLS</span>
            </div>

            <p className="small muted">
                Force your session into a specific Tier to test guardrails.
                (Requires Page Reload)
            </p>

            <div className="grid cols-4" style={{ gap: '0.5rem', marginTop: '1rem' }}>
                {Object.values(PLANS).map(p => (
                    <button
                        key={p.id}
                        className={`button ${currentTier === p.id ? 'primary' : 'secondary'} tiny`}
                        onClick={() => handleSimulate(p.id)}
                    >
                        {p.name}
                    </button>
                ))}
            </div>

            {targetTier && (
                <ConfirmDialog
                    title="Simulate Tier Change?"
                    message={`Switch local session to ${PLANS[targetTier].name}? Page will reload.`}
                    onConfirm={confirmSimulate}
                    onCancel={() => setTargetTier(null)}
                />
            )}
        </div>
    );
};
