import React from 'react';
import { useAuth } from '../hooks/useAuth';
import { useNavigate } from 'react-router-dom';
import { CapitalControlsWidget } from '../components/widgets/CapitalControlsWidget';
import { TrustProgressWidget } from '../components/widgets/TrustProgressWidget';
import { useOnboarding } from '../hooks/useOnboarding';
import { useWhy } from '../contexts/WhyContext';
import { SettingsWidget } from '../components/widgets/SettingsWidget';

import { getExchanges, getUserProfile } from '../api/adapter';
import { usePolledResource } from '../hooks/usePolledResource';
import type { ExchangeConfig, UserProfile } from '../api/types';
import { getPlan } from '../domain/subscription/plans';

export const AccountPage: React.FC = () => {
    const { role, logout, adminToken, opsToken } = useAuth();
    const { isCompleted: isOnboardingComplete, status: onboardingStatus } = useOnboarding();
    const { openWhy } = useWhy();
    const navigate = useNavigate();

    const client = { role, adminToken, opsToken };
    const exchangeRes = usePolledResource<ExchangeConfig[]>((s) => getExchanges(s, client), 10000, [role]);
    const userRes = usePolledResource<UserProfile>((s) => getUserProfile(s, client), 10000, []);

    const user = userRes.data;
    const plan = getPlan(user?.tier);

    const handleUpgrade = () => {
        navigate('/account/subscription');
    };

    const handleCapabilityExplain = (cap: string, reason: string) => {
        openWhy({
            ruleId: 'TIER_RESTRICTION',
            context: `Feature "${cap}" is locked for ${plan.name} Tier. ${reason}`
        });
    };

    return (
        <div className="page-container" style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>
            <header className="flex-between mb-6">
                <div>
                    <span className="tiny font-bold uppercase badge secondary mb-2">My Institution</span>
                    <h1 style={{ margin: 0, letterSpacing: '0.1em' }} className="text-primary">ACCOUNT GOVERNANCE</h1>
                    <div className="small muted uppercase tracking-widest">Identity, Tiering & Capabilities</div>
                </div>
                <div className="flex gap-2">
                    <div className="text-right mr-4">
                        <div className="tiny muted uppercase">User Entity</div>
                        <div className="font-bold">{user ? `ID: ${user.id}` : 'LOADING...'}</div>
                    </div>
                    <button className="button danger small outline" onClick={logout}>Secure Logout</button>
                </div>
            </header>

            {!isOnboardingComplete && (
                <div className="alert warning flex-between mb-6 border-warn">
                    <div className="flex gap-4 items-center">
                        <span className="text-2xl">⚠️</span>
                        <div>
                            <strong>Onboarding Incomplete</strong>
                            <p className="small muted m-0">
                                Trading access is locked until you complete the governance setup wizard.
                            </p>
                        </div>
                    </div>
                    <button className="button primary small" onClick={() => navigate('/onboarding')}>
                        {onboardingStatus === 'IN_PROGRESS' ? 'Resume Setup' : 'Start Setup'}
                    </button>
                </div>
            )}

            <div className="layout-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(350px, 1fr) 2fr', gap: '24px' }}>

                {/* LEFT COLUMN: IDENTITY & TRUST */}
                <div className="flex-col gap-6">
                    <div className="card">
                        <div className="card-header bg-dark-2">
                            <h3>Identity Profile</h3>
                            <div className="badge secondary">{role}</div>
                        </div>
                        <div className="p-4 grid grid-cols-2 gap-4">
                            <div>
                                <div className="tiny muted uppercase mb-1">Full Name</div>
                                <div className="font-mono">{user?.email ? user.email.split('@')[0] : 'Trader'}</div>
                            </div>
                            <div>
                                <div className="tiny muted uppercase mb-1">Email</div>
                                <div className="font-mono tiny truncate">{user?.email || '...'}</div>
                            </div>
                            <div>
                                <div className="tiny muted uppercase mb-1">Member Since</div>
                                <div className="font-mono tiny">{user?.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</div>
                            </div>
                            <div>
                                <div className="tiny muted uppercase mb-1">Plan Tier</div>
                                <div className="badge primary tiny">{plan.name.toUpperCase()}</div>
                            </div>
                        </div>
                    </div>

                    <TrustProgressWidget />
                </div>

                {/* RIGHT COLUMN: CAPABILITIES & LIMITS */}
                <div className="flex-col gap-6">

                    {/* Capability Matrix (New Phase 4) */}
                    <div className="card">
                        <div className="card-header flex-between">
                            <div>
                                <h3>Capability Matrix</h3>
                                <p className="tiny muted uppercase">Feature Access By Tier</p>
                            </div>
                            <button className="button tiny secondary" onClick={handleUpgrade}>Compare Plans</button>
                        </div>
                        <table className="table w-full text-sm">
                            <thead>
                                <tr className="text-left text-muted">
                                    <th className="pl-4 pb-2">Capability</th>
                                    <th className="pb-2">Status</th>
                                    <th className="pb-2 text-right pr-4">Scope</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr className="border-b border-subtle/10">
                                    <td className="pl-4 py-3 font-bold">Manual Execution</td>
                                    <td className="py-3"><span className="badge success tiny">ENABLED</span></td>
                                    <td className="py-3 text-right pr-4 muted">Spot</td>
                                </tr>
                                <tr className="border-b border-subtle/10">
                                    <td className="pl-4 py-3 font-bold">Auto-Trading (Algo)</td>
                                    <td className="py-3">
                                        {plan.auto_allowed ? (
                                            <span className="badge success tiny">ENABLED</span>
                                        ) : (
                                            <button className="badge error tiny clickable" onClick={() => handleCapabilityExplain('Auto-Trading', 'Requires PRO Tier or higher')}>LOCKED (?)</button>
                                        )}
                                    </td>
                                    <td className="py-3 text-right pr-4 muted">Full Auto</td>
                                </tr>
                                <tr className="border-b border-subtle/10">
                                    <td className="pl-4 py-3 font-bold">Margin / Leverage</td>
                                    <td className="py-3">
                                        <button className="badge error tiny clickable" onClick={() => handleCapabilityExplain('Leverage', 'Governance Approval Pending')}>LOCKED (?)</button>
                                    </td>
                                    <td className="py-3 text-right pr-4 muted">3x - 10x</td>
                                </tr>
                                <tr className="border-b border-subtle/10">
                                    <td className="pl-4 py-3 font-bold">API Access</td>
                                    <td className="py-3"><span className="badge success tiny">ENABLED</span></td>
                                    <td className="py-3 text-right pr-4 muted">Read/Trade</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <div style={{ marginTop: '2rem' }}>
                        <SettingsWidget />
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <h3>Governance Limits</h3>
                            <p className="tiny muted uppercase">Capital & Risk Constraints</p>
                        </div>
                        <div className="p-4 grid grid-cols-2 gap-8">
                            <div>
                                <div className="flex-between mb-1">
                                    <span className="small muted">Active Capital Limit</span>
                                    <span className="font-mono font-bold">${plan.max_active_capital_usd.toLocaleString()}</span>
                                </div>
                                <div className="w-full bg-dark-3 h-1.5 rounded overflow-hidden">
                                    <div className="bg-primary h-full" style={{ width: '15%' }}></div>
                                </div>
                                <div className="tiny muted text-right mt-1">15% Used</div>
                            </div>
                            <div>
                                <div className="flex-between mb-1">
                                    <span className="small muted">Exchange Slots</span>
                                    <span className="font-mono font-bold">{exchangeRes.data?.length || 0} / {plan.max_exchanges}</span>
                                </div>
                                <div className="w-full bg-dark-3 h-1.5 rounded overflow-hidden">
                                    <div
                                        className={`h-full ${exchangeRes.data?.length === plan.max_exchanges ? 'bg-warn' : 'bg-success'}`}
                                        style={{ width: `${Math.min(100, ((exchangeRes.data?.length || 0) / plan.max_exchanges) * 100)}%` }}
                                    ></div>
                                </div>
                            </div>
                        </div>
                        <div className="p-4 border-t border-subtle/10">
                            <CapitalControlsWidget />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

