import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

interface Props {
  allowed: Array<'USER' | 'TRADER' | 'FUND' | 'ADMIN'>;
  children: React.ReactElement;
}

export const ProtectedRoute: React.FC<Props> = ({ allowed, children }) => {
  const { role } = useAuth();
  if (!allowed.includes(role)) {
    return <Navigate to="/login" replace />;
  }
  return children;
};
