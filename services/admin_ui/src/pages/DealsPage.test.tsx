import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { BrowserRouter as Router } from 'react-router-dom';
import { Auth0Context, User, type Auth0ContextInterface, type IdToken } from '@auth0/auth0-react';
import { vi, describe, it, expect } from 'vitest';

import DealsPage from './DealsPage';
// import { server } from '../mocks/server'; // MSW server, already handled by setupTests.ts

const mockAuth0ContextValue = {
  // Properties confirmed or very likely to be in Auth0ContextInterface
  isAuthenticated: true,
  user: { 
    name: 'Test User', 
    email: 'test@example.com', 
    picture: 'https://example.com/avatar.jpg' 
  } as User,
  isLoading: false,
  error: undefined, // Assuming error is an optional property, common in context APIs

  // Mocked functions - ensuring their signatures are at least compatible approximations
  getAccessTokenSilently: vi.fn().mockResolvedValue('mocked-access-token'),
  loginWithRedirect: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn().mockResolvedValue(undefined),
  loginWithPopup: vi.fn().mockResolvedValue(undefined),
  getAccessTokenWithPopup: vi.fn().mockResolvedValue(undefined as string | undefined),
  getIdTokenClaims: vi.fn().mockResolvedValue(undefined as IdToken | undefined),
  handleRedirectCallback: vi.fn().mockResolvedValue(undefined as unknown), // Use unknown for unspecified Promise results

  // Functions like buildAuthorizeUrl, buildLogoutUrl might not be direct members or are part of options objects.
  // Omitting them unless TypeScript explicitly demands them as non-optional.
  // If the type Auth0ContextInterface demands more non-optional properties, they need to be added.
  // For example, if `getIdentityClaims` was non-optional and different from `getIdTokenClaims`:
  // getIdentityClaims: vi.fn(), 

  // Adding properties based on the linter error
  buildAuthorizeUrl: vi.fn().mockResolvedValue('http://authorize.url'), // Added back
  buildLogoutUrl: vi.fn().mockReturnValue('http://logout.url'), // Added back
  getAccessTokenSilentlyVerbose: vi.fn().mockResolvedValue({ accessToken: 'mock_token_verbose', id_token: 'mock_id_token', scope: 'openid profile', expires_in: 3600 }), // Placeholder for GetTokenSilentlyVerboseResponse
  getAccessTokenWithPopupVerbose: vi.fn().mockResolvedValue({ accessToken: 'mock_token_verbose_popup', id_token: 'mock_id_token_popup', scope: 'openid profile', expires_in: 3600 }), // Placeholder
  handleRedirectCallbackVerbose: vi.fn().mockResolvedValue({ appState: { targetUrl: '/' } }), // Placeholder for RedirectLoginResult

  // Guessing the "and 2 more" might be related to checkSession or similar
  checkSession: vi.fn().mockResolvedValue(undefined), // Common Auth0 function
  // isAuthenticatedPromise: Promise.resolve(true), // This was in your original mock, let's see if it's one of them or if `isAuthenticated` is enough
  // One more missing? The linter will tell us if these are not the correct "2 more".
  // The error message from the linter is the source of truth for missing non-optional properties.

} as Auth0ContextInterface<User>; // Single cast of the whole object at the end.

// Helper to render with necessary providers
const renderDealsPage = () => {
  return render(
    <Router> {/* DealsPage might contain Link components or routing logic indirectly */}
      <Auth0Context.Provider value={mockAuth0ContextValue}>
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