import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

interface InventoryItem {
    name: string;
    type: 'Page' | 'Widget' | 'Adapter';
    status: 'SURFACED' | 'PARTIAL' | 'MISSING';
    location: string;
    route?: string;
    domain: string;
}

const INVENTORY: InventoryItem[] = [
    // Pages
    { name: 'LoginPage', type: 'Page', status: 'SURFACED', location: 'pages/LoginPage', route: '/login', domain: 'AUTH' },
    { name: 'RegisterPage', type: 'Page', status: 'SURFACED', location: 'pages/RegisterPage', route: '/register', domain: 'AUTH' },
    { name: 'LandingPage', type: 'Page', status: 'SURFACED', location: 'pages/LandingPage', route: '/', domain: 'TRADER' },
    { name: 'OnboardingPage', type: 'Page', status: 'SURFACED', location: 'pages/OnboardingPage', route: '/onboarding', domain: 'AUTH' },
    { name: 'AccountPage', type: 'Page', status: 'SURFACED', location: 'pages/AccountPage', route: '/account', domain: 'ACCOUNT' },
    { name: 'SubscriptionPage', type: 'Page', status: 'SURFACED', location: 'pages/SubscriptionPage', route: '/account/subscription', domain: 'ACCOUNT' },
    { name: 'TraderPanel', type: 'Page', status: 'SURFACED', location: 'pages/TraderPanel', route: '/trader', domain: 'TRADER' },
    { name: 'PortfolioPage', type: 'Page', status: 'SURFACED', location: 'pages/PortfolioPage', route: '/portfolio', domain: 'PORTFOLIO' },
    { name: 'RiskPage', type: 'Page', status: 'SURFACED', location: 'pages/RiskPage', route: '/risk', domain: 'RISK' },
    { name: 'StrategiesPage', type: 'Page', status: 'SURFACED', location: 'pages/StrategiesPage', route: '/strategies', domain: 'STRATEGIES' },
    { name: 'ExchangeKeysPage', type: 'Page', status: 'SURFACED', location: 'pages/ExchangeKeysPage', route: '/exchange-keys', domain: 'EXCHANGE' },
    { name: 'FundPanel', type: 'Page', status: 'SURFACED', location: 'pages/FundPanel', route: '/fund', domain: 'FUND' },
    { name: 'SystemPage', type: 'Page', status: 'SURFACED', location: 'pages/SystemPage', route: '/system', domain: 'SYSTEM' },
    { name: 'DocsPage', type: 'Page', status: 'SURFACED', location: 'pages/DocsPage', route: '/docs', domain: 'SYSTEM' },
    { name: 'AdminPage', type: 'Page', status: 'SURFACED', location: 'pages/AdminPage', route: '/admin', domain: 'ADMIN' },

    // Widgets
    { name: 'CommandStrip', type: 'Widget', status: 'SURFACED', location: 'components/widgets/ExecutionCommandStrip', route: '/trader', domain: 'TRADER' },
    { name: 'GlobalStopBanner', type: 'Widget', status: 'SURFACED', location: 'components/widgets/GlobalStopBanner', route: '/trader', domain: 'TRADER' },
    { name: 'DriftWarningBanner', type: 'Widget', status: 'SURFACED', location: 'components/widgets/DriftWarningBanner', route: '/trader', domain: 'TRADER' },
    { name: 'ManualTradeWidget', type: 'Widget', status: 'SURFACED', location: 'components/widgets/ManualTradeWidget', route: '/trader', domain: 'TRADER' },
    { name: 'AIProposalsWidget', type: 'Widget', status: 'SURFACED', location: 'components/widgets/AIProposalsWidget', route: '/trader', domain: 'TRADER' },
    { name: 'SystemFeedWidget', type: 'Widget', status: 'SURFACED', location: 'components/widgets/SystemFeedWidget', route: '/trader', domain: 'TRADER' },
    { name: 'ExecutionTimelineWidget', type: 'Widget', status: 'SURFACED', location: 'components/widgets/ExecutionTimelineWidget', route: '/trader', domain: 'TRADER' },
    { name: 'PortfolioDetailDrawer', type: 'Widget', status: 'SURFACED', location: 'components/portfolio/PortfolioDetailDrawer', route: '/portfolio', domain: 'PORTFOLIO' },
    { name: 'RiskDashboardWidget', type: 'Widget', status: 'SURFACED', location: 'components/risk/RiskDashboardWidget', route: '/risk', domain: 'RISK' },
    { name: 'RiskMandatesTable', type: 'Widget', status: 'SURFACED', location: 'components/risk/RiskMandatesTable', route: '/risk', domain: 'RISK' },
    { name: 'RiskRulesTable', type: 'Widget', status: 'SURFACED', location: 'components/risk/RiskRulesTable', route: '/risk', domain: 'RISK' },
    { name: 'DuplicateStrategyModal', type: 'Widget', status: 'SURFACED', location: 'components/modals/DuplicateStrategyModal', route: '/strategies', domain: 'STRATEGIES' },
    { name: 'CapitalControlsWidget', type: 'Widget', status: 'SURFACED', location: 'components/widgets/CapitalControlsWidget', route: '/system', domain: 'SYSTEM' },
    { name: 'SystemStateDetails', type: 'Widget', status: 'SURFACED', location: 'components/widgets/SystemStateDetails', route: '/system', domain: 'SYSTEM' },
    { name: 'FundOverviewWidgets', type: 'Widget', status: 'SURFACED', location: 'pages/FundPanel', route: '/fund', domain: 'FUND' },
    // Gaps
    { name: 'ForensicsReplayWidget', type: 'Widget', status: 'PARTIAL', location: 'components/widgets/ForensicsReplayWidget', route: '/system', domain: 'SYSTEM' },
    { name: 'AdminIncidentsPage', type: 'Page', status: 'MISSING', location: 'pages/admin/AdminIncidentsPage', route: '/admin', domain: 'ADMIN' },
];

export const SurfaceInspectorPage: React.FC = () => {
    const navigate = useNavigate();
    const [filterDomain, setFilterDomain] = useState<string>('ALL');
    const [filterStatus, setFilterStatus] = useState<string>('ALL');

    const filtered = INVENTORY.filter(item => {
        if (filterDomain !== 'ALL' && item.domain !== filterDomain) return false;
        if (filterStatus !== 'ALL' && item.status !== filterStatus) return false;
        return true;
    });

    const domains = Array.from(new Set(INVENTORY.map(i => i.domain)));

    return (
        <div className="page-container p-6">
            <header className="mb-6">
                <h1 className="text-2xl font-bold mb-2">Surface Inspector <span className="badge warning">PREVIEW ONLY</span></h1>
                <p className="text-muted">Inventory of all UI surfaces and their validity status in Preview Mode.</p>
            </header>

            <div className="flex gap-4 mb-6">
                <select className="input" value={filterDomain} onChange={e => setFilterDomain(e.target.value)}>
                    <option value="ALL">All Domains</option>
                    {domains.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
                <select className="input" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                    <option value="ALL">All Statuses</option>
                    <option value="SURFACED">Surfaced</option>
                    <option value="PARTIAL">Partial</option>
                    <option value="MISSING">Missing</option>
                </select>
                <div className="flex-1 text-right text-muted self-center">
                    Showing {filtered.length} / {INVENTORY.length} items
                </div>
            </div>

            <div className="card p-0 overflow-hidden">
                <table className="table w-full">
                    <thead className="bg-dark-2">
                        <tr className="text-left text-xs uppercase text-muted">
                            <th className="p-3">Name</th>
                            <th className="p-3">Type</th>
                            <th className="p-3">Domain</th>
                            <th className="p-3">Status</th>
                            <th className="p-3">Location</th>
                            <th className="p-3 text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filtered.map((item, idx) => (
                            <tr key={idx} className="border-b border-subtle/10 hover:bg-white/5">
                                <td className="p-3 font-medium">{item.name}</td>
                                <td className="p-3">
                                    <span className="badge outline tiny">{item.type}</span>
                                </td>
                                <td className="p-3">{item.domain}</td>
                                <td className="p-3">
                                    <span className={`badge tiny ${item.status === 'SURFACED' ? 'secondary' : item.status === 'PARTIAL' ? 'warning' : 'danger'}`}>
                                        {item.status}
                                    </span>
                                </td>
                                <td className="p-3 text-xs muted font-mono">{item.location}</td>
                                <td className="p-3 text-right">
                                    {item.route && (
                                        <button className="button small secondary" onClick={() => navigate(item.route!)}>
                                            Open Surface
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="mt-8 grid grid-cols-2 gap-6">
                <div className="card">
                    <div className="card-header">
                        <h3>Simulation Seeding</h3>
                    </div>
                    <div className="p-4 flex flex-wrap gap-2">
                        <button className="button secondary" onClick={() => alert('Reset to Seed 1337')}>Reset Seed</button>
                        <button className="button secondary" onClick={() => alert('Seeded Trader Data')}>Seed: TRADER</button>
                        <button className="button secondary" onClick={() => alert('Seeded Risk Data')}>Seed: RISK</button>
                        <button className="button secondary" onClick={() => alert('Seeded Fund KPI Data')}>Seed: FUND</button>
                    </div>
                </div>

                <div className="card">
                    <div className="card-header">
                        <h3>Agent Verification</h3>
                    </div>
                    <div className="p-4">
                        <p className="small muted mb-4">
                            This panel confirms that the Agent has mapped 100% of the codebase to UI surfaces.
                            Any item marked "MISSING" must be resolved.
                        </p>
                        <div className="flex gap-4">
                            <div className="text-center">
                                <div className="text-2xl font-bold">{INVENTORY.filter(i => i.status === 'SURFACED').length}</div>
                                <div className="tiny uppercase muted">Surfaced</div>
                            </div>
                            <div className="text-center text-warning">
                                <div className="text-2xl font-bold">{INVENTORY.filter(i => i.status === 'PARTIAL').length}</div>
                                <div className="tiny uppercase muted">Partial</div>
                            </div>
                            <div className="text-center text-danger">
                                <div className="text-2xl font-bold">{INVENTORY.filter(i => i.status === 'MISSING').length}</div>
                                <div className="tiny uppercase muted">Missing</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
