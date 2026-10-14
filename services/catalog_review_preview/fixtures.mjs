// Fictional design fixtures. This is not Too Lost's response schema.
export const CONTRACT_VERSION = 'space-review-design-fixture-v1';
export const ACCOUNT = Object.freeze({ id: 'demo-account', name: 'Northline Records', email: 'alex@example.com' });
export const RELEASES = Object.freeze([
  { id: 'demo-release-1', title: 'Open Water', artist: 'Mara Field', kind: 'EP', tracks: 4, date: '2025-04-18', genre: 'Electronic' },
  { id: 'demo-release-2', title: 'Side Streets', artist: 'Sunday Assembly', kind: 'Single', tracks: 1, date: '2025-08-22', genre: 'Indie pop' },
  { id: 'demo-release-3', title: 'After Hours', artist: 'Northline Sessions', kind: 'Single', tracks: 1, date: '2026-02-13', genre: 'Hip-hop' },
]);
export const MONTHS = Object.freeze([
  { period: '2025-09', amount: '1024.20' }, { period: '2025-10', amount: '980.50' },
  { period: '2025-11', amount: '1105.30' }, { period: '2025-12', amount: '1240.00' },
  { period: '2026-01', amount: '920.00' }, { period: '2026-02', amount: '-24.50' },
  { period: '2026-03', amount: '1130.00' }, { period: '2026-04', amount: '1184.50' },
]);
export const DOCUMENTS = Object.freeze([
  { id: 'statement', name: 'royalty-statement-sample.csv', category: 'Royalty statement', description: 'Synthetic account statement, September 2025 to April 2026.' },
  { id: 'rights', name: 'rights-summary-sample.pdf', category: 'Rights summary', description: 'Fictional ownership notes for the three demo releases.' },
]);
export const SCENARIOS = Object.freeze({
  standard: 'Standard journey', 'wrong-account': 'Different provider account',
  cancelled: 'Permission declined', expired: 'Expired session', empty: 'Empty catalog',
  partial: 'Interrupted import', 'missing-documents': 'Missing documents',
  'save-error': 'Save failure', 'submission-error': 'Submission failure',
  'unknown-currency': 'Currency not confirmed',
});
export const REPLIES = Object.freeze({
  partial: 'The sample only includes statements through April. I will request the remaining months from my distributor.',
  available: 'The remaining sample statements are not available yet. Please review the supplied period and note the limitation.',
});

export function decimalToMinor(value) {
  if (typeof value !== 'string' || !/^-?\d{1,12}\.\d{2}$/.test(value)) throw new Error('Invalid fixed-precision amount');
  const negative = value.startsWith('-');
  const [whole, fraction] = value.replace('-', '').split('.');
  const minor = BigInt(whole) * 100n + BigInt(fraction);
  return negative ? -minor : minor;
}

export function summarizeMonths(rows, currency) {
  const periods = new Set();
  let total = 0n;
  for (const row of rows) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(row.period) || periods.has(row.period)) throw new Error('Invalid or duplicate reporting period');
    periods.add(row.period);
    total += decimalToMinor(row.amount);
  }
  // A known currency is declared only in synthetic fixtures, never inferred from the API.
  return { count: rows.length, currency, totalMinor: rows.length && currency === 'EUR' ? total.toString() : null };
}
