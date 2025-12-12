import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { UserPanel } from './pages/UserPanel';
import { TraderPanel } from './pages/TraderPanel';
import { FundPanel } from './pages/FundPanel';
import { AdminPanel } from './pages/AdminPanel';
import { SystemPage } from './pages/SystemPage';
import { DocsPage } from './pages/DocsPage';

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/user" replace />} />
        <Route
          path="/user"
          element={
            <ProtectedRoute allowed={['USER', 'TRADER', 'FUND', 'ADMIN']}>
              <UserPanel />
            </ProtectedRoute>
          }
        />
        <Route
          path="/trader"
          element={
            <ProtectedRoute allowed={['TRADER', 'ADMIN']}>
              <TraderPanel />
            </ProtectedRoute>
          }
        />
        <Route
          path="/fund"
          element={
            <ProtectedRoute allowed={['FUND', 'ADMIN']}>
              <FundPanel />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowed={['ADMIN']}>
              <AdminPanel />
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
      </Route>
      <Route path="*" element={<Navigate to="/user" replace />} />
    </Routes>
  );
};

export default App;
