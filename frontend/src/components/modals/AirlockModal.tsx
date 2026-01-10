import React, { useState, useEffect, useCallback } from 'react';
import { getHealth, getStatus } from '../../api/adapter';

interface AirlockModalProps {
    onConfirm: () => Promise<void>;
    onCancel: () => void;
    isOpen: boolean;
}

export const AirlockModal: React.FC<AirlockModalProps> = ({ onConfirm, onCancel, isOpen }) => {
    const [step, setStep] = useState(1);

    const [diagnostics, setDiagnostics] = useState({
        heartbeat: { status: 'PENDING', value: '', ok: false },
        riskEngine: { status: 'PENDING', value: '', ok: false },
        latency: { status: 'PENDING', value: '', ok: false }
    });

    const [acks, setAcks] = useState({
        autoExec: false,
        riskConfig: false
    });
    const [countdown, setCountdown] = useState(10);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Reset on Open
    useEffect(() => {
        if (isOpen) {
            setStep(1);
            setChecksPending();
            setAcks({ autoExec: false, riskConfig: false });
            setCountdown(10);
            setError(null);
            setBusy(false);
        }
    }, [isOpen]);

    const setChecksPending = () => {
        setDiagnostics({
            heartbeat: { status: 'PENDING', value: 'Checking...', ok: false },
            riskEngine: { status: 'PENDING', value: 'Querying...', ok: false },
            latency: { status: 'PENDING', value: 'Pinging...', ok: false }
        });
    };

    const runDiagnostics = useCallback(async () => {
        setStep(2);
        setChecksPending();

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000); // 8s timeout

        try {
            // 1. Latency & Link Check
            const start = performance.now();
            const health = await getHealth(controller.signal);
            const rtt = Math.round(performance.now() - start);

            setDiagnostics(prev => ({
                ...prev,
                latency: { status: 'DONE', value: `${rtt}ms`, ok: rtt < 1000 },
                heartbeat: {
                    status: 'DONE',
                    value: health.status === 'ok' ? 'ONLINE' : health.status,
                    ok: health.status === 'ok'
                }
            }));

            // 2. System Status (Risk Engine Proxy)
            const status = await getStatus(controller.signal);
            const riskOk = status.uptime > 0; // Simple liveness check based on uptime presence

            setDiagnostics(prev => ({
                ...prev,
                riskEngine: {
                    status: 'DONE',
                    value: riskOk ? 'ACTIVE' : 'OFFLINE',
                    ok: riskOk
                }
            }));

            clearTimeout(timeoutId);

            // Auto Advance if all OK
            if (health.status === 'ok' && riskOk) {
                setTimeout(() => setStep(3), 1000);
            }

        } catch (e: any) {
            setDiagnostics({
                heartbeat: { status: 'FAIL', value: 'ERR', ok: false },
                riskEngine: { status: 'FAIL', value: 'UNREACHABLE', ok: false },
                latency: { status: 'FAIL', value: 'TIMEOUT', ok: false }
            });
            setError("Diagnostics Failed: System Unreachable");
        }
    }, []);

    // Countdown Logic
    useEffect(() => {
        let timer: any;
        if (step === 5 && countdown > 0) {
            timer = setTimeout(() => setCountdown(c => c - 1), 1000);
        }
        return () => clearTimeout(timer);
    }, [step, countdown]);

    const handleConfirm = async () => {
        setBusy(true);
        setError(null);
        try {
            await onConfirm();
        } catch (e: any) {
            console.error(e);
            setError(`Activation Refused: ${e.message || 'Backened rejected request'}`);
            setBusy(false);
        }
    };

    const allSystemsGo = diagnostics.heartbeat.ok && diagnostics.riskEngine.ok;

    if (!isOpen) return null;

    return (
        <div style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.85)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: 'blur(4px)'
        }}>
            <div className="card" style={{
                maxWidth: '500px',
                width: '100%',
                border: error ? '2px solid var(--accent-danger)' : (step === 5 ? '2px solid var(--accent-primary)' : '1px solid var(--border-color)'),
                boxShadow: step === 5 ? '0 0 30px rgba(59, 130, 246, 0.3)' : 'none',
                transition: 'all 0.3s ease'
            }}>
                <div className="card-header flex-between">
                    <h3 style={{ textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                        {step === 5 ? 'Final Authorization' : `Protocol Sequence ${step}/5`}
                    </h3>
                    <button className="button ghost small" onClick={onCancel}>
                        {step === 5 ? 'ABORT' : 'CANCEL'}
                    </button>
                </div>

                <div style={{ padding: '2rem', textAlign: 'center' }}>

                    {/* STEP 1: INTENT */}
                    {step === 1 && (
                        <>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🤖</div>
                            <h2>Engage Autonomous Mode?</h2>
                            <p className="muted" style={{ marginBottom: '2rem' }}>
                                You are about to hand over full execution authority to the LUNIA Engine.
                                All trades will be executed automatically based on your strategy and governance limits.
                            </p>
                            <button className="button primary full-width" onClick={runDiagnostics}>
                                INITIATE DIAGNOSTICS
                            </button>
                            <div className="mt-4">
                                <a
                                    href="#"
                                    className="tiny text-muted underline"
                                    onClick={(e) => {
                                        e.preventDefault();
                                        alert("Airlock Protocol: A mandatory 5-step verification process to ensure system integrity, risk engine availability, and operator presence before releasing autonomous agents.");
                                    }}
                                >
                                    Why is this required?
                                </a>
                            </div>
                        </>
                    )}

                    {/* STEP 2: DIAGNOSTICS */}
                    {step === 2 && (
                        <div style={{ textAlign: 'left' }}>
                            <h4 style={{ marginBottom: '1rem' }}>System Integrity Check</h4>

                            {/* Heartbeat */}
                            <div className="flex-between" style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>
                                <span>API Heartbeat</span>
                                <span className={diagnostics.heartbeat.ok ? 'text-green' : (diagnostics.heartbeat.status === 'FAIL' ? 'text-red' : 'muted')}>
                                    {diagnostics.heartbeat.value}
                                </span>
                            </div>

                            {/* Risk Engine */}
                            <div className="flex-between" style={{ padding: '0.5rem', borderBottom: '1px solid var(--border-color)' }}>
                                <span>Risk Engine Status</span>
                                <span className={diagnostics.riskEngine.ok ? 'text-green' : (diagnostics.riskEngine.status === 'FAIL' ? 'text-red' : 'muted')}>
                                    {diagnostics.riskEngine.value}
                                </span>
                            </div>

                            {/* Latency */}
                            <div className="flex-between" style={{ padding: '0.5rem' }}>
                                <span>Network Latency</span>
                                <span className={diagnostics.latency.ok ? 'text-green' : (diagnostics.latency.status === 'FAIL' ? 'text-red' : 'muted')}>
                                    {diagnostics.latency.value}
                                </span>
                            </div>

                            {error && (
                                <div className="alert error" style={{ marginTop: '1rem' }}>
                                    {error}
                                </div>
                            )}

                            {!allSystemsGo && (diagnostics.heartbeat.status === 'DONE' || diagnostics.heartbeat.status === 'FAIL') && (
                                <div style={{ marginTop: '1rem' }}>
                                    <button className="button small" onClick={runDiagnostics}>RETRY</button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* STEP 3: ADVISORY */}
                    {step === 3 && (
                        <>
                            <div className="alert info" style={{ textAlign: 'left', marginBottom: '2rem' }}>
                                <strong>READY TO ARM</strong><br />
                                System integrity verified. Expecting high frequency execution. Ensure capital buffers are sufficient.
                            </div>
                            <button className="button primary full-width" onClick={() => setStep(4)}>
                                PROCEED TO ACKNOWLEDGEMENTS
                            </button>
                        </>
                    )}

                    {/* STEP 4: ACKNOWLEDGEMENTS */}
                    {step === 4 && (
                        <div style={{ textAlign: 'left' }}>
                            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                                <input
                                    type="checkbox"
                                    checked={acks.autoExec}
                                    onChange={e => setAcks({ ...acks, autoExec: e.target.checked })}
                                    id="ack1"
                                />
                                <label htmlFor="ack1" className="small" style={{ cursor: 'pointer' }}>
                                    I acknowledge that the system will execute trades without further confirmation.
                                </label>
                            </div>
                            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
                                <input
                                    type="checkbox"
                                    checked={acks.riskConfig}
                                    onChange={e => setAcks({ ...acks, riskConfig: e.target.checked })}
                                    id="ack2"
                                />
                                <label htmlFor="ack2" className="small" style={{ cursor: 'pointer' }}>
                                    I confirm that my Risk Profile and Capital Caps are correctly configured.
                                </label>
                            </div>
                            <button
                                className="button primary full-width"
                                disabled={!acks.autoExec || !acks.riskConfig}
                                onClick={() => setStep(5)}
                            >
                                ARM SYSTEM
                            </button>
                        </div>
                    )}

                    {/* STEP 5: COUNTDOWN */}
                    {step === 5 && (
                        <>
                            <div style={{ fontSize: '4rem', fontWeight: 700, fontFamily: 'monospace', color: 'var(--accent-primary)' }}>
                                00:{countdown.toString().padStart(2, '0')}
                            </div>
                            <p className="small muted" style={{ marginBottom: '2rem' }}>
                                AUTO MODE ENGAGING IN...
                            </p>

                            {error && (
                                <div className="alert error" style={{ marginBottom: '1rem' }}>
                                    {error}
                                </div>
                            )}

                            <div className="grid cols-2" style={{ gap: '1rem' }}>
                                <button className="button danger" onClick={onCancel} disabled={busy}>
                                    CANCEL
                                </button>
                                <button
                                    className="button primary"
                                    disabled={countdown > 0 || busy}
                                    onClick={handleConfirm}
                                    style={{ opacity: countdown > 0 ? 0.5 : 1 }}
                                >
                                    {busy ? 'ENGAGING...' : 'CONFIRM ENGAGE'}
                                </button>
                            </div>
                        </>
                    )}

                </div>
            </div>
        </div>
    );
};
