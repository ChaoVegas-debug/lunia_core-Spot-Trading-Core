import React, { useState, useEffect } from 'react';
import { usePreview } from '../../hooks/usePreview';
import { journalStore } from '../../store/JournalStore';
import { SimOrder } from '../../preview/PreviewStore';

interface StrategyOrdersDrawerProps {
    strategyId: string;
    isOpen: boolean;
    onClose: () => void;
}

export const StrategyOrdersDrawer: React.FC<StrategyOrdersDrawerProps> = ({ strategyId, isOpen, onClose }) => {
    const { isPreview, previewStore, state } = usePreview();
    const [orders, setOrders] = useState<SimOrder[]>([]);

    useEffect(() => {
        if (isOpen) {
            if (isPreview) {
                // Poll or fetch from store
                setOrders(previewStore.getOrders(strategyId));
            } else {
                // Production: Fetch from API (Mocked for now as empty or not implemented)
                setOrders([]);
            }
        }
    }, [isOpen, strategyId, isPreview, state.sim_orders]); // Re-run when store orders change

    if (!isOpen) return null;

    const handleCancel = (orderId: string) => {
        if (isPreview) {
            previewStore.cancelSimOrder(orderId);
            // State update happens via subscription/effect
        } else {
            alert("Production Order Cancellation: Not enabled in this view. Use Trade Terminal.");
        }
    };

    return (
        <>
            <div style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0,0,0,0.5)',
                zIndex: 999
            }} onClick={onClose} />
            <div style={{
                position: 'fixed',
                top: 0,
                right: 0,
                width: '400px',
                height: '100vh',
                background: 'var(--bg-panel)',
                borderLeft: '1px solid var(--border-color)',
                zIndex: 1000,
                boxShadow: '-4px 0 20px rgba(0,0,0,0.5)',
                padding: '2rem',
                overflowY: 'auto'
            }}>
                <div className="flex-between mb-4" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0 }}>Active Orders</h3>
                    <button className="button ghost small" onClick={onClose}>Close</button>
                </div>

                <div className="alert secondary small mb-4" style={{ marginBottom: '1rem', padding: '0.75rem', borderRadius: '4px', background: 'var(--bg-panel-soft)' }}>
                    Showing active orders for Strategy <strong>{strategyId}</strong>.
                    {isPreview && <div className="text-warning tiny mt-1">SOURCE: SIMULATION ENGINE</div>}
                </div>

                <div className="flex-col gap-2" style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {orders.length === 0 ? (
                        <div className="muted small text-center py-4">No active orders found.</div>
                    ) : (
                        orders.map(order => (
                            <div key={order.id} className="card p-2" style={{ padding: '0.75rem', border: '1px solid var(--border-color)', borderLeft: `3px solid ${order.side === 'BUY' ? 'var(--accent-success)' : 'var(--accent-danger)'}`, borderRadius: '4px' }}>
                                <div className="flex-between mb-1" style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span className={`badge ${order.side === 'BUY' ? 'success' : 'danger'}`}>{order.side}</span>
                                    <span className="font-mono">{order.symbol}</span>
                                </div>
                                <div className="flex-between small muted mb-2" style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span>{order.qty} @ {order.price.toFixed(2)}</span>
                                    <span>{new Date(order.created_ts).toLocaleTimeString()}</span>
                                </div>
                                <div className="flex-between" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span className={`tiny badge ${order.status === 'OPEN' ? 'primary' : 'secondary'}`} style={{ fontSize: '0.7em' }}>{order.status}</span>
                                    {isPreview && <span className="tiny badge warning" style={{ fontSize: '0.7em' }}>SIM</span>}
                                </div>
                                {order.status === 'OPEN' && (
                                    <button className="button tiny outline danger full-width mt-2" onClick={() => handleCancel(order.id)} style={{ marginTop: '0.5rem', width: '100%' }}>
                                        CANCEL ORDER
                                    </button>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>
        </>
    );
};
