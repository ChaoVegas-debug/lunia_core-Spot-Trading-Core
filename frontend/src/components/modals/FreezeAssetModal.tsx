import React from 'react';

interface FreezeAssetModalProps {
    symbol: string;
    onClose: () => void;
    onConfirm: () => void;
}

export const FreezeAssetModal: React.FC<FreezeAssetModalProps> = ({ symbol, onClose, onConfirm }) => {
    return (
        <div className="modal-overlay">
            <div className="modal-content" style={{ maxWidth: '400px' }}>
                <div className="modal-header danger">
                    <h3>Freeze Asset: {symbol}</h3>
                </div>
                <div className="modal-body">
                    <p className="description">
                        This will:
                    </p>
                    <ul className="list-disc ml-4 my-2 text-small muted">
                        <li>Cancel all open orders for {symbol}</li>
                        <li>Block new BUY orders</li>
                        <li>Allow MANUAL reducing only</li>
                    </ul>
                    <div className="status-badge warning mt-2">
                        Requires Admin Approval to unfreeze.
                    </div>
                </div>
                <div className="modal-footer">
                    <button className="button ghost" onClick={onClose}>Cancel</button>
                    <button className="button danger" onClick={onConfirm}>
                        Confirm Freeze
                    </button>
                </div>
            </div>
        </div>
    );
};
