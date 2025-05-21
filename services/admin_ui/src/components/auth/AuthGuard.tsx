import { useAuth0 } from '@auth0/auth0-react';
import { Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';

export const ProtectedRoute = ({ children }: { children: ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth0();
  if (isLoading) return <div className="flex items-center justify-center h-screen">Loading auth…</div>; // Added some basic centering
  return isAuthenticated ? <>{children}</> : <Navigate to="/" />;
}; 