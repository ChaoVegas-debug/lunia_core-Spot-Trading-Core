import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface TourStep {
    id: string;
    path: string;
    title: string;
    content: string;
    target?: string; // CSS selector if we were doing positioning, ignoring for now as per plan (simple overlay)
}

const TOUR_STEPS: TourStep[] = [
    {
        id: 'intro',
        path: '/getting-started',
        title: 'Welcome to Lunia',
        content: 'This tour will guide you through the setup of your institutional-grade trading environment. We start with System Governance.'
    },
    {
        id: 'system-mode',
        path: '/system',
        title: 'Step 1: System Control',
        content: 'Set your operational mode. "Semi-Auto" is recommended for supervised AI trading. Configure your Capital Cap below.'
    },
    {
        id: 'risk-profile',
        path: '/risk',
        title: 'Step 2: Risk Limits',
        content: 'Define hard constraints. Active risk limits act as a "Veto Layer" preventing any AI action that violates your safety parameters.'
    },
    {
        id: 'strategies',
        path: '/strategies',
        title: 'Step 3: Strategy Composition',
        content: 'Select and weight your algorithm mix. You can combine "Shield" (Conservative) and "Rocket" (Aggressive) strategies.'
    },
    {
        id: 'exchange-keys',
        path: '/exchange-keys',
        title: 'Step 4: Venue Connectivity',
        content: 'Connect your exchange accounts. Keys are stored encrypted. You need at least one active venue to deploy.'
    },
    {
        id: 'portfolio-wizard',
        path: '/portfolio',
        title: 'Step 5: Portfolio Construction',
        content: 'Create your target portfolio using the Wizard. The AI will analyze your asset selection against your risk profile.'
    },
    {
        id: 'cockpit-ready',
        path: '/trader',
        title: 'Ready to Trade',
        content: 'You are now in the Trader Cockpit. Monitor "Reality vs Model" and "Execution Timeline" here. Good luck.'
    }
];

export const GuidedOnboardingTour: React.FC<{ active: boolean, onClose: () => void }> = ({ active, onClose }) => {
    const navigate = useNavigate();
    const location = useLocation();

    // Find current step index based on state or default to 0
    // We store current step index in local state
    const [currentIndex, setCurrentIndex] = useState(0);

    // Sync route: When step changes, navigate
    useEffect(() => {
        if (!active) return;
        const step = TOUR_STEPS[currentIndex];
        if (location.pathname !== step.path) {
            navigate(step.path, { state: { tourActive: true, stepId: step.id } });
        }
    }, [currentIndex, active, navigate, location.pathname]);

    if (!active) return null;

    const step = TOUR_STEPS[currentIndex];
    const isLast = currentIndex === TOUR_STEPS.length - 1;

    const handleNext = () => {
        if (isLast) {
            onClose();
        } else {
            setCurrentIndex(prev => prev + 1);
        }
    };

    const handleBack = () => {
        if (currentIndex > 0) setCurrentIndex(prev => prev - 1);
    };

    return (
        <div style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            width: '320px',
            backgroundColor: 'var(--bg-panel)',
            border: '1px solid var(--accent-primary)',
            borderRadius: '8px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            zIndex: 9999,
            padding: '16px',
            animation: 'slideIn 0.3s ease-out'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className="badge primary tiny">GUIDED TOUR</span>
                <button className="button ghost tiny" onClick={onClose}>✕</button>
            </div>

            <h4 style={{ margin: '0 0 8px 0', color: 'white' }}>{step.title}</h4>
            <p className="small muted" style={{ lineHeight: '1.4', marginBottom: '16px' }}>
                {step.content}
            </p>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="tiny muted">
                    Step {currentIndex + 1} / {TOUR_STEPS.length}
                </div>
                <div className="button-group small">
                    <button
                        className="button secondary"
                        onClick={handleBack}
                        disabled={currentIndex === 0}
                    >
                        Prev
                    </button>
                    <button
                        className="button primary"
                        onClick={handleNext}
                    >
                        {isLast ? 'Finish' : 'Next →'}
                    </button>
                </div>
            </div>

            <style>{`
                @keyframes slideIn {
                    from { transform: translateY(20px); opacity: 0; }
                    to { transform: translateY(0); opacity: 1; }
                }
            `}</style>
        </div>
    );
};
