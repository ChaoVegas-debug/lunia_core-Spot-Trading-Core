import React, { useState, useEffect, useCallback } from 'react';
import { useForensicSession, useClientIntent, useAnomalyDetection, ClientIntentMetadata } from '../../hooks/useForensicSession';
import { useEvidenceRecorder } from '../../hooks/useEvidenceRecorder';
import { AirlockContext } from '../../lib/airlock/airlockHelper';
import { ForensicHeader } from '../forensics/ForensicHeader';
import { ImpactTabs } from '../forensics/ImpactTabs';
import { PreflightLivestream, PreflightCheck } from '../forensics/PreflightLivestream';
import { ConfirmationZone } from '../forensics/ConfirmationZone';
import { ExecutionTrace } from '../forensics/ExecutionTrace';
import { EvidenceExport } from '../forensics/EvidenceExport';

interface AirlockModalV3Props {
    isOpen: boolean;
    context?: AirlockContext;
    onClose: () => void;
}

/**
 * GOVERNANCE AIRLOCK v3.1 — FORENSIC-GRADE CONFIRMATION SYSTEM
 * 
 * Composes Zones 0-5 with complete forensic protocol:
 * - Zone 0: ForensicHeader (session/intent IDs, TTL, anomalies)
 * - Zone 1: ImpactTabs (5-tab evidence display)
 * - Zone 2: PreflightLivestream (5 system checks)
 * - Zone 3: ConfirmationZone (reason + hold-to-confirm)
 * - Zone 4: ExecutionTrace (post-execution timeline)
 * - Zone 5: EvidenceExport (bundle seal + verify)
 */
export const AirlockModalV3: React.FC<AirlockModalV3Props> = ({ isOpen, context, onClose }) => {
    const session = useForensicSession();
    const { generateIntent } = useClientIntent(
        context?.actionType || 'UNKNOWN',
        context?.severity || 'MEDIUM',
        300000 // 5 minutes TTL
    );
    const { recordEvent, events } = useEvidenceRecorder(session?.forensic_session_id);

    // Local state
    const [intent, setIntent] = useState<ClientIntentMetadata | null>(null);
    const anomalies = useAnomalyDetection(intent || undefined);
    const [preflightsPassed, setPreflightsPassed] = useState(false);
    const [preflightChecks, setPreflightChecks] = useState<PreflightCheck[]>([]);
    const [executionStatus, setExecutionStatus] = useState<'PENDING' | 'EXECUTING' | 'SUCCESS' | 'FAILED'>('PENDING');
    const [isBusy, setIsBusy] = useState(false);
    const [finalStatus, setFinalStatus] = useState<'SUCCESS' | 'PARTIAL' | 'FAILED'>('SUCCESS');
    const [userReason, setUserReason] = useState('');

    // Initialize intent when modal opens
    useEffect(() => {
        if (isOpen && !intent && context) {
            const newIntent = generateIntent();
            if (newIntent) {
                setIntent(newIntent);
                // Record evidence events
                recordEvent('SESSION_PRESENT', {
                    client_intent_id: newIntent.client_intent_id,
                    notes: `Session: ${session?.forensic_session_id.slice(0, 18)}`
                });
                recordEvent('INTENT_CREATED', {
                    client_intent_id: newIntent.client_intent_id,
                    notes: `Action: ${context.actionType}, Severity: ${context.severity}`
                });
                recordEvent('UI_OPENED', {
                    client_intent_id: newIntent.client_intent_id,
                    notes: 'Airlock v3.1 opened'
                });
            }
        }

        // Reset state when modal closes
        if (!isOpen) {
            setIntent(null);
            setPreflightsPassed(false);
            setPreflightChecks([]);
            setExecutionStatus('PENDING');
            setIsBusy(false);
            setUserReason('');
        }
    }, [isOpen, context, intent, generateIntent, recordEvent, session]);

    // Handle preflight completion
    const handlePreflightComplete = useCallback((checks: PreflightCheck[]) => {
        setPreflightChecks(checks);
        const allPass = checks.every(c => c.status === 'PASS');
        const anyFail = checks.some(c => c.status === 'FAIL');
        const anyDegraded = checks.some(c => c.status === 'DEGRADED');

        // FAIL-CLOSED ENFORCEMENT
        if (anyFail && context?.severity === 'CRITICAL') {
            setPreflightsPassed(false);
        } else if (anyFail || anyDegraded) {
            // Allows override for MEDIUM/HIGH
            setPreflightsPassed(false); // User must check override box
        } else {
            setPreflightsPassed(allPass);
        }
    }, [context?.severity]);

    // Handle confirmation & execution
    const handleConfirm = useCallback(async (reason: string) => {
        if (!context || !intent) return;

        setUserReason(reason);
        setIsBusy(true);
        setExecutionStatus('EXECUTING');

        try {
            // Record user confirmation
            await recordEvent('USER_REASON_SET', {
                client_intent_id: intent.client_intent_id,
                notes: `Reason: ${reason}`
            });
            await recordEvent('USER_CONFIRM_HELD', {
                client_intent_id: intent.client_intent_id,
                notes: `Held for ${context.severity} (${context.fastPath ? 'FAST PATH' : 'NORMAL'})`
            });
            await recordEvent('USER_CONFIRM_ACCEPTED', {
                client_intent_id: intent.client_intent_id
            });

            // Execute
            await recordEvent('EXECUTE_REQUEST', {
                client_intent_id: intent.client_intent_id,
                endpoint: context.actionType,
                method: 'POST',
                notes: context.fastPath ? 'FAST PATH — risk-reducing action' : undefined
            });

            const startTime = Date.now();
            const result = await context.executor();
            const latency = Date.now() - startTime;

            await recordEvent('EXECUTE_RESPONSE', {
                client_intent_id: intent.client_intent_id,
                status: result.status || 200,
                latency_ms: result.latency_ms || latency,
                request_id: result.request_id,
                notes: `Success: ${result.status === 200 || result.status === 204}`
            });

            setExecutionStatus('SUCCESS');
            setFinalStatus('SUCCESS');

        } catch (error: any) {
            console.error('[Airlock] Execution failed:', error);

            await recordEvent('EXECUTE_RESPONSE', {
                client_intent_id: intent?.client_intent_id,
                status: error.status || 500,
                notes: `Error: ${error.message || 'Unknown'}`
            });

            setExecutionStatus('FAILED');
            setFinalStatus('FAILED');
        } finally {
            setIsBusy(false);
        }
    }, [context, intent, recordEvent]);

    // Handle cancel
    const handleCancel = useCallback(() => {
        if (intent) {
            recordEvent('USER_CANCELLED', {
                client_intent_id: intent.client_intent_id,
                notes: 'User cancelled action, no execution occurred'
            });
        }
        onClose();
    }, [intent, recordEvent, onClose]);

    if (!isOpen || !context || !session || !intent) {
        return null;
    }

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0, 0, 0, 0.85)',
                backdropFilter: 'blur(4px)',
                zIndex: 1000,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '2rem'
            }}
            onClick={(e) => {
                if (e.target === e.currentTarget) handleCancel();
            }}
        >
            <div
                style={{
                    background: 'var(--surface)',
                    borderRadius: '12px',
                    border: `2px solid ${context.severity === 'CRITICAL' ? 'var(--accent-danger)' :
                        context.severity === 'HIGH' ? 'var(--accent-warning)' :
                            'var(--accent-info)'}`,
                    maxWidth: '900px',
                    width: '100%',
                    maxHeight: '90vh',
                    overflow: 'auto',
                    padding: '2rem',
                    boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)'
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <h2 style={{ margin: 0, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                <span>🔒</span>
                                <span>GOVERNANCE AIRLOCK v3.1</span>
                            </h2>
                            <p className="small muted" style={{ margin: 0 }}>
                                Forensic-grade confirmation system — All actions recorded
                            </p>
                        </div>
                        <button
                            className="button ghost"
                            onClick={handleCancel}
                            disabled={isBusy}
                            style={{ fontSize: '1.5rem', padding: '0.25rem 0.75rem' }}
                        >
                            ×
                        </button>
                    </div>
                </div>

                {/* ZONE 0: Forensic Header */}
                <ForensicHeader
                    session={session}
                    intent={intent}
                    anomalies={anomalies}
                />

                {/* ZONE 1: Impact Tabs */}
                {executionStatus === 'PENDING' && (
                    <div style={{ marginBottom: '1.5rem' }}>
                        <ImpactTabs
                            actionType={context.actionType}
                            stateBefore={context.state_before}
                            stateAfter={context.state_after}
                        />
                    </div>
                )}

                {/* ZONE 2: Preflight Livestream */}
                {executionStatus === 'PENDING' && (
                    <div style={{ marginBottom: '1.5rem' }}>
                        <PreflightLivestream
                            intent={intent}
                            onCheckComplete={handlePreflightComplete}
                        />
                    </div>
                )}

                {/* ZONE 3: Confirmation Zone */}
                {executionStatus === 'PENDING' && (
                    <div style={{ marginBottom: '1.5rem' }}>
                        <ConfirmationZone
                            intent={intent}
                            preflightsPassed={preflightsPassed}
                            onConfirm={handleConfirm}
                            onCancel={handleCancel}
                            isBusy={isBusy}
                        />
                    </div>
                )}

                {/* ZONE 4: Execution Trace */}
                {executionStatus !== 'PENDING' && (
                    <div style={{ marginBottom: '1.5rem' }}>
                        <ExecutionTrace
                            intentId={intent.client_intent_id}
                            events={events}
                            finalStatus={finalStatus}
                        />
                    </div>
                )}

                {/* ZONE 5: Evidence Export */}
                {executionStatus !== 'PENDING' && (
                    <div style={{ marginBottom: '1.5rem' }}>
                        <EvidenceExport
                            session_id={session.forensic_session_id}
                            intent={intent}
                            events={events}
                            userReason={userReason}
                            finalStatus={finalStatus}
                        />
                    </div>
                )}

                {/* Footer Status */}
                <div style={{
                    marginTop: '1.5rem',
                    paddingTop: '1rem',
                    borderTop: '1px solid var(--border-color)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                }}>
                    <div className="small muted">
                        {executionStatus === 'PENDING' && 'Awaiting operator confirmation'}
                        {executionStatus === 'EXECUTING' && 'Executing action...'}
                        {executionStatus === 'SUCCESS' && '✅ Action completed successfully'}
                        {executionStatus === 'FAILED' && '❌ Action failed'}
                    </div>
                    {executionStatus !== 'PENDING' && (
                        <button className="button ghost" onClick={onClose}>
                            Close Airlock
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};
