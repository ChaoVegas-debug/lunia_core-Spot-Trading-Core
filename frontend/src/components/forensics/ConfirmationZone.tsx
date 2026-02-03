import React, { useState, useEffect } from 'react';
import { ClientIntentMetadata } from '../../hooks/useForensicSession';

interface ConfirmationZoneProps {
    intent: ClientIntentMetadata;
    preflightsPassed: boolean;
    onConfirm: (reason: string) => void;
    onCancel: () => void;
    isBusy?: boolean;
}

/**
 * CONFIRMATION ZONE (ZONE 3)
 * 
 * Features:
 * - Mandatory reason input (min 30 chars for CRITICAL)
 * - Hold-to-confirm with severity-based timing
 * - Dual approval flow for FUND mode (mock for now)
 */
export const ConfirmationZone: React.FC<ConfirmationZoneProps> = ({
    intent,
    preflightsPassed,
    onConfirm,
    onCancel,
    isBusy = false
}) => {
    const [reason, setReason] = useState('');
    const [holdProgress, setHoldProgress] = useState(0);
    const [isHolding, setIsHolding] = useState(false);
    const [holdTimer, setHoldTimer] = useState<NodeJS.Timeout | null>(null);

    // Hold duration based on severity (in milliseconds)
    const getHoldDuration = (): number => {
        switch (intent.severity) {
            case 'CRITICAL': return 3000; // 3.0s
            case 'HIGH': return 2500;     // 2.5s
            case 'MEDIUM': return 1500;   // 1.5s
            default: return 1000;
        }
    };

    const holdDuration = getHoldDuration();
    const minReasonLength = intent.severity === 'CRITICAL' ? 30 : 15;

    // Hold-to-confirm logic
    const startHold = () => {
        if (!canConfirm()) return;

        setIsHolding(true);
        const startTime = Date.now();

        const timer = setInterval(() => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min((elapsed / holdDuration) * 100, 100);
            setHoldProgress(progress);

            if (progress >= 100) {
                clearInterval(timer);
                setIsHolding(false);
                onConfirm(reason);
            }
        }, 50);

        setHoldTimer(timer);
    };

    const stopHold = () => {
        if (holdTimer) {
            clearInterval(holdTimer);
            setHoldTimer(null);
        }
        setIsHolding(false);
        setHoldProgress(0);
    };

    useEffect(() => {
        return () => {
            if (holdTimer) clearInterval(holdTimer);
        };
    }, [holdTimer]);

    const canConfirm = (): boolean => {
        return preflightsPassed && reason.length >= minReasonLength && !isBusy;
    };

    return (
        <div>
            <h4 style={{ marginBottom: '1rem' }}>🔐 Authorization</h4>

            {/* Mandatory Reason Input */}
            <div style={{ marginBottom: '1.5rem' }}>
                <label htmlFor="operator-reason" className="small" style={{ display: 'block', marginBottom: '0.5rem' }}>
                    Operator Reason <span className="text-danger">*</span>
                    {intent.severity === 'CRITICAL' && <span className="muted"> (min {minReasonLength} chars)</span>}
                </label>
                <textarea
                    id="operator-reason"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder={intent.severity === 'CRITICAL'
                        ? "CRITICAL action requires detailed justification..."
                        : "Brief reason for this action..."}
                    rows={intent.severity === 'CRITICAL' ? 4 : 2}
                    style={{
                        width: '100%',
                        padding: '0.75rem',
                        borderRadius: '6px',
                        border: `1px solid ${reason.length >= minReasonLength ? 'var(--accent-success)' : 'var(--border-color)'}`,
                        background: 'var(--surface-secondary)',
                        fontFamily: 'inherit',
                        fontSize: '0.875rem',
                        resize: 'vertical'
                    }}
                />
                <div className="tiny muted" style={{ marginTop: '0.25rem' }}>
                    {reason.length}/{minReasonLength} characters {reason.length >= minReasonLength && '✅'}
                </div>
            </div>

            {/* Prerequisites Checklist */}
            <div style={{ marginBottom: '1.5rem' }}>
                <div className="small muted" style={{ marginBottom: '0.5rem' }}>Prerequisites:</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span>{preflightsPassed ? '✅' : '⏳'}</span>
                        <span className={preflightsPassed ? '' : 'muted'}>All preflight checks passed</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span>{reason.length >= minReasonLength ? '✅' : '⏳'}</span>
                        <span className={reason.length >= minReasonLength ? '' : 'muted'}>Justification provided</span>
                    </div>
                </div>
            </div>

            {/* Hold-to-Confirm Button */}
            <div style={{ display: 'flex', gap: '1rem' }}>
                <div style={{ flex: 1, position: 'relative' }}>
                    <button
                        className="button primary full-width"
                        disabled={!canConfirm() || isBusy}
                        onMouseDown={startHold}
                        onMouseUp={stopHold}
                        onMouseLeave={stopHold}
                        onTouchStart={startHold}
                        onTouchEnd={stopHold}
                        style={{
                            position: 'relative',
                            overflow: 'hidden',
                            height: '48px',
                            fontSize: '1rem',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            cursor: canConfirm() ? 'pointer' : 'not-allowed',
                            opacity: canConfirm() ? 1 : 0.5
                        }}
                    >
                        {/* Progress Background */}
                        <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            height: '100%',
                            width: `${holdProgress}%`,
                            background: 'rgba(255, 255, 255, 0.2)',
                            transition: isHolding ? 'none' : 'width 0.3s ease',
                            pointerEvents: 'none'
                        }} />

                        {/* Button Text */}
                        <span style={{ position: 'relative', zIndex: 1 }}>
                            {isBusy ? 'EXECUTING...' :
                                isHolding ? `HOLD (${((holdDuration - (holdProgress / 100 * holdDuration)) / 1000).toFixed(1)}s)` :
                                    `HOLD TO CONFIRM (${(holdDuration / 1000).toFixed(1)}s)`}
                        </span>
                    </button>
                </div>

                <button
                    className="button ghost"
                    onClick={onCancel}
                    disabled={isBusy}
                    style={{ minWidth: '100px' }}
                >
                    CANCEL
                </button>
            </div>

            {/* Dual Approval (Mock - for FUND mode) */}
            {intent.severity === 'CRITICAL' && (
                <div className="alert info small" style={{ marginTop: '1rem' }}>
                    <strong>📋 Dual Approval Policy:</strong> CRITICAL actions in FUND mode require secondary operator approval.
                    This is currently MOCKED for demo purposes.
                </div>
            )}
        </div>
    );
};
