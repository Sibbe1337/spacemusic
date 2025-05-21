import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { BrowserRouter as Router } from 'react-router-dom';
import { Auth0Context, User } from '@auth0/auth0-react';
import { vi, describe, it, expect } from 'vitest';

import DealsPage from './DealsPage';
// import { server } from '../mocks/server'; // MSW server, already handled by setupTests.ts

// Mock Auth0 context provider values
const mockAuth0ContextValue = {
  isAuthenticated: true,
  user: { 
    name: 'Test User', 
    email: 'test@example.com', 
    picture: 'https://example.com/avatar.jpg' 
    // Add other user properties if your app uses them
  } as User,
  isLoading: false,
  getAccessTokenSilently: vi.fn().mockResolvedValue('mocked-access-token'),
  loginWithRedirect: vi.fn(),
  logout: vi.fn(),
  loginWithPopup: vi.fn(),
  getAccessTokenWithPopup: vi.fn(),
  getIdTokenClaims: vi.fn(),
  handleRedirectCallback: vi.fn(),
  buildAuthorizeUrl: vi.fn(),
  buildLogoutUrl: vi.fn(),
  isAuthenticatedPromise: Promise.resolve(true),
};

// Helper to render with necessary providers
const renderDealsPage = () => {
  return render(
    <Router> {/* DealsPage might contain Link components or routing logic indirectly */}
      <Auth0Context.Provider value={mockAuth0ContextValue as any}> {/* Cast as any to simplify mock type */}
        <DealsPage />
      </Auth0Context.Provider>
    </Router>
  );
};

describe('DealsPage', () => {
  it('renders loading state initially', () => {
    // Temporarily override getAccessTokenSilently for this specific test if needed
    // to ensure loading state can be tested before data arrives.
    // Here, we assume MSW responds fast enough or we test the loaded state primarily.
    renderDealsPage();
    // The component itself has an internal isLoading, then shows "Loading deals..."
    // If Auth0 isLoading is true, App.tsx shows "Loading authentication state..."
    // We are testing DealsPage specific loading here.
    expect(screen.getByText(/loading deals.../i)).toBeInTheDocument();
  });

  it('fetches and displays deals in a table', async () => {
    renderDealsPage();

    // Wait for the table to appear with data from MSW mock
    // (mockDeals in handlers.ts has 3 deals)
    await waitFor(() => {
      expect(screen.getByText('deal-1'.substring(0,8) + '...')).toBeInTheDocument();
      expect(screen.getByText('test1@example.com')).toBeInTheDocument();
      expect(screen.getByText('1200.50')).toBeInTheDocument(); // price_eur from mock
    });

    expect(screen.getByText('deal-2'.substring(0,8) + '...')).toBeInTheDocument();
    expect(screen.getByText('deal-3'.substring(0,8) + '...')).toBeInTheDocument();
    expect(screen.getByText(/A list of recent deals./i)).toBeInTheDocument(); // TableCaption
  });

  it('opens DealDetailsDrawer on row click and shows details', async () => {
    renderDealsPage();
    await waitFor(() => {
      expect(screen.getByText('deal-1'.substring(0,8) + '...')).toBeInTheDocument();
    });

    // Click on the first deal row (containing 'deal-1')
    const firstDealRow = screen.getByText('deal-1'.substring(0,8) + '...').closest('tr');
    expect(firstDealRow).toBeInTheDocument();
    if (firstDealRow) {
        await userEvent.click(firstDealRow);
    }

    // Wait for Drawer to open and show details (content from mockDeals[0])
    await waitFor(() => {
      expect(screen.getByText(/Deal Details: deal-1/i)).toBeInTheDocument();
      expect(screen.getByText("Email:", { exact: false })).toHaveTextContent("test1@example.com");
      expect(screen.getByText("Price:", { exact: false })).toHaveTextContent("1200.50 EUR");
      expect(screen.getByText("Termsheet:", { exact: false })).toBeInTheDocument(); // pdf_url was '#'
    });
  });

  it('calls retry payout API when Retry Payout button in drawer is clicked', async () => {
    renderDealsPage();
    await waitFor(() => {
      expect(screen.getByText('deal-1'.substring(0,8) + '...')).toBeInTheDocument();
    });

    const firstDealRow = screen.getByText('deal-1'.substring(0,8) + '...').closest('tr');
    if (firstDealRow) await userEvent.click(firstDealRow);

    await waitFor(() => {
      expect(screen.getByText(/Deal Details: deal-1/i)).toBeInTheDocument();
    });

    // Mock axios.post for this specific test, as MSW will handle the actual HTTP call during test
    // but we want to assert our component calls it correctly.
    // The MSW handler for this is already in src/mocks/handlers.ts.
    // We just need to ensure our UI calls it.
    const retryButton = screen.getByRole('button', { name: /retry payout/i });
    await userEvent.click(retryButton);

    // Check for toast message (from sonner via MSW response)
    // This requires sonner's Toaster to be rendered, which it is in App.tsx
    // Exact message comes from our MSW handler for retry_payout
    await waitFor(() => {
        expect(screen.getByText(/Payout retry initiated successfully for mock offer deal-1/i)).toBeInTheDocument();
    });
  });

}); 