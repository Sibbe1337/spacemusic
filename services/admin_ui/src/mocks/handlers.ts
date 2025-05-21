import { http, HttpResponse } from 'msw';

const mockDeals = [
  { id: 'deal-1', email: 'test1@example.com', price_eur: 1200.50, status: 'OFFER_READY', created_at: new Date().toISOString(), pdf_url: '#' },
  { id: 'deal-2', email: 'test2@example.com', price_eur: 850.00, status: 'PAID_OUT', created_at: new Date(Date.now() - 86400000).toISOString() }, // Yesterday
  { id: 'deal-3', email: 'test3@example.com', price_eur: 2500.75, status: 'PENDING_VALUATION', created_at: new Date(Date.now() - 172800000).toISOString() }, // Two days ago
];

export const handlers = [
  // Mock for fetching deals
  http.get('/internal/deals', ({ request }) => {
    const url = new URL(request.url);
    const limit = parseInt(url.searchParams.get('limit') || '10');
    return HttpResponse.json({ deals: mockDeals.slice(0, limit) });
  }),

  // Mock for retrying payout
  http.post('/internal/payouts/offers/:offerId/retry_payout', ({ params }) => {
    console.log(`MSW: Mocked retry payout for offer ID: ${params.offerId}`);
    // Simulate a successful response
    return HttpResponse.json(
        { message: `Payout retry initiated successfully for mock offer ${params.offerId}.` }, 
        { status: 202 } // Accepted
    );
  }),
  
  // Add other handlers as needed, e.g., for Auth0 token endpoint if testing that flow deeply
  // http.post('https://your-auth0-domain.auth0.com/oauth/token', () => {
  //   return HttpResponse.json({
  //     access_token: 'mocked-access-token',
  //     id_token: 'mocked-id-token',
  //     scope: 'openid profile email',
  //     expires_in: 86400,
  //     token_type: 'Bearer',
  //   });
  // }),
]; 