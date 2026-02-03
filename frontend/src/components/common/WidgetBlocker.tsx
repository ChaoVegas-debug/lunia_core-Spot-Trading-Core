import React from 'react';

interface WidgetBlockerProps {
    reason: string;
    detail?: string;
    action?: string;
    icon?: string;
}

export const WidgetBlocker: React.FC<WidgetBlockerProps> = ({
    reason,
    detail,
    action = "Check System Status",
    icon = "🔒"
}) => {
    return (
        <div className="widget-blocker" style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            minHeight: '120px',
            background: 'rgba(20, 0, 0, 0.6)',
            border: '1px solid rgba(255, 50, 50, 0.3)',
            borderRadius: '8px',
            padding: '16px',
            textAlign: 'center',
            color: '#ffaaaa',
            backdropFilter: 'blur(2px)'
        }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>{icon}</div>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                WIDGET BLOCKED
            </h3>
            <div style={{ fontWeight: 'bold', marginBottom: '4px', color: '#ff4444' }}>
                {reason}
            </div>
            {detail && (
                <div style={{ fontSize: '11px', opacity: 0.8, marginBottom: '12px', maxWidth: '90%' }}>
                    {detail}
                </div>
            )}
            {action && (
                <div style={{
                    fontSize: '10px',
                    background: 'rgba(255,255,255,0.1)',
                    padding: '4px 8px',
                    borderRadius: '4px'
                }}>
                    Suggested Action: {action}
                </div>
            )}
        </div>
    );
};
