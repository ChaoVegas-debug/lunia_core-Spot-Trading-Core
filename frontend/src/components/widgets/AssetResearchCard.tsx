import React from 'react';
import { ResearchCard } from '../../api/types';

interface Props {
    data: ResearchCard;
    selected: boolean;
    onToggle: () => void;
}

export const AssetResearchCard: React.FC<Props> = ({ data, selected, onToggle }) => {
    return (
        <div
            onClick={onToggle}
            style={{
                cursor: 'pointer',
                background: selected ? 'rgba(0, 240, 255, 0.1)' : 'rgba(255,255,255,0.02)',
                border: `1px solid ${selected ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)'}`,
                borderRadius: '8px',
                padding: '12px',
                transition: 'all 0.2s',
                position: 'relative'
            }}
        >
            <div className="flex-between mb-2">
                <div style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>{data.symbol}</div>
                <div className="badge tiny">{data.score}/100</div>
            </div>

            <div style={{ fontSize: '0.85rem', color: '#ccc', marginBottom: '8px', height: '40px', overflow: 'hidden' }}>
                {data.thesis_short}
            </div>

            <div className="grid-2" style={{ gap: '8px', fontSize: '0.75rem' }}>
                <div className="muted">Buy Zone: <span className="text-white">{data.zones.entry}</span></div>
                <div className="muted">Target: <span className="text-success">{data.zones.exit}</span></div>
            </div>

            {selected && (
                <div style={{ position: 'absolute', top: '8px', right: '8px', color: 'var(--accent-primary)' }}>
                    ✅
                </div>
            )}
        </div>
    );
};
