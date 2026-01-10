import React, { useState } from 'react';
import { executePortfolioAction } from '../../api/adapter';

interface FlattenPortfolioModalProps {
    onClose: () => void;
    portfolioId?: string; // Optional, if global
}

export const FlattenPortfolioModal: React.FC<FlattenPortfolioModalProps> = ({ onClose, portfolioId }) => {
    const [confirmPhrase, setConfirmPhrase] = useState('');
    const [ackRisks, setAckRisks] = useState(false);
    const [ackReview, setAckReview] = useState(false);
    const [status, setStatus] = useState<'IDLE' | 'EXECUTING' | 'MANUAL_REQUIRED' | 'DONE'>('IDLE');
    const [error, setError] = useState<string | null>(null);

    const canExecute = confirmPhrase === 'FLATTEN' && ackRisks && ackReview && status === 'IDLE';

    const handleExecute = async () => {
        if (!canExecute) return;
        setStatus('EXECUTING');
        try {
            if (portfolioId) {
                // Try the specific portfolio action endpoint
                await executePortfolioAction(portfolioId, 'DERISK', new AbortController().signal);
                setStatus('DONE');
            } else {
                // Global flatten? No endpoint for global flatten yet.
                // Fallback to "Manual Required" as per strict P1.1 spec
                throw new Error("No automated global flatten endpoint available.");
            }
        } catch (err: any) {
            // If endpoint is missing (404) or fails, we enforce the "Honest Manual Fallback"
            console.error("Flatten failed or unavailable:", err);
            setStatus('MANUAL_REQUIRED');
            setError("Automated liquidation unavailable. Manual intervention required.");
        }
    };

    return (
        <div className="modal-overlay">
            <div className="modal-content danger-modal" style={{ maxWidth: '500px', borderTop: '4px solid var(--accent-danger)' }}>
                <div className="modal-header">
                    <h3 style={{ color: 'var(--accent-danger)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>☢️</span> NUCLEAR OPTION: FLATTEN PORTFOLIO
                    </h3>
                </div>

                <div className="modal-body">
                    {status === 'IDLE' && (
                        <>
                            <div className="alert danger mb-4">
                                <strong>WARNING: IRREVERSIBLE ACTION.</strong><br />
                                This will attempt to MARKET SELL all positions to USDT/Stablecoin.
                                Slippage may be significant. Capital verification required.
                            </div>

                            <div className="form-group mb-4">
                                <label className="checkbox-label" style={{ display: 'flex', gap: '8px', alignItems: 'start', cursor: 'pointer' }}>
                                    <input type="checkbox" checked={ackRisks} onChange={e => setAckRisks(e.target.checked)} />
                                    <span>I understand that this executes MARKET SELL orders and I accept the liquidation risk.</span>
                                </label>
                            </div>

                            <div className="form-group mb-4">
                                <label className="checkbox-label" style={{ display: 'flex', gap: '8px', alignItems: 'start', cursor: 'pointer' }}>
                                    <input type="checkbox" checked={ackReview} onChange={e => setAckReview(e.target.checked)} />
                                    <span>I confirm I have reviewed all open positions and this is a necessary emergency action.</span>
                                </label>
                            </div>

                            <div className="form-group">
                                <label>Type <strong>FLATTEN</strong> to confirm:</label>
                                <input
                                    type="text"
                                    className="input danger-input"
                                    style={{ textTransform: 'uppercase', borderColor: 'var(--accent-danger)' }}
                                    placeholder="FLATTEN"
                                    value={confirmPhrase}
                                    onChange={e => setConfirmPhrase(e.target.value)}
                                />
                            </div>
                        </>
                    )}

                    {status === 'EXECUTING' && (
                        <div className="loading-state text-center p-8">
                            <div className="spinner-danger mb-4"></div>
                            <div>Sending Kill Signals...</div>
                        </div>
                    )}

                    {status === 'DONE' && (
                        <div className="success-state text-center p-4">
                            <h4 className="text-success">Signal Sent</h4>
                            <p>The Risk Engine has accepted the De-Risk command.</p>
                            <button className="button full-width mt-4" onClick={onClose}>Close</button>
                        </div>
                    )}

                    {status === 'MANUAL_REQUIRED' && (
                        <div className="manual-fallback">
                            <div className="alert warn mb-4">
                                <strong>{error}</strong>
                            </div>
                            <p className="mb-2"><strong>Emergency Procedure:</strong></p>
                            <ol className="list-decimal pl-4 mb-4 small">
                                <li>Go to <strong>Exchange Controls</strong> and verify connection.</li>
                                <li>Navigate to the Exchange Terminal (External).</li>
                                <li>Manually cancel all open Limit Orders.</li>
                                <li>Execute Market Sells for each asset manually.</li>
                                <li>Return here to verify "Free Capital" reflects the sales.</li>
                            </ol>
                            <p className="tiny muted">Event ID: MAN_FLATTEN_REQ_{Date.now()}</p>
                        </div>
                    )}
                </div>

                <div className="modal-footer flex-row gap-2 justify-end">
                    {status !== 'EXECUTING' && status !== 'DONE' && (
                        <>
                            <button className="button ghost" onClick={onClose}>Cancel</button>
                            {status === 'IDLE' && (
                                <button
                                    className="button danger"
                                    disabled={!canExecute}
                                    onClick={handleExecute}
                                    style={{ opacity: canExecute ? 1 : 0.5 }}
                                >
                                    EXECUTE FLATTEN
                                </button>
                            )}
                            {status === 'MANUAL_REQUIRED' && (
                                <button className="button primary" onClick={onClose}>I Understand</button>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
