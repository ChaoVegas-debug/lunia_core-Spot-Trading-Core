import React from 'react';

interface ConvertToStableModalProps {
    symbol: string;
    onClose: () => void;
    onConfirm: () => void;
}

export const ConvertToStableModal: React.FC<ConvertToStableModalProps> = ({ symbol, onClose, onConfirm }) => {
    return (
        <div className="modal-overlay">
            <div className="modal-content" style={{ maxWidth: '400px' }}>
                <div className="modal-header danger">
                    <h3>Convert to Stable: {symbol}</h3>
                </div>
                <div className="modal-body">
                    <p className="description mb-2">
                        You are about to liquidate 100% of your {symbol} position into base currency (USDT).
                    </p>
                    <div className="p-3 bg-red-900/20 border border-red-500/30 rounded text-center">
                        <div className="text-xl font-bold text-red-400 mb-1">NUCLEAR OPTION</div>
                        <div className="text-small opacity-80">This action overrides all strategy logic.</div>
                    </div>
                </div>
                <div className="modal-footer">
                    <button className="button ghost" onClick={onClose}>Cancel</button>
                    <button className="button danger" onClick={onConfirm}>
                        LIQUIDATE POSITION
                    </button>
                </div>
            </div>
        </div>
    );
};
