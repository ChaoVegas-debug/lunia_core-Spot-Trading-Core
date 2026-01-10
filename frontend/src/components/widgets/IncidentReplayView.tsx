import React, { useState, useRef, useEffect } from 'react';

export const IncidentReplayView: React.FC = () => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [tick, setTick] = useState(0);
    const timerRef = useRef<number | null>(null);

    // Mock Timeline Data (60 ticks representing 1 minute of a "Flash Crash")
    const totalTicks = 60;

    // Derived state based on tick
    const getScenarioState = (t: number) => {
        // Scenario: Stable -> Crash -> Recovery
        if (t < 20) return { price: 50000 + Math.random() * 100, equity: 100000, risk: 'LOW' };
        if (t < 40) return { price: 50000 - (t - 20) * 500, equity: 100000 - (t - 20) * 1000, risk: 'CRITICAL' };
        return { price: 40000 + (t - 40) * 100, equity: 80000 + (t - 40) * 200, risk: 'STABILIZING' };
    };

    const currentState = getScenarioState(tick);

    useEffect(() => {
        if (isPlaying) {
            timerRef.current = window.setInterval(() => {
                setTick(prev => {
                    if (prev >= totalTicks) {
                        setIsPlaying(false);
                        return prev;
                    }
                    return prev + 1;
                });
            }, 500); // 500ms per tick
        } else {
            if (timerRef.current) clearInterval(timerRef.current);
        }
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, [isPlaying]);

    return (
        <div className="card">
            <div className="card-header">
                <h3>Incident Forensics Replay</h3>
                <div className="button-group tiny">
                    <button className="button secondary" onClick={() => setTick(0)}>⏮</button>
                    <button className={`button ${isPlaying ? 'secondary' : 'primary'}`} onClick={() => setIsPlaying(!isPlaying)}>
                        {isPlaying ? '⏸ PAUSE' : '▶ PLAY'}
                    </button>
                </div>
            </div>

            <div className="card-body">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1rem' }}>
                    <span className="small font-mono">10:00:00</span>
                    <input
                        type="range"
                        min="0"
                        max={totalTicks}
                        value={tick}
                        onChange={e => { setIsPlaying(false); setTick(parseInt(e.target.value)); }}
                        style={{ flex: 1 }}
                    />
                    <span className="small font-mono">10:01:00</span>
                </div>

                <div className="grid cols-3" style={{ gap: '12px', textAlign: 'center' }}>
                    <div className="p-2 bg-dark-2 rounded">
                        <div className="small muted">Simulated BTC Price</div>
                        <div className="large font-mono">${currentState.price.toFixed(0)}</div>
                    </div>
                    <div className="p-2 bg-dark-2 rounded">
                        <div className="small muted">Portfolio Equity</div>
                        <div className="large font-mono" style={{ color: currentState.equity < 90000 ? 'var(--accent-danger)' : 'white' }}>
                            ${currentState.equity.toLocaleString()}
                        </div>
                    </div>
                    <div className="p-2 bg-dark-2 rounded">
                        <div className="small muted">Risk State</div>
                        <div className={`badge ${currentState.risk === 'CRITICAL' ? 'danger' : currentState.risk === 'LOW' ? 'success' : 'warn'}`}>
                            {currentState.risk}
                        </div>
                    </div>
                </div>

                <div className="mt-4 p-2 bg-dark-3 rounded small font-mono opacity-75">
                    <strong>Log Stream T+{tick}s:</strong>
                    <div style={{ marginTop: '4px' }}>
                        {tick < 20 && <div>[INFO] Market stable. Algo active.</div>}
                        {tick >= 20 && tick < 25 && <div className="text-warn">[WARN] High volatility detected.</div>}
                        {tick >= 25 && tick < 40 && <div className="text-error">[CRITICAL] Stop-Loss triggered! Dumping assets...</div>}
                        {tick >= 40 && <div>[INFO] Recovery mode engaged. Buying dip.</div>}
                    </div>
                </div>
            </div>
        </div>
    );
};
