import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';
import './cockpit.css';
import { AuthProvider } from './hooks/useAuth';
import { EnhancedErrorBoundary } from './lib/EnhancedErrorBoundary';
import { BootstrapShell } from './components/bootstrap/BootstrapShell';

console.log('Mounting App Root');
(window as any).mainExecuted = true;

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <EnhancedErrorBoundary>
            <BootstrapShell>
                <BrowserRouter>
                    <AuthProvider>
                        <App />
                    </AuthProvider>
                </BrowserRouter>
            </BootstrapShell>
        </EnhancedErrorBoundary>
    </React.StrictMode>
);
