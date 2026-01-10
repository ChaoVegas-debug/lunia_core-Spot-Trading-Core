import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { PLANS, getPlan, PlanTier } from '../domain/subscription/plans';
import { useNavigate } from 'react-router-dom';
import { requestUpgrade, getUserProfile } from '../api/adapter';
import { usePolledResource } from '../hooks/usePolledResource';
import type { UserProfile } from '../api/types';

export const SubscriptionPage: React.FC = () => {
    const { role } = useAuth();
    // Re-fetch user to ensure fresh tier if it changed (simulated)
    const userRes = usePolledResource<UserProfile>((s) => getUserProfile(s, { role }), 10000, []);
    const user = userRes.data;
    const currentPlan = getPlan(user?.tier);
    const navigate = useNavigate();

    const [isUpgrading, setIsUpgrading] = useState(false);

    // Helper to render check/cross
    const BoolIcon = ({ val }: { val: boolean }) => (
        <span style={{ color: val ? 'var(--accent-ok)' : 'var(--text-muted)' }}>{val ? '✓' : '—'}</span>
    );

    const handleUpgradeRequest = async (targetTier: string) => {
        setIsUpgrading(true);
        if (!confirm(`Request upgrade to ${targetTier}? Compliance team will review this action.`)) {
            setIsUpgrading(false);
            return;
        }

        try {
            await requestUpgrade(targetTier, new AbortController().signal);
            alert(`Upgrade Request Logged for ${targetTier}. Compliance has been notified.`);
            // In a real app we might poll or wait for WebSocket, here we just show success.
        } catch (e) {
            alert("Upgrade request failed or requires manual sales contact.");
        } finally {
            setIsUpgrading(false);
        }
    };

    return (
        <div className="page-container" style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>

            <header className="flex-between mb-8">
                <div>
                    <button onClick={() => navigate('/account')} className="button ghost small mb-2">← Back to Cabinet</button>
                    <h1>Subscription & Limits</h1>
                    <p className="muted">Manage your institutional access tier and capabilities.</p>
                </div>
                <div className="text-right">
                    <div className="small muted uppercase">Current Plan</div>
                    <div className="badge primary large">{currentPlan.name.toUpperCase()}</div>
                </div>
            </header>

            <div className="card mb-8">
                <div className="card-header">
                    <h3>Plan Capabilities</h3>
                </div>
                <div style={{ overflowX: 'auto' }}>
                    <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr>
                                <th style={{ textAlign: 'left', padding: '12px' }}>Feature</th>
                                {Object.values(PLANS).map(p => (
                                    <th key={p.id} style={{
                                        textAlign: 'center',
                                        padding: '12px',
                                        background: p.id === currentPlan.id ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                                        borderBottom: p.id === currentPlan.id ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)'
                                    }}>
                                        {p.name}
                                        {p.id === currentPlan.id && <div className="tiny text-primary uppercase">Current</div>}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td className="muted">Monthly Fee</td>
                                <td className="text-center">$0 (Free)</td>
                                <td className="text-center">$49</td>
                                <td className="text-center">$199</td>
                                <td className="text-center">Contact Sales</td>
                            </tr>
                            <tr>
                                <td className="muted">Active Capital Limit</td>
                                {Object.values(PLANS).map(p => (
                                    <td key={p.id} className="text-center text-mono">${p.max_active_capital_usd.toLocaleString()}</td>
                                ))}
                            </tr>
                            <tr>
                                <td className="muted">Exchange Connections</td>
                                {Object.values(PLANS).map(p => (
                                    <td key={p.id} className="text-center">{p.max_exchanges}</td>
                                ))}
                            </tr>
                            <tr>
                                <td className="muted">Portfolio Limit</td>
                                {Object.values(PLANS).map(p => (
                                    <td key={p.id} className="text-center">{p.max_portfolios}</td>
                                ))}
                            </tr>
                            <tr>
                                <td className="muted">Auto-Trading (Algo)</td>
                                {Object.values(PLANS).map(p => (
                                    <td key={p.id} className="text-center">
                                        <BoolIcon val={p.auto_allowed} />
                                    </td>
                                ))}
                            </tr>
                            <tr>
                                <td className="muted">Risk Profiles</td>
                                {Object.values(PLANS).map(p => (
                                    <td key={p.id} className="text-center small">
                                        {p.allowed_risk_profiles.includes('ROCKET') ? 'Full Suite' :
                                            p.allowed_risk_profiles.includes('AGGRESSIVE') ? 'Advanced' : 'Conservative'}
                                    </td>
                                ))}
                            </tr>
                            <tr>
                                <td></td>
                                {Object.values(PLANS).map(p => (
                                    <td key={p.id} className="text-center" style={{ padding: '16px' }}>
                                        {p.id === currentPlan.id ? (
                                            <span className="tiny muted">Active</span>
                                        ) : (
                                            <button
                                                className="button secondary tiny"
                                                disabled={isUpgrading}
                                                onClick={() => handleUpgradeRequest(p.id)}
                                            >
                                                {p.max_active_capital_usd > currentPlan.max_active_capital_usd ? 'Request Upgrade' : 'Contact'}
                                            </button>
                                        )}
                                    </td>
                                ))}
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="grid cols-2" style={{ gap: '2rem' }}>
                <div className="card">
                    <div className="p-4 bg-dark-2">
                        <strong className="text-primary">Enterprise Customization</strong>
                        <p className="small muted">
                            For funds managing &gt;$10M AUM, we offer dedicated infrastructure, white-glove onboarding, and custom algo development support.
                        </p>
                        <button className="button secondary small item-right mt-2" onClick={() => handleUpgradeRequest('INST_LITE')}>Contact Institutional Sales</button>
                    </div>
                </div>

                <div className="alert danger">
                    <h4 className="m-0 mb-2">Compliance Notice</h4>
                    <p className="small m-0">
                        Upgrading your plan <strong>does not bypass Risk Engine constraints</strong> or Global Mandates. All accounts, regardless of tier, are subject to the same Safety & Governance invariants (Drawdown limits, Airlock checks, and Veto rights).
                    </p>
                </div>
            </div>
        </div>
    );
};

