import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import {
    setPortfolioDraftConfig,
    setPortfolioDraftAssets,
    analyzePortfolioDraft,
    createPortfolio,
    getPortfolioStructure
} from '../../api/adapter';
import { buildClient } from '../../api/client';
import { getPlan, isUiRiskAllowed, type UIRiskProfile } from '../../domain/subscription/plans';
import { LockedFeatureModal } from './LockedFeatureModal';
import { useDashboard } from '../../context/DashboardContext';

interface CreatePortfolioModalProps {
    onClose: () => void;
    onDeploy: (config: any) => void;
}

const ASSETS = ['BTC', 'ETH', 'SOL', 'MATIC', 'NEAR', 'AVAX', 'LINK', 'UNI', 'AAVE', 'DOT'];

export const CreatePortfolioModal: React.FC<CreatePortfolioModalProps> = ({ onClose, onDeploy }) => {
    const auth = useAuth();
    const { addToast } = useDashboard();
    const client = buildClient(auth);
    const plan = getPlan(auth.user?.tier);

    const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
    const [loading, setLoading] = useState(false);
    const [isLimitReached, setIsLimitReached] = useState(false);
    const [checkingLimit, setCheckingLimit] = useState(true);

    // Analysis State
    const [analysisRunning, setAnalysisRunning] = useState(false);
    const [aiAnalysis, setAiAnalysis] = useState<{ confidence: number; risk_class: string; drawdown_est: number } | null>(null);
    const [analysisError, setAnalysisError] = useState<string | null>(null);
    const [limitCheckError, setLimitCheckError] = useState(false);

    // Form State
    const [horizon, setHorizon] = useState<'SHORT' | 'MID' | 'LONG'>('MID');
    const [riskProfile, setRiskProfile] = useState<UIRiskProfile>('BALANCED');
    const [selectedAssets, setSelectedAssets] = useState<Set<string>>(new Set(['BTC', 'ETH']));

    // Generic Lock State
    const [lockReason, setLockReason] = useState<{ isLocked: boolean; title: string; reason: string; requiredTier?: any } | null>(null);

    // Check Limits on Mount
    React.useEffect(() => {
        const check = async () => {
            try {
                const portfolios = await getPortfolioStructure(new AbortController().signal, client);
                // Safe check if array
                if (Array.isArray(portfolios) && portfolios.length >= plan.max_portfolios) {
                    setIsLimitReached(true);
                }
            } catch (e) {
                console.warn("Limit check unavailable, proceeding conservatively", e);
                setLimitCheckError(true);
                // Honest UI: If we can't verify, we don't hard-block here, 
                // but we might warn or let backend reject.
                // Decision: Allow proceed with warning.
            } finally {
                setCheckingLimit(false);
            }
        };
        check();
    }, []);

    const toggleAsset = (asset: string) => {
        const next = new Set(selectedAssets);
        if (next.has(asset)) next.delete(asset);
        else next.add(asset);
        setSelectedAssets(next);
    };

    const runAnalysis = async () => {
        setAnalysisRunning(true);
        setAnalysisError(null);

        const ac = new AbortController();
        try {
            const res = await analyzePortfolioDraft(ac.signal, client);
            setAiAnalysis(res);
        } catch (err: any) {
            console.error("Analysis Failed", err);

            // DEMO FALLBACK
            const isDemo = import.meta.env.VITE_DEMO_MODE === '1';
            if (isDemo) {
                // Mock result
                setTimeout(() => {
                    setAiAnalysis({ confidence: 0.88, risk_class: 'MODERATE', drawdown_est: 0.12 });
                    setAnalysisRunning(false);
                }, 1000);
                return;
            }

            setAnalysisError("Governance Gateway: Analysis Service Unreachable or Risk Model Failed.");
        } finally {
            if (import.meta.env.VITE_DEMO_MODE !== '1') {
                setAnalysisRunning(false);
            }
        }
    };

    const handleNext = async () => {
        setLoading(true);
        const ac = new AbortController();

        try {
            if (step === 1) {
                await setPortfolioDraftConfig({ horizon, risk_profile: riskProfile }, ac.signal, client);
                setStep(2);
            } else if (step === 2) {
                await setPortfolioDraftAssets(Array.from(selectedAssets), ac.signal, client);
                setStep(3);
            } else if (step === 3) {
                // Check if ROCKET is denied (example logic, if AI returns HIGH risk logic could be here)
                if (riskProfile === 'ROCKET' && aiAnalysis && aiAnalysis.risk_class === 'HIGH' && aiAnalysis.confidence < 0.7) {
                    addToast({ type: 'WARNING', message: "Governance Veto: 'ROCKET' profile rejected due to low confidence score." });
                    // Don't advance
                } else {
                    setStep(4);
                }
            }
        } catch (e) {
            console.error("Step failed", e);
        } finally {
            setLoading(false);
        }
    };

    const handleBack = () => {
        setAnalysisError(null);
        if (step > 1) setStep((s) => (s - 1) as any);
    };

    const handleDeploy = async () => {
        setLoading(true);
        const ac = new AbortController();
        try {
            await createPortfolio(ac.signal, client);
            setTimeout(() => {
                onDeploy({});
                onClose();
            }, 500);
        } catch (e) {
            console.error("Deploy failed", e);
            addToast({ type: 'ERROR', message: "Deployment Failed: " + String(e) });
        } finally {
            setLoading(false);
        }
    };

    if (checkingLimit) return <div className="modal-backdrop"><div className="loader"></div></div>;

    // Limit Reached State
    if (isLimitReached) {
        return (
            <LockedFeatureModal
                title="Portfolio Limit Reached"
                reason={`You have reached the limit of ${plan.max_portfolios} active portfolios on the ${plan.name} plan.`}
                requiredTier={plan.id === 'BEGINNER' ? 'STD_RETAIL' : 'ADV_RETAIL'}
                onClose={onClose}
            />
        );
    }

    return (
        <div className="modal-backdrop">
            {lockReason && (
                <LockedFeatureModal
                    title={lockReason.title}
                    reason={lockReason.reason}
                    requiredTier={lockReason.requiredTier}
                    onClose={() => setLockReason(null)}
                />
            )}
            <div className="card modal-content" style={{ width: '600px', padding: '0', overflow: 'hidden', border: '1px solid var(--accent-primary)' }}>
                {/* Header */}
                <div className="card-header" style={{ background: 'var(--bg-secondary)', padding: '16px', borderBottom: '1px solid #333' }}>
                    <div>
                        <h3>Deploy New Strategy</h3>
                        <p className="tiny muted uppercase">Institutional Engine • Portfolio Construction</p>
                        {limitCheckError && <div className="tiny text-warn">⚠ Plan Limit Check Unavailable</div>}
                    </div>
                    <div className="flex-row">
                        <span className={`status-chip ${step >= 1 ? 'ok' : 'muted'}`}>1. CONFIG</span>
                        <span className="muted">→</span>
                        <span className={`status-chip ${step >= 2 ? 'ok' : 'muted'}`}>2. UNIV</span>
                        <span className="muted">→</span>
                        <span className={`status-chip ${step >= 3 ? 'ok' : 'muted'}`}>3. AI</span>
                        <span className="muted">→</span>
                        <span className={`status-chip ${step >= 4 ? 'ok' : 'muted'}`}>4. EXEC</span>
                    </div>
                </div>

                {/* Body */}
                <div style={{ padding: '24px', minHeight: '320px' }}>

                    {/* STEP 1: CONFIG */}
                    {step === 1 && (
                        <div className="flex-col" style={{ gap: '24px' }}>
                            <div>
                                <div className="small muted uppercase mb-2">Investment Horizon</div>
                                <div className="grid cols-3" style={{ gap: '12px' }}>
                                    {(['SHORT', 'MID', 'LONG'] as const).map(h => (
                                        <button
                                            key={h}
                                            className={`button large ${horizon === h ? 'primary' : 'ghost'}`}
                                            onClick={() => setHorizon(h)}
                                        >
                                            {h} TERM
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div>
                                <div className="small muted uppercase mb-2">Risk Appetite</div>
                                <div className="grid cols-3" style={{ gap: '12px' }}>
                                    <button
                                        className={`button large ${riskProfile === 'SHIELD' ? 'ok' : 'ghost'}`}
                                        disabled={!isUiRiskAllowed(plan, 'SHIELD')}
                                        onClick={() => setRiskProfile('SHIELD')}
                                        style={{ opacity: isUiRiskAllowed(plan, 'SHIELD') ? 1 : 0.4 }}
                                    >
                                        🛡 SHIELD
                                    </button>
                                    <button
                                        className={`button large ${riskProfile === 'BALANCED' ? 'primary' : 'ghost'}`}
                                        disabled={!isUiRiskAllowed(plan, 'BALANCED')}
                                        onClick={() => setRiskProfile('BALANCED')}
                                        style={{ opacity: isUiRiskAllowed(plan, 'BALANCED') ? 1 : 0.4 }}
                                    >
                                        ⚖ BALANCED
                                    </button>
                                    <button
                                        className={`button large ${riskProfile === 'ROCKET' ? 'danger' : 'ghost'}`}
                                        onClick={() => {
                                            if (isUiRiskAllowed(plan, 'ROCKET')) {
                                                setRiskProfile('ROCKET');
                                            } else {
                                                setLockReason({
                                                    isLocked: true,
                                                    title: "Risk Profile Restricted",
                                                    reason: "The 'ROCKET' risk engine profile is not available on your current plan due to volatility governance.",
                                                    requiredTier: 'INST_LITE'
                                                });
                                            }
                                        }}
                                        style={{
                                            opacity: isUiRiskAllowed(plan, 'ROCKET') ? 1 : 0.6,
                                            cursor: 'pointer'
                                        }}
                                    >
                                        🚀 ROCKET
                                        {!isUiRiskAllowed(plan, 'ROCKET') && " 🔒"}
                                    </button>
                                </div>
                            </div>

                        </div>
                    )}

                    {/* STEP 2: ASSETS */}
                    {step === 2 && (
                        <div className="flex-col" style={{ gap: '16px' }}>
                            <div className="small muted uppercase">Select Asset Universe</div>
                            <div className="grid cols-4" style={{ gap: '8px' }}>
                                {ASSETS.map(asset => (
                                    <button
                                        key={asset}
                                        className={`button ${selectedAssets.has(asset) ? 'active-mode' : 'ghost'}`}
                                        onClick={() => toggleAsset(asset)}
                                        style={{ justifyContent: 'space-between', padding: '12px' }}
                                    >
                                        <span>{asset}</span>
                                        {selectedAssets.has(asset) && <span className="text-cyan">✓</span>}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* STEP 3: AI ANALYSIS (GOVERNANCE GATE) */}
                    {step === 3 && (
                        <div className="flex-col" style={{ gap: '16px', height: '100%', justifyContent: 'center' }}>

                            {!aiAnalysis && !analysisRunning && !analysisError && (
                                <div style={{ textAlign: 'center', padding: '2rem' }}>
                                    <div className="badge warning large" style={{ marginBottom: '1rem' }}>GOVERNANCE CHECK REQUIRED</div>
                                    <p className="muted" style={{ marginBottom: '2rem' }}>
                                        Before deployment, the AI MUST simulate volatility against the selected risk profile to generate a confidence score.
                                    </p>
                                    <button className="button primary large" onClick={runAnalysis}>
                                        RUN ANALYSIS SIMULATION
                                    </button>
                                </div>
                            )}

                            {analysisRunning && (
                                <div className="flex-center" style={{ flexDirection: 'column' }}>
                                    <div className="loader" />
                                    <p className="small blink" style={{ marginTop: '1rem' }}>Running Monte Carlo Simulations...</p>
                                </div>
                            )}

                            {aiAnalysis && (
                                <div className="grid cols-2" style={{ gap: '16px' }}>
                                    <div className="card subtle">
                                        <div className="muted uppercase tiny">Model Confidence</div>
                                        <div className="text-cyan" style={{ fontSize: '2rem', fontWeight: 700 }}>
                                            {(aiAnalysis.confidence * 100).toFixed(1)}%
                                        </div>
                                    </div>
                                    <div className="card subtle">
                                        <div className="muted uppercase tiny">Risk Classification</div>
                                        <div className={`text-${aiAnalysis.risk_class === 'LOW' ? 'green' : aiAnalysis.risk_class === 'HIGH' ? 'red' : 'primary'}`} style={{ fontSize: '2rem', fontWeight: 700 }}>
                                            {aiAnalysis.risk_class}
                                        </div>
                                    </div>
                                    <div className="card subtle" style={{ gridColumn: 'span 2' }}>
                                        <div className="muted uppercase tiny">Projected Max Drawdown (95% CI)</div>
                                        <div className="text-red" style={{ fontSize: '1.5rem', fontWeight: 700 }}>
                                            -{(aiAnalysis.drawdown_est * 100).toFixed(2)}%
                                        </div>
                                    </div>
                                    <div className="alert ok small" style={{ gridColumn: 'span 2' }}>
                                        ✓ Risk Model Validated. Deployment Authorized.
                                    </div>
                                </div>
                            )}

                            {analysisError && (
                                <div className="alert error" style={{ textAlign: 'center' }}>
                                    <strong>Analysis Failed</strong>
                                    <p className="small">{analysisError}</p>
                                    <button className="button small outline" onClick={runAnalysis} style={{ marginTop: '1rem' }}>Retry</button>
                                </div>
                            )}
                        </div>
                    )}

                    {/* STEP 4: EXECUTION */}
                    {step === 4 && (
                        <div className="flex-col" style={{ gap: '24px' }}>
                            <div className="alert info">
                                Ready to deploy <strong>{riskProfile} / {horizon}</strong> Strategy.
                            </div>
                            <div className="alert warn">
                                <strong>DISCLAIMER:</strong> Algorithmic trading involves significant risk.
                            </div>
                        </div>
                    )}

                </div>

                {/* Footer */}
                <div style={{ padding: '16px', display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid #333', background: 'var(--bg-secondary)' }}>
                    <button className="button ghost" onClick={handleBack} disabled={loading || analysisRunning}>BACK</button>
                    {step === 4 ? (
                        <button className="button primary" onClick={handleDeploy} disabled={loading}>
                            {loading ? 'DEPLOYING...' : 'APPROVE & DEPLOY'}
                        </button>
                    ) : (
                        <button
                            className="button"
                            onClick={handleNext}
                            // Locked if Step 3 and no analysis result
                            disabled={loading || (step === 2 && selectedAssets.size === 0) || (step === 3 && !aiAnalysis)}
                        >
                            {loading ? '...' : 'NEXT'}
                        </button>
                    )}
                    <button className="button ghost" onClick={onClose} style={{ marginLeft: 'auto', color: '#666' }}>CANCEL</button>
                </div>
            </div>
        </div>
    );
};
