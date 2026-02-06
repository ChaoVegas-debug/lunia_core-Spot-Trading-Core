import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

interface Props {
  allowed: Array<'USER' | 'TRADER' | 'FUND' | 'ADMIN'>;
  children: React.ReactElement;
}

/**
 * I.2: ProtectedRoute now integrated with auth controller.
 * Auth state is checked at BootstrapShell level, so if we reach here, auth is READY.
 * This component just checks role matching.
 */
export const ProtectedRoute: React.FC<Props> = ({ allowed, children }) => {
  const { role } = useAuth();

  // If role not in allowed list, redirect to login
  if (!allowed.includes(role)) {
    return <Navigate to="/login" replace />;
  }

  return children;
};
