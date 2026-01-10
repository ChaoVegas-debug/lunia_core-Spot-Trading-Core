import React, { useState } from 'react';

interface ReduceRiskModalProps {
    symbol: string;
    onClose: () => void;
    onConfirm: (amount: number) => void;
}

export const ReduceRiskModal: React.FC<ReduceRiskModalProps> = ({ symbol, onClose, onConfirm }) => {
    const [percentage, setPercentage] = useState(10);

    return (
        <div className="modal-overlay">
            <div className="modal-content" style={{ maxWidth: '400px' }}>
                <div className="modal-header danger">
                    <h3>Reduce Risk: {symbol}</h3>
                </div>
                <div className="modal-body">
                    <p className="mb-4">Select percentage of position to liquidate immediately.</p>

                    <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                        {[10, 25, 50, 75].map(p => (
                            <button
                                key={p}
                                className={`button small ${percentage === p ? 'primary' : 'outline'}`}
                                onClick={() => setPercentage(p)}
                            >
                                {p}%
                            </button>
                        ))}
                    </div>

                    <div className="p-2 bg-dark rounded text-small mb-4">
                        <strong>Governance Consequence:</strong>
                        <br />
                        Creating a MANUAL SELL order overriding current strategy.
                    </div>
                </div>
                <div className="modal-footer">
                    <button className="button ghost" onClick={onClose}>Cancel</button>
                    <button className="button danger" onClick={() => onConfirm(percentage)}>
                        Confirm Sell {percentage}%
                    </button>
                </div>
            </div>
        </div>
    );
};
