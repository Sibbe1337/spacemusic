import { cases, buyerProfiles } from './fixtures.mjs';
import { caseIdSchema, snapshotSchema } from '../shared/contract.mjs';

function summary(item) {
  const { id, name, rights, description, nextStep } = item;
  return { id, name, rights, description, nextStep,
    provided: item.checks.filter(check => check.status === 'provided').length, total: 6 };
}

export function compareProfile(item, profile) {
  const result = { id: profile.id, name: profile.name, criteria: profile.criteria,
    sourceId: profile.sourceId, status: 'blocked', reasons: [] };
  if (item.rights !== profile.rights) {
    return { ...result, status: 'outside_scope', reasons: ['The offered rights do not match this fictional profile.'] };
  }
  const f = item.finance;
  if (!f.currency || f.basis !== 'net_to_owner' || !Number.isFinite(f.annual) || f.annual < 0 ||
      f.period !== '2025-10/2026-09' || f.scope !== 'full_owned_interest') {
    result.reasons.push('Financial comparison blocked: a defined 12-month period, currency, net-income basis and income scope are required.');
  } else if (f.currency !== profile.currency) {
    result.reasons.push('Currency differs from the profile. No exchange rate or conversion is assumed.');
  } else if (f.annual < profile.minimum) {
    result.reasons.push('The fictional annual net income is below this fictional profile criterion.');
  }
  for (const check of item.checks.filter(check => check.status !== 'provided')) {
    result.reasons.push(`${check.label}: ${check.nextStep}`);
  }
  if (!result.reasons.length) {
    result.status = 'potential';
    result.reasons.push('The declared fixture matches these limited criteria. This is not a verified buyer match or an offer.');
  }
  result.reasons.push('Human verification and seller permission for the specific recipient and materials are still required. Sharing is disabled.');
  return result;
}

export function snapshot(view = 'overview', caseId) {
  const item = view === 'overview' ? null : cases.find(entry => entry.id === caseIdSchema.parse(caseId));
  if (!['overview', 'review', 'buyers'].includes(view)) throw new Error('Unknown view');
  return snapshotSchema.parse({
    schemaVersion: 1, dataMode: 'synthetic', asOf: '2026-10-03', view, sharingEnabled: false,
    notice: 'Fictional catalogs, documents and buyer profiles. No real review, valuation, buyer outreach or data sharing.',
    cases: cases.map(summary),
    selected: item ? { ...summary(item), offeredShare: item.offeredShare,
      financialContext: item.financialContext, checks: item.checks, sources: item.sources } : null,
    matches: view === 'buyers' ? buyerProfiles.map(profile => compareProfile(item, profile)) : [],
  });
}

export function toolResult(data) {
  const result = snapshotSchema.parse(data);
  const lines = [result.notice];
  if (result.selected) {
    const item = result.selected;
    lines.push(`${item.name} (${item.id}): ${item.provided}/6 document categories supplied in the fixture; not verified.`,
      item.offeredShare, item.financialContext, `Next: ${item.nextStep}`);
    if (result.view === 'review') {
      lines.push(...item.checks.map(check => `${check.label} [${check.status}; ${check.sourceId}]: ${check.finding} Next: ${check.nextStep}`));
    } else {
      lines.push(...result.matches.map(match => `${match.name} [${match.status}; ${match.sourceId}]: ${match.reasons.join(' ')}`));
    }
  } else {
    lines.push(...result.cases.map(item => `${item.name} (${item.id}), ${item.rights}: ${item.nextStep}`));
  }
  return { content: [{ type: 'text', text: lines.join('\n') }], structuredContent: result };
}
