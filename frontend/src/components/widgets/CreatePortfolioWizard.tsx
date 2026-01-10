import React, { useState, useEffect } from 'react';
import { getResearchCards, createPortfolio } from '../../api/adapter';
import { safeArray } from '../../utils/safe';
import { ResearchCard } from '../../api/types';
import { AssetResearchCard } from './AssetResearchCard';

interface Props {
    onClose: () => void;
}

export const CreatePortfolioWizard: React.FC<Props> = ({ onClose }) => {
    const [step, setStep] = useState(1);
    const [cards, setCards] = useState<ResearchCard[]>([]);
    const [selected, setSelected] = useState<string[]>([]);
    const [analyzing, setAnalyzing] = useState(false);

    useEffect(() => {
        // Mock loading cards
        getResearchCards(new AbortController().signal).then(res => {
            // If empty (simulatedBackend fallback might need explicit call or data)
            if (safeArray(res?.items).length === 0) {
                setCards([
                    { symbol: 'BTC', score: 92, thesis_short: 'Strong institutional inflows via ETFs.', zones: { entry: '61k', exit: '75k', invalidation: '58k' }, probability: 0.85, expected_return: 0.15 },
                    { symbol: 'ETH', score: 88, thesis_short: 'L2 blob scaling catalyst.', zones: { entry: '3200', exit: '4500', invalidation: '2800' }, probability: 0.75, expected_return: 0.25 },
                    { symbol: 'SOL', score: 75, thesis_short: 'Activity metric divergence.', zones: { entry: '135', exit: '180', invalidation: '110' }, probability: 0.6, expected_return: 0.40 },
                    { symbol: 'AVAX', score: 68, thesis_short: 'Gaming subnets gaining traction.', zones: { entry: '45', exit: '65', invalidation: '35' }, probability: 0.55, expected_return: 0.50 }
                ]);
            } else {
                setCards(res.items as any);
            }
        });
    }, []);

    const handleDeploy = async () => {
        setAnalyzing(true);
        await new Promise(r => setTimeout(r, 1500)); // Fake analysis
        await createPortfolio(new AbortController().signal);
        setAnalyzing(false);
        onClose(); // In real app, route to new portfolio
        alert("Portfolio Deployed Successfully!");
    };

    return (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', zIndex: 999, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <div className="card" style={{ width: '800px', height: '600px', display: 'flex', flexDirection: 'column' }}>
                <header className="flex-between mb-4 border-b pb-2">
                    <h2>AI Portfolio Architect {step}/2</h2>
                    <button className="button ghost" onClick={onClose}>CLOSE</button>
                </header>

                {step === 1 && (
                    <div style={{ flex: 1, overflowY: 'auto' }}>
                        <h3 className="mb-2">Select Universe</h3>
                        <div className="grid-3" style={{ gap: '1rem' }}>
                            {cards.map(c => (
                                <AssetResearchCard
                                    key={c.symbol}
                                    data={c}
                                    selected={selected.includes(c.symbol)}
                                    onToggle={() => {
                                        setSelected(prev => prev.includes(c.symbol) ? prev.filter(x => x !== c.symbol) : [...prev, c.symbol]);
                                    }}
                                />
                            ))}
                        </div>
                    </div>
                )}

                {step === 2 && (
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                        <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🤖 🧠 📈</div>
                        <h3>Constructing Risk Parity Model...</h3>
                        <p className="muted">Assets: {selected.join(', ')}</p>
                        {analyzing && <div className="badge warning">OPTIMIZING WEIGHTS...</div>}
                    </div>
                )}

                <footer className="mt-4 border-t pt-4 flex-between">
                    <button className="button secondary" disabled={step === 1} onClick={() => setStep(1)}>BACK</button>
                    {step === 1 ? (
                        <button className="button primary" disabled={selected.length === 0} onClick={() => setStep(2)}>ANALYZE & SETUP</button>
                    ) : (
                        <button className="button success" onClick={handleDeploy} disabled={analyzing}>
                            {analyzing ? 'DEPLOYING...' : 'APPROVE & DEPLOY'}
                        </button>
                    )}
                </footer>
            </div>
        </div>
    );
};
