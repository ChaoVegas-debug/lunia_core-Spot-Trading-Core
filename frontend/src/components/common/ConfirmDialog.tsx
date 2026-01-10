import React from 'react';

interface ConfirmDialogProps {
    onConfirm: () => void;
    onCancel: () => void;
    deadline?: number;
    title?: string;
    message?: string; // Optional message override
    children?: React.ReactNode;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
    onConfirm,
    onCancel,
    deadline,
    title = "CONFIRM EXECUTION",
    message,
    children
}) => {
    const [timeLeft, setTimeLeft] = React.useState<number | null>(null);

    React.useEffect(() => {
        if (!deadline) return;

        const tick = () => {
            const diff = Math.max(0, deadline - Date.now());
            setTimeLeft(Math.ceil(diff / 1000));
            if (diff <= 0) {
                // Could auto-cancel here or let parent handle
                // onCancel(); 
            }
        };
        tick();
        const interval = setInterval(tick, 1000);
        return () => clearInterval(interval);
    }, [deadline]);

    const isExpired = timeLeft !== null && timeLeft <= 0;

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0, 0, 0, 0.8)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1100
        }}>
            <div className="card" style={{ width: '400px', border: '1px solid var(--accent-danger)', padding: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h3 style={{ color: 'var(--accent-danger)', margin: 0 }}>{title}</h3>
                    {timeLeft !== null && (
                        <div style={{ fontSize: '1.2em', fontWeight: 'bold', color: isExpired ? 'red' : 'white' }}>
                            {timeLeft}s
                        </div>
                    )}
                </div>

                {message ? (
                    <p style={{ lineHeight: '1.5', marginBottom: '24px' }}>{message}</p>
                ) : children ? (
                    <div style={{ marginBottom: '24px' }}>{children}</div>
                ) : (
                    <p className="small muted" style={{ lineHeight: '1.5', marginBottom: '24px' }}>
                        This action will execute trades according to the approved proposal. This is irreversible.
                    </p>
                )}

                {isExpired && (
                    <div className="alert error">
                        CONFIRMATION EXPIRED. Please Review Again.
                    </div>
                )}
                {!isExpired && !message && !children && (
                    <div className="alert warn">
                        <strong>Warning:</strong> Live capital will be allocated immediately.
                    </div>
                )}

                <div className="flex-row" style={{ gap: '12px', justifyContent: 'flex-end', marginTop: '32px' }}>
                    <button className="button secondary" onClick={onCancel}>BACK</button>
                    <button
                        className="button danger"
                        onClick={onConfirm}
                        disabled={isExpired}
                        style={{ fontWeight: 'bold', opacity: isExpired ? 0.5 : 1 }}
                    >
                        CONFIRM
                    </button>
                </div>
            </div>
        </div>
    );
};
