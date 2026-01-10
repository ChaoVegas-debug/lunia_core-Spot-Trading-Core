import React from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import { PreviewModeProvider } from './context/PreviewModeContext';
import { AppLayout } from './components/layout/AppLayout';
import { GuidedOnboardingTour } from './components/widgets/GuidedOnboardingTour';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { RequireOnboarding } from './components/layout/RequireOnboarding';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { UserPanel } from './pages/UserPanel';
import { TraderPanel } from './pages/TraderPanel';
import { FundPanel } from './pages/FundPanel';
import { AdminPanel } from './pages/AdminPanel';
import { AdminPage } from './pages/AdminPage';
import { SystemPage } from './pages/SystemPage';
import { DocsPage } from './pages/DocsPage';
import { PortfolioPage } from './pages/PortfolioPage';
import { RiskPage } from './pages/RiskPage';
import { StrategiesPage } from './pages/StrategiesPage';
import { AccountPage } from './pages/AccountPage';
import { SubscriptionPage } from './pages/SubscriptionPage';
import { ExchangeKeysPage } from './pages/ExchangeKeysPage';
import { GettingStartedPage } from './pages/GettingStartedPage';
import { SurfaceInspectorPage } from './pages/SurfaceInspectorPage';

import { AdminLayout } from './pages/admin/AdminLayout';
import { AdminDashboard } from './pages/admin/AdminDashboard';
import { AdminUsersPage } from './pages/admin/AdminUsersPage';
import { AdminAuditPage } from './pages/admin/AdminAuditPage';
import { AdminFlagsPage } from './pages/admin/AdminFlagsPage';
import { AdminTenantsPage } from './pages/admin/AdminTenantsPage';
import { AdminExchangesPage } from './pages/admin/AdminExchangesPage';
import { AdminIncidentsPage } from './pages/admin/AdminIncidentsPage';

import { OnboardingPage } from './pages/OnboardingPage';
import { WhyProvider } from './contexts/WhyContext';

const App: React.FC = () => {
  console.log('App Rendering');
  const location = useLocation();
  const navigate = useNavigate();
  const tourActive = (location.state as any)?.tourActive;

  return (
    <PreviewModeProvider>
      <AuthProvider>
        <WhyProvider>
          <Routes>
            <Route
              path="/login"
              element={<LoginPage />}
            />
            <Route
              path="/register"
              element={<RegisterPage />}
            />
            <Route
              path="/"
              element={<LandingPage />}
            />

            <Route element={<AppLayout />}>
              {/* /user -> /account alias */}
              <Route path="/user" element={<Navigate to="/account" replace />} />

              {/* ACCOUNT: Accessible without Onboarding (for settings) */}
              <Route
                path="/account"
                element={
                  <ProtectedRoute allowed={['USER', 'TRADER', 'FUND', 'ADMIN']}>
                    <AccountPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/account/subscription"
                element={
                  <ProtectedRoute allowed={['USER', 'TRADER', 'FUND', 'ADMIN']}>
                    <SubscriptionPage />
                  </ProtectedRoute>
                }
              />

              {/* TRADER PANEL: GATED */}
              <Route
                path="/trader"
                element={
                  <ProtectedRoute allowed={['TRADER', 'ADMIN']}>
                    {/* <RequireOnboarding> */}
                    <TraderPanel />
                    {/* </RequireOnboarding> */}
                  </ProtectedRoute>
                }
              />

              {/* PORTFOLIO: GATED */}
              <Route
                path="/portfolio"
                element={
                  <ProtectedRoute allowed={['TRADER', 'ADMIN']}>
                    <RequireOnboarding>
                      <PortfolioPage />
                    </RequireOnboarding>
                  </ProtectedRoute>
                }
              />

              {/* RISK: GATED */}
              <Route
                path="/risk"
                element={
                  <ProtectedRoute allowed={['TRADER', 'ADMIN']}>
                    <RequireOnboarding>
                      <RiskPage />
                    </RequireOnboarding>
                  </ProtectedRoute>
                }
              />

              {/* STRATEGIES: GATED */}
              <Route
                path="/strategies"
                element={
                  <ProtectedRoute allowed={['TRADER', 'ADMIN']}>
                    <RequireOnboarding>
                      <StrategiesPage />
                    </RequireOnboarding>
                  </ProtectedRoute>
                }
              />

              {/* EXCHANGE KEYS: GATED */}
              <Route
                path="/exchange-keys"
                element={
                  <ProtectedRoute allowed={['TRADER', 'ADMIN']}>
                    <RequireOnboarding>
                      <ExchangeKeysPage />
                    </RequireOnboarding>
                  </ProtectedRoute>
                }
              />

              {/* FUND PANEL */}
              <Route
                path="/fund"
                element={
                  <ProtectedRoute allowed={['FUND', 'ADMIN']}>
                    <FundPanel />
                  </ProtectedRoute>
                }
              />

              <Route
                path="/system"
                element={
                  <ProtectedRoute allowed={['USER', 'TRADER', 'FUND', 'ADMIN']}>
                    <SystemPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/docs"
                element={
                  <ProtectedRoute allowed={['USER', 'TRADER', 'FUND', 'ADMIN']}>
                    <DocsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/getting-started"
                element={
                  <ProtectedRoute allowed={['USER', 'TRADER', 'FUND', 'ADMIN']}>
                    <GettingStartedPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/preview/surfaces"
                element={
                  <SurfaceInspectorPage />
                }
              />

              {/* ADMIN ROUTES */}
              <Route
                path="/admin"
                element={
                  <ProtectedRoute allowed={['ADMIN']}>
                    <AdminPage />
                  </ProtectedRoute>
                }
              />
            </Route>

            <Route path="*" element={<h1>404 NOT FOUND</h1>} />
          </Routes>
        </WhyProvider>
      </AuthProvider>
    </PreviewModeProvider>
  );
};

export default App;
