/**
 * Integration Gate I.1 — Enhanced Global Error Boundary
 * 
 * Replaces basic ErrorBoundary in main.tsx with governance-aware version.
 */

import React from 'react';
import { CrashScreen } from '../components/bootstrap/BootstrapScreens';

interface Props {
    children: React.ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: React.ErrorInfo | null;
}

export class EnhancedErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('[EnhancedErrorBoundary] Uncaught error:', error, errorInfo);
        this.setState({ errorInfo });

        // Optional: Send to error tracking service
        // sendErrorToService({ error, errorInfo, timestamp: Date.now() });
    }

    reset = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
        window.location.href = '/'; // Full reload to clean state
    };

    render() {
        if (this.state.hasError && this.state.error) {
            return (
                <CrashScreen
                    error={this.state.error}
                    errorInfo={this.state.errorInfo || undefined}
                    reset={this.reset}
                />
            );
        }

        return this.props.children;
    }
}
