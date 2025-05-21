import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { Button } from '@/components/ui/button';
import { Toaster } from "@/components/ui/sonner"; // For toasts

import LoginButton from '@/components/auth/LoginButton';
import LogoutButton from '@/components/auth/LogoutButton';
import { ProtectedRoute } from '@/components/auth/AuthGuard'; 

// Import actual Page components
import DealsPage from '@/pages/DealsPage';
import RiskPage from '@/pages/RiskPage';
import CashPage from '@/pages/CashPage';
import SlaPage from '@/pages/SlaPage';

// Placeholder Pages (to be created next) - REMOVE THESE NOW
// const DealsPage = () => <div>Deals Page (Protected) <Profile /></div>;
// const RiskPage = () => <div>Risk Page (Protected)</div>;
// const CashPage = () => <div>Cash Page (Protected)</div>;
// const SlaPage = () => <div>SLA Page (Protected)</div>;

const HomePage = () => {
  const { isAuthenticated, isLoading } = useAuth0();
  if (isLoading) return <div>Loading...</div>;
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Admin Dashboard</h1>
      {!isAuthenticated && <p>Please log in to access the dashboard features.</p>}
      {isAuthenticated && <p>Welcome! Select a section from the navbar.</p>}
    </div>
  );
};

function App() {
  const { isAuthenticated, isLoading } = useAuth0();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div>Loading authentication state...</div>
      </div>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-background text-foreground">
        <header className="border-b">
          <div className="container mx-auto flex h-16 items-center justify-between px-4">
            <Link to="/" className="text-lg font-semibold">
              SPACE Admin
            </Link>
            <nav className="flex items-center space-x-4">
              {isAuthenticated && (
                <>
                  <Link to="/deals"><Button variant="ghost">Deals</Button></Link>
                  <Link to="/risk"><Button variant="ghost">Risk</Button></Link>
                  <Link to="/cash"><Button variant="ghost">Cash</Button></Link>
                  <Link to="/sla"><Button variant="ghost">SLA</Button></Link>
                  <LogoutButton />
                </>
              )}
              {!isAuthenticated && <LoginButton />}
            </nav>
          </div>
        </header>

        <main className="container mx-auto p-4">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/deals" element={<ProtectedRoute><DealsPage /></ProtectedRoute>} />
            <Route path="/risk" element={<ProtectedRoute><RiskPage /></ProtectedRoute>} />
            <Route path="/cash" element={<ProtectedRoute><CashPage /></ProtectedRoute>} />
            <Route path="/sla" element={<ProtectedRoute><SlaPage /></ProtectedRoute>} />
            {/* Redirect to home if no other route matches and authenticated, or show login prompt */}
            <Route path="*" element={isAuthenticated ? <Navigate to="/" /> : <div className="p-4">Please log in.</div>} />
          </Routes>
        </main>
        <Toaster />
      </div>
    </Router>
  );
}

export default App;
