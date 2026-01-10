import React from 'react';

interface DriftWarningBannerProps {
    status?: 'NONE' | 'SOFT' | 'HARD';
    reason?: string;
    onAck?: () => void;
}

export const DriftWarningBanner: React.FC<DriftWarningBannerProps> = ({ status, reason, onAck }) => {
    if (!status || status === 'NONE') return null;

    const isHard = status === 'HARD';

    return (
        <div className={`alert ${isHard ? 'danger error' : 'warn'}`} style={{
            marginBottom: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderLeft: isHard ? '5px solid var(--accent-danger)' : '5px solid var(--accent-warn)'
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <span style={{ fontSize: '1.5rem' }}>{isHard ? '🛑' : '⚠️'}</span>
                <div>
                    <div style={{ fontWeight: 'bold', textTransform: 'uppercase' }}>
                        {isHard ? 'INTEGRITY VIOLATION (HARD DRIFT)' : 'PORTFOLIO DRIFT DETECTED'}
                    </div>
                    <div className="small opacity-80">
                        {reason || (isHard
                            ? "Manual intervention detected. Automation has been downgraded to SEMI-AUTO."
                            : "Asset values deviating from target model. Review recommended.")}
                    </div>
                </div>
            </div>

            {isHard && onAck && (
                <button className="button small outline-danger" onClick={onAck}>
                    ACKNOWLEDGE & RE-ARM
                </button>
            )}
        </div>
    );
};
