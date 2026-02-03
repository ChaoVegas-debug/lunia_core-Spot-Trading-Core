import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { usePoller } from '../../hooks/usePoller';
import { getHealth, getOpsState, setSystemMode, setArbitrage, opsStart, getOpsRunState } from '../../api/adapter';
import type { OpsState, OpsRunState } from '../../api/types';
import { WhyPanel } from '../modals/WhyPanel';
import { StartConfirmationModal } from '../modals/StartConfirmationModal';
import { useDashboard } from '../../context/DashboardContext';
import { FlattenPortfolioModal } from '../modals/FlattenPortfolioModal';
import { usePreview } from '../../context/PreviewModeContext';
import { journalStore } from '../../store/JournalStore';
import { openAirlock } from '../../lib/airlock/airlockHelper';

export const ExecutionCommandStrip: React.FC = () => {
    const auth = useAuth();
    const client = { role: auth.role, opsToken: auth.opsToken };
    const { isPreview, isSimulation, simHealth, simOps, setSimExecMode, setSimGlobalStop } = usePreview();
    const { addToast } = useDashboard();

    // Polling - MIGRATED to canonical usePoller
    const { data: healthData, error: healthError, refresh: healthRefresh } = usePoller({
        key: 'exec_strip_health',
        endpoint: '/api/health',
        fetcher: () => getHealth(new AbortController().signal, client),
        interval_ms: 5000,
        critical: false
    });
    const health = { data: healthData, error: healthError, loading: false, refresh: healthRefresh };

    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'exec_strip_ops',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 2000,
        critical: true  // Core system health
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

    // SIMULATION FALLBACK
    const useSimData = isPreview && isSimulation && (health.error || health.data?.status !== 'ok');
    const effectiveHealth = useSimData ? simHealth : health.data;
    const effectiveOps = useSimData ? simOps : ops.data;

    // Local Journal State
    const [lastJournalEvent, setLastJournalEvent] = useState(journalStore.getLastEvent());

    useEffect(() => {
        const unsub = journalStore.subscribe(() => {
            // Force re-render on log update
            // In a real app we'd use useExternalStore or similar
            // Here we just accept the subscription trigger
            setLastJournalEvent(journalStore.getLastEvent());
        });
        return () => { unsub(); };
    }, []);

    // Local State
    const [showFlatten, setShowFlatten] = useState(false);
    const [showWhy, setShowWhy] = useState(false);
    const [showStart, setShowStart] = useState(false);
    const [whyContext, setWhyContext] = useState<{ id: string, text: string }>({ id: '', text: '' });
    const [busy, setBusy] = useState(false);

    // Run State Polling for START button orchestration - MIGRATED
    const { data: runStateData, error: runStateError, refresh: runStateRefresh } = usePoller<OpsRunState>({
        key: 'exec_strip_run_state',
        endpoint: '/api/ops/run_state',
        fetcher: () => getOpsRunState(new AbortController().signal, client),
        interval_ms: 2000,
        critical: false
    });
    const runState = { data: runStateData, error: runStateError, loading: false, refresh: runStateRefresh };

    // Derived Logic
    const isArbOn = effectiveOps?.arb_on || false;
    const isOffline = effectiveHealth?.status !== 'ok';
    // VARIANT A: Use system_mode for governance, derive from auto_mode if missing
    const mode = effectiveOps?.system_mode || (effectiveOps?.global_stop ? 'STOP' : (effectiveOps?.auto_mode ? 'AUTO' : 'MANUAL'));
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
            addToast({ type: 'ERROR', message: "Failed to toggle Arbitrage" });
        }
    };

    const handleFlatten = () => setShowFlatten(true);

    const handleModeClick = (target: 'MANUAL' | 'SEMI' | 'AUTO') => {
        // Pre-conditions for AUTO
        if (target === 'AUTO') {
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
        }

        // ALL mode changes go through Airlock
        openAirlock({
            actionType: 'SET_SYSTEM_MODE',
            severity: target === 'AUTO' ? 'CRITICAL' : 'HIGH',
            state_before: {
                mode: mode,
                auto_mode: mode === 'AUTO',
                trading_on: effectiveOps?.trading_on,
                global_stop: isStop
            },
            state_after: {
                mode: target,
                auto_mode: target === 'AUTO',
                trading_on: true,
                global_stop: false
            },
            dependencies: ['RiskEngine', 'ExecutionGateway', 'AuditLog', 'BalanceSync'],
            entry_exit_plan: {
                entry_conditions: ['All preflight checks PASS', 'Operator authenticated', 'No hard drift'],
                exit_triggers: ['Hard drift detected', 'Risk engine veto', 'Emergency stop'],
                reversion_method: 'Auto-downgrade to MANUAL + position freeze'
            },
            executor: async () => {
                const startTime = Date.now();
                try {
                    if (useSimData) {
                        await new Promise(r => setTimeout(r, 600));
                        setSimExecMode(target);
                        journalStore.addLog('MODE_CHANGE', `Mode changed to ${target}`, 'HUMAN');
                        return { status: 200, latency_ms: Date.now() - startTime, request_id: 'sim-' + Date.now() };
                    } else {
                        await setSystemMode(target, new AbortController().signal, client);
                        ops.refresh();
                        journalStore.addLog('MODE_CHANGE', `Mode changed to ${target} (Real)`, 'HUMAN');
                        return { status: 200, latency_ms: Date.now() - startTime, request_id: 'real-' + Date.now() };
                    }
                } catch (error: any) {
                    addToast({ type: 'ERROR', message: `Mode change failed: ${error.message || error}` });
                    throw error;
                }
            }
        });
    };


    const handleStop = () => {
        // STOP goes through Airlock but with FAST PATH (risk-reducing action)
        openAirlock({
            actionType: 'GLOBAL_EMERGENCY_STOP',
            severity: 'CRITICAL',
            fastPath: true, // 0.5-1.0s hold instead of 3.0s
            state_before: {
                mode: mode,
                trading_on: effectiveOps?.trading_on,
                global_stop: isStop
            },
            state_after: {
                mode: 'STOP',
                trading_on: false,
                global_stop: true
            },
            dependencies: ['AllTradingEngines', 'StrategyExecution', 'OrderRouter'],
            entry_exit_plan: {
                entry_conditions: ['Operator authority confirmed'],
                exit_triggers: ['Manual restart only'],
                reversion_method: 'Requires explicit mode change to re-enable trading'
            },
            executor: async () => {
                const startTime = Date.now();
                try {
                    if (useSimData) {
                        setSimExecMode('STOP');
                        setSimGlobalStop(true);
                        journalStore.addLog('STOP', 'Operator triggered Emergency Stop', 'HUMAN', 'CRITICAL');
                        return { status: 200, latency_ms: Date.now() - startTime, request_id: 'sim-stop-' + Date.now() };
                    } else {
                        await setSystemMode('STOP', new AbortController().signal, client);
                        ops.refresh();
                        journalStore.addLog('STOP', 'Operator triggered Emergency Stop (Real)', 'HUMAN', 'CRITICAL');
                        return { status: 200, latency_ms: Date.now() - startTime, request_id: 'real-stop-' + Date.now() };
                    }
                } catch (error: any) {
                    addToast({ type: 'ERROR', message: `Emergency stop failed: ${error.message || error}` });
                    throw error;
                }
            }
        });
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
            addToast({ type: 'ERROR', message: "Mode change failed: " + e });
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

                {/* 3. RIGHT: START, STOP, WHY & SIGNAL */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                    {/* Run State Badge */}
                    {runState.data?.running && (
                        <div className="badge success" style={{ marginBottom: '4px', animation: 'pulse 1.5s infinite' }}>
                            {runState.data.phase === 'assembling_portfolio' && '🔧 ASSEMBLING'}
                            {runState.data.phase === 'arming' && '🔒 ARMING'}
                            {runState.data.phase === 'trading' && `⚡ TRADING (${runState.data.run_mode?.toUpperCase() || 'DRY'})`}
                        </div>
                    )}
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        {/* START Button */}
                        {!runState.data?.running && !isStop && (
                            <button
                                className="button tiny primary"
                                onClick={() => setShowStart(true)}
                                disabled={busy}
                            >
                                ▶ START
                            </button>
                        )}
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
            {/* Legacy AirlockModal removed - all mutations now go through AirlockModalV3 via openAirlock() */}
            <StartConfirmationModal
                isOpen={showStart}
                onCancel={() => setShowStart(false)}
                onConfirm={async (mode) => {
                    setBusy(true);
                    try {
                        const result = await opsStart(mode, new AbortController().signal, client);
                        if (result.status === 'success') {
                            journalStore.addLog('START', `Orchestration started (${mode.toUpperCase()})`, 'HUMAN');
                            addToast({ type: 'SUCCESS', message: `Trading pipeline started in ${mode.toUpperCase()} mode` });
                        } else {
                            addToast({ type: 'ERROR', message: result.reason || 'START blocked' });
                        }
                    } catch (e) {
                        addToast({ type: 'ERROR', message: 'Failed to start: ' + e });
                    } finally {
                        setBusy(false);
                        setShowStart(false);
                        runState.refresh();
                    }
                }}
                ops={effectiveOps || null}
                loading={busy}
            />
            {showFlatten && <FlattenPortfolioModal onClose={() => setShowFlatten(false)} />}
        </>
    );
}
