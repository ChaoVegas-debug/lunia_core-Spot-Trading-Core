import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

export interface TourStep {
    id: string; // e.g. 'connect-keys', 'set-mode'
    title: string;
    description: string;
    targetRoute: string; // Where this step happens
    nextLabel?: string;
    nextRoute?: string; // Where to go next
    prevRoute?: string; // Where to go back
    totalSteps: number;
    currentStep: number;
}

// Define the Canonical Flow Steps
export const TOUR_STEPS: Record<string, TourStep> = {
    'connect-keys': {
        id: 'connect-keys',
        title: 'Step 1: Connect Exchange',
        description: 'You need at least one active exchange connection to deploy portfolios.',
        targetRoute: '/exchange-keys',
        nextLabel: 'Next: System Mode',
        nextRoute: '/system',
        currentStep: 1,
        totalSteps: 7
    },
    'system-mode': {
        id: 'system-mode',
        title: 'Step 2: System Governance',
        description: 'Set the execution mode (SEMI recommended) and Global Capital Cap.',
        targetRoute: '/system',
        nextLabel: 'Next: Risk Limits',
        nextRoute: '/risk',
        prevRoute: '/exchange-keys',
        currentStep: 2,
        totalSteps: 7
    },
    'risk-limits': {
        id: 'risk-limits',
        title: 'Step 3: Risk Guardrails',
        description: 'Select a Risk Preset (e.g. SHIELD) to define hard limits.',
        targetRoute: '/risk',
        nextLabel: 'Next: Strategies',
        nextRoute: '/strategies',
        prevRoute: '/system',
        currentStep: 3,
        totalSteps: 7
    },
    'strategies': {
        id: 'strategies',
        title: 'Step 4: Strategy Profile',
        description: 'Configure your algorithmic mix and verify weights.',
        targetRoute: '/strategies',
        nextLabel: 'Next: Create Portfolio',
        nextRoute: '/portfolio',
        prevRoute: '/risk',
        currentStep: 4,
        totalSteps: 7
    },
    'portfolio-wizard': {
        id: 'portfolio-wizard',
        title: 'Step 5: Create Portfolio',
        description: 'Use the Wizard to specificy assets, analyze with AI, and DEPLOY.',
        targetRoute: '/portfolio',
        nextLabel: 'Next: Dashboard',
        nextRoute: '/trader',
        prevRoute: '/strategies',
        currentStep: 5,
        totalSteps: 7
    },
    'dashboard-intro': {
        id: 'dashboard-intro',
        title: 'Step 6: Trader Cockpit',
        description: 'Monitor your portfolio, AI signals, and system feed here.',
        targetRoute: '/trader',
        nextLabel: 'Next: Verify Logs',
        nextRoute: '/trader',
        prevRoute: '/portfolio',
        currentStep: 6,
        totalSteps: 7
    },
    // We can add logs or wrap up
    'finish': {
        id: 'finish',
        title: 'Step 7: Verification',
        description: 'Check logs to verify your actions are recorded.',
        targetRoute: '/trader', // Or logs widget
        prevRoute: '/trader',
        currentStep: 7,
        totalSteps: 7
    }
};

export const TourHelper: React.FC = () => {
    const location = useLocation();
    const navigate = useNavigate();

    // Check if we are in "Tour Mode" via location state
    // We expect state: { tourActive: true, stepId: string }
    const tourState = location.state as { tourActive?: boolean; stepId?: string } | null;

    if (!tourState?.tourActive || !tourState?.stepId) return null;

    const step = TOUR_STEPS[tourState.stepId];
    if (!step) return null;

    // Simple overlay banner at the bottom
    return (
        <div style={{
            position: 'fixed',
            bottom: '24px',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: '#1e293b',
            border: '1px solid var(--accent-primary)',
            borderRadius: '8px',
            padding: '16px',
            zIndex: 9999,
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
            width: '90%',
            maxWidth: '600px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
        }}>
            <div style={{ flex: 1, marginRight: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{
                        backgroundColor: 'var(--accent-primary)',
                        color: 'white',
                        fontSize: '0.75rem',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        marginRight: '8px',
                        fontWeight: 'bold'
                    }}>
                        STEP {step.currentStep}/{step.totalSteps}
                    </span>
                    <strong style={{ fontSize: '1rem', color: 'white' }}>{step.title}</strong>
                </div>
                <p style={{ margin: 0, fontSize: '0.9rem', color: '#cbd5e1' }}>
                    {step.description}
                </p>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
                <button
                    id="tour-exit-btn"
                    className="button small secondary"
                    onClick={() => navigate('/getting-started')}
                >
                    Exit
                </button>
                {step.prevRoute && (
                    <button
                        id="tour-back-btn"
                        className="button small secondary"
                        onClick={() => navigate(step.prevRoute!, { state: { tourActive: true, stepId: Object.keys(TOUR_STEPS).find(k => TOUR_STEPS[k].targetRoute === step.prevRoute)?.toString() } })} // Simple hack, ideally find prev step ID
                    >
                        &larr; Back
                    </button>
                )}
                {step.nextRoute && (
                    <button
                        id="tour-next-btn"
                        className="button small primary"
                        onClick={() => {
                            const nextStepEntry = Object.entries(TOUR_STEPS).find(([_, s]) => s.targetRoute === step.nextRoute);
                            if (nextStepEntry && step.nextRoute) {
                                navigate(step.nextRoute, { state: { tourActive: true, stepId: nextStepEntry[0] } });
                            } else if (step.nextRoute) {
                                navigate(step.nextRoute);
                            }
                        }}
                    >
                        {step.nextLabel || 'Next'} &rarr;
                    </button>
                )}
            </div>
        </div>
    );
};
