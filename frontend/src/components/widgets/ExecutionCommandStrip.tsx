import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getHealth, getOpsState, setSystemMode, setArbitrage } from '../../api/adapter';
import type { OpsState } from '../../api/types';
import { WhyPanel } from '../modals/WhyPanel';
import { AirlockModal } from '../modals/AirlockModal';
import { FlattenPortfolioModal } from '../modals/FlattenPortfolioModal';
import { usePreview } from '../../context/PreviewModeContext';
import { journalStore } from '../../store/JournalStore';

export const ExecutionCommandStrip: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };
    const { isPreview, isSimulation, simHealth, simOps, setSimExecMode, setSimGlobalStop } = usePreview();

    // Polling
    const health = usePolledResource((s) => getHealth(s, client), 5000, []);
    const ops = usePolledResource<OpsState>((s) => getOpsState(s, client), 2000, []);

    // SIMULATION FALLBACK
    const useSimData = isPreview && isSimulation && (health.error || health.data?.status !== 'ok');
    const effectiveHealth = useSimData ? simHealth : health.data;
    const effectiveOps = useSimData ? simOps : ops.data;

    // Local Journal State
    const [lastJournalEvent, setLastJournalEvent] = useState(journalStore.getLastEvent());

    useEffect(() => {
        return journalStore.subscribe(() => {
            setLastJournalEvent(journalStore.getLastEvent());
        });
    }, []);

    // Local State
    const [showAirlock, setShowAirlock] = useState(false);
    const [showFlatten, setShowFlatten] = useState(false);
    const [showWhy, setShowWhy] = useState(false);
    const [whyContext, setWhyContext] = useState<{ id: string, text: string }>({ id: '', text: '' });
    const [busy, setBusy] = useState(false);

    // Derived Logic
    const isArbOn = effectiveOps?.arb_on || false;
    const isOffline = effectiveHealth?.status !== 'ok';
    const mode = effectiveOps?.exec_mode || 'MANUAL'; // STOP, MANUAL, SEMI, AUTO
    const isStop = mode === 'STOP' || effectiveOps?.global_stop;
    const isDrift = effectiveOps?.drift_status === 'HARD' || effectiveOps?.drift_status === 'SOFT';
    const airlockStatus = effectiveOps?.airlock_status || 'NOT_READY';

    // Determine Driver
    const driver = isStop ? 'NONE' : ((mode === 'AUTO' || mode === 'SEMI') && !isDrift ? 'AI PILOT' : 'HUMAN');

    // Health Indicators
    const latency = effectiveHealth?.latency_ms ?? '—';
    const riskStatus = effectiveOps?.risk_score ? (effectiveOps.risk_score > 80 ? 'CRITICAL' : effectiveOps.risk_score > 50 ? 'WARNING' : 'OK') : 'UKN';

    // Handlers
    const handleArb = async () => {
        try {
            await setArbitrage(!isArbOn, new AbortController().signal, { role: auth.role });
            ops.refresh();
        } catch (err) {
            console.error(err);
            alert("Failed to toggle Arbitrage");
        }
    };

    const handleFlatten = () => setShowFlatten(true);

    const handleModeClick = (target: 'MANUAL' | 'SEMI' | 'AUTO') => {
        if (target === 'AUTO') {
            // Check pre-conditions
            if (isStop) {
                setWhyContext({ id: 'GLOBAL_STOP', text: 'Auto Blocked: System Halted' });
                setShowWhy(true);
                return;
            }
            if (isDrift) {
                setWhyContext({ id: 'DRIFT_LIMIT', text: 'Auto Blocked: Portfolio Drift' });
                setShowWhy(true);
                return;
            }
            // Open Airlock
            setShowAirlock(true);
        } else {
            // Direct switch for MANUAL/SEMI
            updateMode((target as any));
        }
    };

    const handleStop = async () => {
        if (!confirm("CONFIRM: EMERGENCY STOP ALL TRADING?")) return;

        if (useSimData) {
            setSimExecMode('STOP');
            setSimGlobalStop(true);
            journalStore.addLog('STOP', 'Operator triggered Emergency Stop', 'HUMAN', 'CRITICAL');
            return;
        }
        updateMode('STOP');
        journalStore.addLog('STOP', 'Operator triggered Emergency Stop (Real)', 'HUMAN', 'CRITICAL');
    };

    const updateMode = async (newMode: 'MANUAL' | 'SEMI' | 'AUTO' | 'STOP') => {
        setBusy(true);
        try {
            if (useSimData) {
                // Simulate network delay
                await new Promise(r => setTimeout(r, 600));
                setSimExecMode(newMode);
                journalStore.addLog('MODE_CHANGE', `Mode changed to ${newMode}`, 'HUMAN');
            } else {
                await setSystemMode(newMode, new AbortController().signal, client);
                ops.refresh();
                journalStore.addLog('MODE_CHANGE', `Mode changed to ${newMode} (Real)`, 'HUMAN');
            }
        } catch (e) {
            alert("Mode change failed: " + e);
        } finally {
            setBusy(false);
        }
    };

    // Last Event Display
    // Prefer backend event if recent/available, else local journal
    const displayEvent = effectiveOps?.last_governance_event || {
        message: lastJournalEvent?.message || "System Ready",
        type: lastJournalEvent?.type || "INFO",
        timestamp: lastJournalEvent?.timestamp,
        severity: lastJournalEvent?.severity || "INFO"
    };

    return (
        <>
            <div className="command-strip" style={{
                display: 'grid',
                gridTemplateColumns: 'auto 1fr auto',
                gap: '1rem',
                alignItems: 'center',
                padding: '0.5rem 1rem',
                background: 'var(--bg-panel)',
                borderBottom: '1px solid var(--border-color)',
                marginBottom: '1rem',
                borderRadius: '6px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}>
                {/* 1. LEFT: STATUS & HEALTH */}
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    <div className={`badge ${isOffline ? 'danger' : 'success'}`}>
                        {isOffline ? 'OFFLINE' : 'ONLINE'}
                    </div>

                    {/* ARBITRAGE CORE */}
                    <div className="mode-group" style={{ display: 'flex', gap: '4px', borderRight: '1px solid #333', paddingRight: '12px' }}>
                        <span className="tiny muted" style={{ alignSelf: 'center', marginRight: '4px' }}>ARB CORE</span>
                        <button
                            className={`button small ${isArbOn ? 'active-mode' : 'subtle'}`}
                            onClick={handleArb}
                            style={{
                                border: isArbOn ? '1px solid var(--accent-primary)' : '1px solid #333',
                                color: isArbOn ? 'var(--accent-primary)' : '#666'
                            }}
                        >
                            {isArbOn ? 'ON' : 'OFF'}
                        </button>
                    </div>

                    {/* EXECUTION MODE */}
                    <div className="mode-group" style={{ display: 'flex', gap: '4px' }}>
                        <div className="mini-health" style={{ display: 'flex', gap: '8px', fontSize: '10px', color: 'var(--text-muted)' }}>
                            <span title="API Latency">LAT: {latency}ms</span>
                            <span title="Risk Engine Status" style={{ color: riskStatus === 'OK' ? 'inherit' : 'var(--color-danger)' }}>
                                RISK: {riskStatus}
                            </span>
                        </div>
                    </div>

                    <div style={{ width: '1px', height: '24px', background: 'var(--border-color)' }}></div>

                    {/* Airlock Status */}
                    <div className={`badge ${airlockStatus === 'ARMED' ? 'success' : 'muted'} outline`}>
                        {airlockStatus}
                    </div>

                    {isStop && <div className="badge danger animate-pulse">GLOBAL STOP</div>}
                    {isDrift && (
                        <div
                            className="badge warning clickable"
                            onClick={() => { setWhyContext({ id: 'DRIFT_LIMIT', text: 'Drift Detected' }); setShowWhy(true); }}
                            style={{ cursor: 'pointer' }}
                        >
                            ⚠ DRIFT
                        </div>
                    )}
                </div>

                {/* 2. CENTER: MODE CONTROL (The Cockpit) */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                    <div className="button-group" style={{ display: 'flex', background: 'var(--bg-base)', padding: '2px', borderRadius: '4px' }}>
                        {['MANUAL', 'SEMI', 'AUTO'].map((m) => (
                            <button
                                key={m}
                                className={`button tiny ${mode === m ? 'primary' : 'ghost'}`}
                                onClick={() => handleModeClick(m as any)}
                                disabled={isStop || busy}
                                style={{ minWidth: '60px' }}
                            >
                                {m}
                            </button>
                        ))}
                    </div>
                    {/* Driver Indicator below buttons */}
                    <span className="tiny-label" style={{ fontSize: '9px', textTransform: 'uppercase', letterSpacing: '1px', opacity: 0.7 }}>
                        DRIVER: <span style={{ color: driver === 'AI PILOT' ? 'var(--color-primary)' : 'inherit', fontWeight: 'bold' }}>{driver}</span>
                    </span>
                </div>

                {/* 3. RIGHT: DANGER, WHY & SIGNAL */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        {isStop ? (
                            <button className="button tiny danger" onClick={handleStop} disabled>STOPPED</button>
                        ) : (
                            <button className="button tiny danger outline" onClick={handleStop}>STOP</button>
                        )}

                        <button
                            className="button secondary tiny"
                            onClick={() => { setWhyContext({ id: 'UNKNOWN', text: 'System Diagnostics' }); setShowWhy(true); }}
                        >
                            ? WHY
                        </button>
                        <button
                            className="button danger tiny outline"
                            onClick={handleFlatten}
                            title="Emergency Flatten Portfolio"
                        >
                            ⚠ FLATTEN
                        </button>
                    </div>
                    {/* Last Governance Event */}
                    <div
                        className="last-event"
                        style={{ fontSize: '10px', color: 'var(--text-muted)', maxWidth: '280px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                        title={displayEvent.message}
                    >
                        Last Event: <span style={{ color: displayEvent.severity === 'CRITICAL' ? 'var(--color-danger)' : 'inherit' }}>
                            {displayEvent.message}
                        </span>
                    </div>
                </div>
            </div>

            {/* MODALS */}
            <WhyPanel
                isOpen={showWhy}
                onClose={() => setShowWhy(false)}
                ruleId={whyContext.id}
                context={whyContext.text}
            />
            <AirlockModal
                isOpen={showAirlock}
                onCancel={() => setShowAirlock(false)}
                onConfirm={async () => {
                    await updateMode('AUTO');
                    setShowAirlock(false);
                    journalStore.addLog('AIRLOCK', 'Airlock procedure completed, AUTO mode engaged', 'HUMAN');
                }}
            />
            {showFlatten && <FlattenPortfolioModal onClose={() => setShowFlatten(false)} />}
        </>
    );
}
