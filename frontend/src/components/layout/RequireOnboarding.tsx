import React from 'react';
import { useOnboarding } from '../../hooks/useOnboarding';
import { usePreview } from '../../context/PreviewModeContext';

export const RequireOnboarding: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isCompleted } = useOnboarding();
    const { isPreview } = usePreview();

    // No loading state exposed by hook currently, assuming it hydrates fast or defaulting to block safely.

    if (!isCompleted) {
        if (isPreview) {
            return (
                <>
                    <div className="alert warning" style={{ margin: 0, borderRadius: 0, textAlign: 'center' }}>
                        <strong>PREVIEW MODE:</strong> Onboarding Guard Bypassed for Demo
                    </div>
                    {children}
                </>
            );
        }

        return (
            <div className="flex-center flex-column p-8 gap-4 mt-8" style={{ height: '60vh' }}>
                <h2>Pending Onboarding</h2>
                <p className="text-muted max-w-md text-center">
                    Your institutional setup is not complete. Please complete the setup wizard to access the Trader Cockpit.
                </p>
                <a href="/onboarding" className="button primary">CONTINUE SETUP</a>
            </div>
        );
    }

    return <>{children}</>;
};
