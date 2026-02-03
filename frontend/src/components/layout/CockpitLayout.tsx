/**
 * COCKPIT LAYOUT - INSTITUTIONAL TERMINAL
 * 
 * F2 Full Assembly: 12+ widgets at Bloomberg/TWS density
 * 
 * Architecture:
  * - Fixed header: Identity + Status chips + STOP ALL
 * - 3-column grid (LEFT 20% | CENTER 50% | RIGHT 30%)
 * - Bottom drawer: TraceDrawer (collapsible)
 * 
 * Header Chips:
 * - UI LIVE/STALLED (Dead Man's Switch heartbeat)
 * - GLOBAL DATA AGE (max age across critical pollers)
 * - MODE (MANUAL/AUTO/STOP)
 * - DEFCON (placeholder)
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useForensicSession } from '../../hooks/useForensicSession';
import { openAirlock } from '../../lib/airlock/airlockHelper';
import { useLocalStorageState } from '../../hooks/useLocalStorageState';
import { useGlobalPulse } from '../../hooks/useGlobalPulse';
import { useGlobalDataAge } from '../../hooks/useGlobalDataAge';
import { emitSystemEvent } from '../../lib/runtime/eventBus';

// LEFT Column - Control
import { SystemStateWidgetF1 } from '../widgets/SystemStateWidgetF1';
import { StrategiesBoardWidget } from '../widgets/StrategiesBoardWidget';
import { AllocationControlsWidget } from '../widgets/AllocationControlsWidget';
import { KillSwitchReadinessWidget } from '../widgets/KillSwitchReadinessWidget';

// CENTER Column - Capital & Execution
import { BalancesWidget } from '../widgets/BalancesWidget';
import { PositionsWidget } from '../widgets/PositionsWidget';
import { OrdersWidget } from '../widgets/OrdersWidget';
import { PnLWidget } from '../widgets/PnLWidget';

// RIGHT Column - Risk & Intel
import { SignalsWidget } from '../widgets/SignalsWidget';
import { RiskLimitsWidget } from '../widgets/RiskLimitsWidget';
import { DriftMonitorWidget } from '../widgets/DriftMonitorWidget';
import { IncidentsWidget } from '../widgets/IncidentsWidget';

// Bottom Drawer
import { TraceDrawer } from '../widgets/TraceDrawer';

// Ops state for mode display
import { usePoller } from '../../hooks/usePoller';
import { getOpsState, setSystemMode } from '../../api/adapter';
import type { OpsState } from '../../api/types';

export const CockpitLayout: React.FC = () => {
    const auth = useAuth();
    const session = useForensicSession();
    const client = { role: auth.role, opsToken: auth.opsToken };
    const { data: opsData, error: opsError, refresh: opsRefresh } = usePoller<OpsState>({
        key: 'ops_CockpitLayout',
        endpoint: '/api/ops/state',
        fetcher: () => getOpsState(new AbortController().signal, client),
        interval_ms: 2000,
        critical: true
    });
    const ops = { data: opsData, error: opsError, loading: false, refresh: opsRefresh };

    const [traceOpen, setTraceOpen] = useLocalStorageState('cockpit:trace_open', false);

    // Phase F3: Global Pulse
    const { activityTicker, networkQuality } = useGlobalPulse();
    const globalDataAge = useGlobalDataAge();

    // Dead Man's Switch - UI Heartbeat
    const [heartbeat, setHeartbeat] = useState(false);
    const [lastBeat, setLastBeat] = useState(Date.now());

    useEffect(() => {
        const interval = setInterval(() => {
            setHeartbeat(prev => !prev);
            setLastBeat(Date.now());
        }, 500);

        return () => clearInterval(interval);
    }, []);

    // Detect UI stall (heartbeat stopped)
    const [uiStalled, setUiStalled] = useState(false);
    const [lastStallState, setLastStallState] = useState(false);

    useEffect(() => {
        const checkInterval = setInterval(() => {
            const timeSinceLastBeat = Date.now() - lastBeat;
            const nowStalled = timeSinceLastBeat > 1500;

            if (nowStalled && !lastStallState) {
                // Transition to stalled: emit event ONCE
                setUiStalled(true);
                setLastStallState(true);
                emitSystemEvent('UI_STALLED', 'CRITICAL', { time_since_beat_ms: timeSinceLastBeat });
                console.warn('UI heartbeat stalled - thread may be frozen');
            } else if (!nowStalled && lastStallState) {
                // Recovered
                setUiStalled(false);
                setLastStallState(false);
            }
        }, 1000);

        return () => clearInterval(checkInterval);
    }, [lastBeat, lastStallState]);

    const mode = ops.data?.exec_mode || 'MANUAL';
    const sessionHash = session?.forensic_session_id?.slice(0, 8) || 'unknown';

    const handleStopAll = () => {
        openAirlock({
            actionType: 'GLOBAL_EMERGENCY_STOP_ALL',
            severity: 'CRITICAL',
            fastPath: true,
            state_before: {
                mode,
                active_strategies: 'ALL',
            },
            state_after: {
                mode: 'STOP',
                active_strategies: 'NONE',
            },
            dependencies: ['AllStrategies', 'AllOrders', 'AllPositions'],
            entry_exit_plan: {
                entry_conditions: ['EMERGENCY STOP triggered by operator'],
                exit_triggers: ['All strategies HALTED', 'All positions closed', 'All orders cancelled'],
                reversion_method: 'Manual recovery: setSystemMode(MANUAL) after verification',
            },
            executor: async () => {
                console.log('[EXECUTOR] STOP ALL - calling setSystemMode(STOP)');
                const controller = new AbortController();
                try {
                    const response = await setSystemMode('STOP', controller.signal, client);
                    console.log('[EXECUTOR] STOP ALL complete:', response);
                    // Wrap response to match Airlock contract
                    return {
                        status: 200,
                        request_id: undefined,
                        latency_ms: 0,
                    };
                } catch (error) {
                    console.error('[EXECUTOR] STOP ALL failed:', error);
                    throw error;
                }
            },
        });
    };

    return (
        <div style={{
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            overflow: 'hidden',
        }}>
            {/* FIXED HEADER */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto auto auto auto auto',
                gap: '12px',
                alignItems: 'center',
                padding: '8px 16px',
                background: 'var(--bg-panel)',
                borderBottom: '2px solid var(--border-color)',
                flexShrink: 0,
            }}>
                {/* Left: Identity */}
                <div style={{ fontSize: '11px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '2px' }}>
                        ALADDIN TERMINAL
                    </div>
                    <div style={{ fontSize: '9px', color: '#888', fontFamily: 'monospace' }}>
                        SESSION {sessionHash} | USER {auth.role.toUpperCase()}
                    </div>
                </div>

                {/* UI LIVE / UI STALLED */}
                <div style={{
                    background: uiStalled ? '#dc2626' : '#10b981',
                    color: '#fff',
                    padding: '6px 12px',
                    borderRadius: '3px',
                    fontSize: '10px',
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                }}>
                    {!uiStalled && (
                        <span style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            background: heartbeat ? '#fff' : 'rgba(255,255,255,0.3)',
                            transition: 'background 0.3s',
                        }} />
                    )}
                    {uiStalled ? 'UI STALLED' : 'UI LIVE'}
                </div>

                {/* MODE */}
                <div style={{
                    background: mode === 'STOP' ? '#dc2626' : mode === 'AUTO' ? '#f59e0b' : '#666',
                    color: mode === 'AUTO' ? '#000' : '#fff',
                    padding: '6px 12px',
                    borderRadius: '3px',
                    fontSize: '10px',
                    fontWeight: 'bold',
                }}>
                    MODE: {mode}
                </div>

                {/* Network Quality (Phase F3) */}
                <div style={{
                    background: '#1a1a1a',
                    border: `1px solid ${networkQuality.color}`,
                    color: networkQuality.color,
                    padding: '6px 12px',
                    borderRadius: '3px',
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    fontWeight: 'bold',
                }}>
                    NET p95={networkQuality.p95_ms}ms
                </div>

                {/* Global Data Age (Phase F3.1) */}
                <div
                    style={{
                        background: '#1a1a1a',
                        border: `1px solid ${globalDataAge.status === 'FRESH' ? '#10b981' :
                            globalDataAge.status === 'STALE' ? '#f59e0b' : '#dc2626'
                            }`,
                        color: globalDataAge.status === 'FRESH' ? '#10b981' :
                            globalDataAge.status === 'STALE' ? '#f59e0b' : '#dc2626',
                        padding: '6px 12px',
                        borderRadius: '3px',
                        fontSize: '10px',
                        fontFamily: 'monospace',
                        fontWeight: 'bold',
                        cursor: 'help',
                    }}
                    title={`WORST: ${globalDataAge.worst_endpoint}\nAGE: ${globalDataAge.age_s}s (${globalDataAge.status})\nREASON: ${globalDataAge.reason_label}\n${globalDataAge.reason_detail ? 'DETAIL: ' + globalDataAge.reason_detail : ''}\n${globalDataAge.last_success_ts ? 'LAST SUCCESS: ' + new Date(globalDataAge.last_success_ts).toLocaleTimeString() : ''}`}
                >
                    AGE: {globalDataAge.age_s}s
                </div>

                {/* STOP ALL */}
                <button
                    onClick={handleStopAll}
                    style={{
                        background: '#dc2626',
                        color: '#fff',
                        border: 'none',
                        padding: '8px 16px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        letterSpacing: '0.5px',
                    }}
                >
                    STOP ALL
                </button>
            </div>

            {/* ACTIVITY TICKER (Phase F3) */}
            {activityTicker.length > 0 && (
                <div style={{
                    padding: '4px 16px',
                    background: '#0a0a0a',
                    borderBottom: '1px solid var(--border-color)',
                    fontSize: '9px',
                    fontFamily: 'monospace',
                    color: '#888',
                    flexShrink: 0,
                    overflowX: 'auto',
                    whiteSpace: 'nowrap',
                }}>
                    {activityTicker.slice(0, 3).map((evt, idx) => (
                        <span key={evt.ts} style={{ marginRight: '24px', color: evt.color }}>
                            {evt.display}
                        </span>
                    ))}
                </div>
            )}

            {/* MAIN GRID (3 columns) */}
            <div style={{
                flex: 1,
                display: 'grid',
                gridTemplateColumns: '20% 50% 30%',
                gap: '8px',
                padding: '8px',
                overflow: 'hidden',
            }}>
                {/* LEFT COLUMN - Control */}
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    overflow: 'hidden',
                }}>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <SystemStateWidgetF1 />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <StrategiesBoardWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <AllocationControlsWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <KillSwitchReadinessWidget />
                    </div>
                </div>

                {/* CENTER COLUMN - Capital & Execution */}
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    overflow: 'hidden',
                }}>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <BalancesWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <PositionsWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <OrdersWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <PnLWidget />
                    </div>
                </div>

                {/* RIGHT COLUMN - Risk & Intel */}
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    overflow: 'hidden',
                }}>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <SignalsWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <RiskLimitsWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <DriftMonitorWidget />
                    </div>
                    <div style={{ flex: 1, minHeight: 0 }}>
                        <IncidentsWidget />
                    </div>
                </div>
            </div>

            {/* BOTTOM DRAWER - Trace */}
            <div style={{
                flexShrink: 0,
                borderTop: '2px solid var(--border-color)',
                background: 'var(--bg-panel)',
            }}>
                {/* Drawer Toggle */}
                <div
                    onClick={() => setTraceOpen(!traceOpen)}
                    style={{
                        padding: '6px 16px',
                        background: 'var(--bg-panel)',
                        borderBottom: traceOpen ? '1px solid var(--border-color)' : 'none',
                        cursor: 'pointer',
                        fontSize: '10px',
                        fontWeight: 'bold',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                    }}
                >
                    <span>FORENSIC TRACE</span>
                    <span>{traceOpen ? '▼' : '▲'}</span>
                </div>

                {/* Drawer Content */}
                {traceOpen && (
                    <div style={{ height: '200px' }}>
                        <TraceDrawer />
                    </div>
                )}
            </div>
        </div>
    );
};
