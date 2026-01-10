
import React from 'react';
import { usePolledResource } from '../../hooks/usePolledResource';
import { getResearchCards } from '../../api/adapter';
import { useAuth } from '../../hooks/useAuth';

export const AIResearchCards: React.FC = () => {
    const auth = useAuth();
    const { data } = usePolledResource((signal) => getResearchCards(signal, { role: auth.role }), 10000, []);
    const cards = data?.items || [];

    return (
        <div style={{ marginTop: '2rem' }}>
            <h3 style={{ borderBottom: '1px solid #333', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
                🧠 AI Research Feed
            </h3>

            <div className="grid cols-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
                {cards.map((card: any) => (
                    <div className="card" key={card.symbol} style={{ borderLeft: `4px solid ${card.risk === 'LOW' ? 'var(--status-ok)' : card.risk === 'HIGH' ? 'var(--status-error)' : 'var(--status-risk)'}` }}>
                        <div className="card-header flex-between" style={{ marginBottom: '0.5rem', paddingBottom: '0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span style={{ fontWeight: 800, fontSize: '1.2rem' }}>{card.symbol}</span>
                                <span className="badge">{card.risk} RISK</span>
                            </div>
                            <div className="tiny muted">{card.confidence}% CONF</div>
                        </div>

                        <p style={{ fontSize: '0.9rem', lineHeight: '1.4', margin: '0 0 1rem 0', minHeight: '3em' }}>
                            {card.thesis}
                        </p>

                        <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem' }}>
                            <div style={{ flex: 1, background: '#111', padding: '0.5rem', borderRadius: '4px' }}>
                                <div className="tiny muted uppercase">Buy Zone</div>
                                <div style={{ color: 'var(--status-ok)', fontWeight: 600 }}>{card.zone_buy}</div>
                            </div>
                            <div style={{ flex: 1, background: '#111', padding: '0.5rem', borderRadius: '4px' }}>
                                <div className="tiny muted uppercase">Sell Zone</div>
                                <div style={{ color: 'var(--status-risk)', fontWeight: 600 }}>{card.zone_sell}</div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
            {cards.length === 0 && (
                <div className="card subtle" style={{ padding: '2rem', textAlign: 'center' }}>
                    Generating Market Research...
                </div>
            )}
        </div>
    );
};
