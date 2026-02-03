import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RiskDashboardWidget } from '../components/risk/RiskDashboardWidget';
import { RiskRulesTable } from '../components/risk/RiskRulesTable';
import { RiskMandatesTable } from '../components/risk/RiskMandatesTable';
import { usePoller } from '../hooks/usePoller';
import { getSystemEvents } from '../api/adapter';
import type { SystemEvent } from '../api/types';
import { useLocation } from 'react-router-dom';
import { useDashboard } from '../context/DashboardContext';

export const RiskPage: React.FC = () => {
    const location = useLocation() as { state: any };
    const navigate = useNavigate();
    const { data: eventsData, error: eventsError, refresh: eventsRefresh } = usePoller({
        key: 'risk_page_events',
        endpoint: '/api/events/system',
        fetcher: () => getSystemEvents(new AbortController().signal, { role: 'admin' }),
        interval_ms: 2000,
        critical: false
    });
    const events = { data: eventsData, error: eventsError, loading: false, refresh: eventsRefresh };
    const { addToast } = useDashboard();
    const [tab, setTab] = useState<'DASHBOARD' | 'RULES' | 'LOGS'>('DASHBOARD');

    const riskEvents = React.useMemo(() => {
        if (!events.data?.items) return [];
        return events.data.items.filter((e: SystemEvent) => e.type === 'RISK_VETO' || e.type === 'RISK_LIMIT_UPDATE' || e.type === 'RISK_WARN');
    }, [events.data]);

    const lastEvent = riskEvents.length > 0 ? riskEvents[riskEvents.length - 1] : null;

    return (
        <div className="page-container" style={{ padding: '24px', maxWidth: '1600px', margin: '0 auto' }}>
            <header className="flex-between mb-6">
                <div>
                    {location.state?.tourActive && location.state?.stepId === 'risk-limits' && (
                        <div style={{ marginBottom: '8px' }}>
                            <span className="tiny font-bold uppercase badge primary">Step 4: Risk Guardrails</span>
                        </div>
                    )}
                    <h1 style={{ margin: 0, letterSpacing: '0.1em' }} className="text-warn">RISK GOVERNANCE</h1>
                    <div className="small muted uppercase tracking-widest">Global Limits & Stop-Loss Configuration</div>
                </div>
                <div className="text-right">
                    <div className="tiny muted uppercase">Last Risk Event</div>
                    <div className="font-bold text-warn">{lastEvent ? `${lastEvent.type} @ ${new Date(lastEvent.timestamp).toLocaleTimeString()}` : 'None'}</div>
                </div>
            </header>

            {/* Navigation Tabs */}
            <div className="tabs mb-4 border-b border-subtle flex gap-6">
                <button className={`pb-2 ${tab === 'DASHBOARD' ? 'border-b-2 border-primary font-bold' : 'muted'}`} onClick={() => setTab('DASHBOARD')}>Dashboard</button>
                <button className={`pb-2 ${tab === 'RULES' ? 'border-b-2 border-primary font-bold' : 'muted'}`} onClick={() => setTab('RULES')}>Rules & Mandates</button>
                <button className={`pb-2 ${tab === 'LOGS' ? 'border-b-2 border-primary font-bold' : 'muted'}`} onClick={() => setTab('LOGS')}>Veto Log</button>
            </div>

            <div className="layout-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 1fr) 3fr', gap: '24px' }}>

                {/* Left Column: Mandates (Always Visible) */}
                <div className="flex-col gap-4">
                    <RiskMandatesTable />

                    {/* Quick Actions (Mock Remediation) */}
                    <div className="card">
                        <div className="card-header">
                            <h3>Remediation</h3>
                            <p className="small muted">Quick Navigation</p>
                        </div>
                        <div className="p-3 flex flex-col gap-2">
                            <button className="button secondary small w-full text-left" onClick={() => navigate('/portfolio', { state: { action: 'DERISK' } })}>
                                ⚠️ De-Risk Portfolios
                            </button>
                            <button className="button secondary small w-full text-left" onClick={() => navigate('/system')}>
                                🛑 System Halt
                            </button>
                        </div>
                    </div>
                </div>

                {/* Right Column: Main Content */}
                <div className="flex-col gap-4">

                    {tab === 'DASHBOARD' && (
                        <RiskDashboardWidget />
                    )}

                    {tab === 'RULES' && (
                        <RiskRulesTable />
                    )}

                    {tab === 'LOGS' && (
                        <div className="card">
                            <div className="card-header">
                                <h3>Veto & Exception Log</h3>
                                <p className="tiny muted uppercase">Rejections enforced by Risk Engine</p>
                            </div>

                            <div className="table-container" style={{ maxHeight: '600px', overflowY: 'auto' }}>
                                {riskEvents.length === 0 ? (
                                    <div className="p-8 muted small text-center border-dashed border-2 m-4 rounded">No risk veto events recorded in current session.</div>
                                ) : (
                                    <table className="table w-full text-sm">
                                        <thead>
                                            <tr className="text-left text-muted">
                                                <th className="pl-4">Time</th>
                                                <th>Type</th>
                                                <th>Payload / Reason</th>
                                                <th>Action</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {riskEvents.slice().reverse().map((e: SystemEvent) => (
                                                <tr key={e.id} className="border-b border-subtle/10 hover:bg-deep/50">
                                                    <td className="pl-4 font-mono text-muted">{new Date(e.timestamp).toLocaleTimeString()}</td>
                                                    <td className="font-bold text-warn">{e.type}</td>
                                                    <td className="text-muted text-xs font-mono">{JSON.stringify(e.payload)}</td>
                                                    <td>
                                                        <button className="button tiny secondary" onClick={() => {
                                                            console.log('Risk Event Payload:', e);
                                                            addToast({ type: 'INFO', message: 'Event details logged to console' });
                                                        }}>Inspect</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

