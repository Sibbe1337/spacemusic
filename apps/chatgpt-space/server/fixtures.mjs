// Fictional fixtures only. These are not derived from customer submissions.
const check = (id, label, status, finding, nextStep, sourceId) =>
  ({ id, label, status, finding, nextStep, sourceId });

export const cases = [
  {
    id: 'demo-harbor', name: 'Harbor Sessions', rights: 'Masters',
    description: '36 recordings / independent electronic catalog',
    offeredShare: '50% of the specified master rights; future releases excluded.',
    financialContext: 'Fictional statement: EUR 60,000 net to the owner, Oct 2025-Sep 2026. Full owned interest, not the offered 50%. Not a valuation.',
    nextStep: 'Resolve the ownership split and distribution consent.',
    finance: { currency: 'EUR', basis: 'net_to_owner', annual: 60000, period: '2025-10/2026-09', scope: 'full_owned_interest' },
    checks: [
      check('scope', 'Sale scope', 'provided', '36 existing recordings are listed; 50% is proposed.', 'Confirm the final schedule and the meaning of the 50% interest.', 'H-01'),
      check('authority', 'Seller authority', 'provided', 'A fictional authority declaration is supplied.', 'A reviewer must verify identity and authority independently.', 'H-02'),
      check('ownership', 'Ownership & splits', 'clarify', 'Two recordings have unresolved producer splits.', 'Obtain the signed split agreements for those recordings.', 'H-01'),
      check('income', 'Royalty history', 'provided', 'The fixture contains a complete 12-month net-income summary in EUR.', 'Reconcile statements and payouts before relying on any figures.', 'H-03'),
      check('agreements', 'Existing agreements', 'missing', 'Distribution terms and transfer consent are not supplied.', 'Provide the distribution agreement and applicable consent terms.', 'H-04'),
      check('metadata', 'Catalog metadata', 'provided', 'The fictional schedule lists recording identifiers and release dates.', 'Reconcile identifiers against the source statements.', 'H-01'),
    ],
    sources: [
      { id: 'H-01', label: 'Demo catalog schedule', note: 'Invented fixture; includes the unresolved split.' },
      { id: 'H-02', label: 'Demo seller declaration', note: 'Invented declaration, not identity or ownership verification.' },
      { id: 'H-03', label: 'Demo income summary', note: 'Invented EUR net-income figures for a defined 12-month period.' },
      { id: 'H-04', label: 'Demo intake checklist', note: 'Records that distribution documentation is missing.' },
    ],
  },
  {
    id: 'demo-juniper', name: 'Juniper Works', rights: 'Publishing',
    description: '18 compositions / songwriter catalog',
    offeredShare: 'Selected publishing interests only; no master rights offered.',
    financialContext: 'The fictional summary does not define currency, dates, or gross/net treatment. No annual income or financial comparison can be established.',
    nextStep: 'Request dated statements with currency and gross/net definitions.',
    finance: { currency: null, basis: null, annual: null, period: null, scope: null },
    checks: [
      check('scope', 'Sale scope', 'provided', '18 compositions are proposed; masters are excluded.', 'Define the exact publishing interests and territories.', 'J-01'),
      check('authority', 'Seller authority', 'missing', 'Authority documentation is absent.', 'Confirm the seller and their authority to offer these interests.', 'J-02'),
      check('ownership', 'Ownership & splits', 'clarify', 'Writer shares are listed but not supported by signed agreements.', 'Provide signed splits and confirm which share is transferable.', 'J-01'),
      check('income', 'Royalty history', 'clarify', 'Currency, statement periods and gross/net definitions are unknown.', 'Supply source statements; do not annualize or combine this summary.', 'J-03'),
      check('agreements', 'Existing agreements', 'missing', 'Publishing administration terms are not supplied.', 'Provide the administration agreement and any restrictions.', 'J-02'),
      check('metadata', 'Catalog metadata', 'provided', 'A fictional work list is supplied.', 'Reconcile work identifiers and writer names with registrations.', 'J-01'),
    ],
    sources: [
      { id: 'J-01', label: 'Demo composition schedule', note: 'Invented work list, not a rights registration.' },
      { id: 'J-02', label: 'Demo intake checklist', note: 'Records missing authority and administration documentation.' },
      { id: 'J-03', label: 'Incomplete demo income summary', note: 'Deliberately incomplete; unsuitable for financial conclusions.' },
    ],
  },
  {
    id: 'demo-northline', name: 'Northline Records', rights: 'Masters',
    description: '64 recordings / independent label catalog',
    offeredShare: '100% of the label-owned interests in the listed recordings.',
    financialContext: 'Fictional statement: USD 95,000 net to the label, Oct 2025-Sep 2026. No currency conversion or valuation has been performed.',
    nextStep: 'Complete human verification before seeking any sharing permission.',
    finance: { currency: 'USD', basis: 'net_to_owner', annual: 95000, period: '2025-10/2026-09', scope: 'full_owned_interest' },
    checks: [
      check('scope', 'Sale scope', 'provided', '64 recordings and the offered label-owned interests are listed.', 'A reviewer must confirm the sale scope.', 'N-01'),
      check('authority', 'Seller authority', 'provided', 'A fictional company authority declaration is included.', 'Verify the signatory and company authority independently.', 'N-02'),
      check('ownership', 'Ownership & splits', 'provided', 'Fictional artist agreements and splits are supplied.', 'Independently assess the rights chain and any retained interests.', 'N-02'),
      check('income', 'Royalty history', 'provided', 'A complete 12-month USD net-income summary is supplied in the fixture.', 'Reconcile statements and payouts; do not treat the summary as verified.', 'N-03'),
      check('agreements', 'Existing agreements', 'provided', 'Fictional distribution terms are included.', 'Review transfer restrictions and outstanding obligations.', 'N-02'),
      check('metadata', 'Catalog metadata', 'provided', 'Recording identifiers and release dates are included.', 'Reconcile the catalog schedule against agreements and statements.', 'N-01'),
    ],
    sources: [
      { id: 'N-01', label: 'Demo recording schedule', note: 'Invented metadata for this demo only.' },
      { id: 'N-02', label: 'Demo agreement checklist', note: 'Invented document status; no legal determination.' },
      { id: 'N-03', label: 'Demo royalty summary', note: 'Invented USD figures for a defined 12-month period.' },
    ],
  },
];

export const buyerProfiles = [
  { id: 'profile-a', name: 'Profile A / master-rights buyer', rights: 'Masters', currency: 'EUR', minimum: 50000,
    criteria: 'Fictional criterion: masters; EUR 50,000 annual net income from the full owned interest.', sourceId: 'DEMO-A' },
  { id: 'profile-b', name: 'Profile B / publishing buyer', rights: 'Publishing', currency: 'EUR', minimum: 25000,
    criteria: 'Fictional criterion: publishing; EUR 25,000 annual net income from the full owned interest.', sourceId: 'DEMO-B' },
  { id: 'profile-c', name: 'Profile C / label-catalog buyer', rights: 'Masters', currency: 'USD', minimum: 75000,
    criteria: 'Fictional criterion: masters; USD 75,000 annual net income from the full owned interest.', sourceId: 'DEMO-C' },
];
