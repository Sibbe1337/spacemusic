import { RELEASES, DOCUMENTS, SCENARIOS, REPLIES } from './fixtures.mjs';

export const STEPS = ['invitation', 'source', 'permissions', 'provider', 'account', 'import', 'coverage', 'selection', 'rights', 'documents', 'summary', 'status', 'settings', 'expired'];
const ids = RELEASES.map(release => release.id);
const copy = value => JSON.parse(JSON.stringify(value));
const fail = message => { throw new Error(message); };
const requireThat = (condition, message) => { if (!condition) fail(message); };

export function initialState(scenario = 'standard') {
  requireThat(Object.hasOwn(SCENARIOS, scenario), 'Unknown preview scenario');
  return {
    version: 1, scenario, step: 'invitation', resume: 'source', source: null,
    connection: 'disconnected', importStatus: 'idle', checkpoint: 0, run: 0,
    releases: [], selected: [], rights: null, rightsDraft: {}, documents: [], missingEvidence: false,
    status: 'draft', submission: null, consent: false, reply: null,
    deletionRequested: false, consentVersion: null, faultUsed: false,
  };
}

export function canVisit(state, step) {
  if (!STEPS.includes(step)) return false;
  if (state.step === 'expired') return step === 'expired';
  if (step === 'settings') return true;
  if (step === 'status') return !!state.submission;
  if (state.submission) return false;
  if (step === 'invitation') return true;
  switch (step) {
    case 'source': return true;
    case 'permissions': return state.source === 'toolost';
    case 'provider': return state.connection === 'authorizing';
    case 'account': return state.connection === 'unconfirmed';
    case 'import': return state.connection === 'connected' && state.importStatus !== 'idle';
    case 'coverage': return ['partial', 'complete'].includes(state.importStatus);
    case 'selection': return state.releases.length > 0;
    case 'rights': return state.selected.length > 0;
    case 'documents': return !!state.rights;
    case 'summary': return !!state.rights && (state.documents.length > 0 || state.missingEvidence);
    default: return false;
  }
}

export function submissionIssues(state) {
  const issues = [];
  if (!state.selected.length) issues.push('Choose at least one existing release.');
  if (!state.rights) issues.push('Save the rights information first.');
  if (!state.documents.length && !state.missingEvidence) issues.push('Add a sample document or explain that documents are not available.');
  if (!state.consent) issues.push('Confirm the review scope before submitting.');
  return issues;
}

export function transition(current, event) {
  requireThat(event && typeof event.type === 'string', 'Invalid event');
  const state = copy(current);
  const editable = () => requireThat(state.status === 'draft' && state.step !== 'expired', 'This submitted version is read-only.');
  const at = (...steps) => requireThat(steps.includes(state.step), 'This action is not available on this step.');
  switch (event.type) {
    case 'navigate':
      requireThat(canVisit(state, event.step), 'Complete the previous step first.');
      state.step = event.step;
      return state;
    case 'start':
      at('invitation');
      state.step = state.scenario === 'expired' ? 'expired' : 'source';
      return state;
    case 'source':
      editable(); at('source');
      requireThat(['toolost', 'manual'].includes(event.source), 'Choose a data source.');
      state.selected = []; state.rights = null; state.rightsDraft = {}; state.documents = [];
      state.missingEvidence = false; state.consent = false; state.releases = [];
      state.connection = 'disconnected'; state.importStatus = 'idle'; state.checkpoint = 0;
      state.run += 1;
      state.source = event.source;
      if (event.source === 'toolost') state.step = 'permissions';
      else {
        state.connection = 'disconnected'; state.importStatus = 'idle'; state.checkpoint = 0;
        state.releases = [...ids]; state.step = 'selection'; state.run += 1;
      }
      return state;
    case 'authorize':
      editable(); at('permissions');
      state.connection = 'authorizing'; state.step = 'provider';
      state.consentVersion = 'design-notice-v1';
      return state;
    case 'cancel-authorization':
      editable(); at('provider', 'account');
      state.connection = 'disconnected'; state.step = 'source';
      return state;
    case 'authorize-result':
      editable(); at('provider');
      requireThat(state.scenario !== 'cancelled', 'Permission was not granted. Use documents or restart the connection.');
      state.connection = 'unconfirmed'; state.step = 'account';
      return state;
    case 'confirm-account':
      editable(); at('account');
      state.connection = 'connected'; state.importStatus = 'running'; state.checkpoint = 0;
      state.run += 1; state.step = 'import';
      return state;
    case 'import-tick':
      if (event.run !== state.run || state.connection !== 'connected' || state.importStatus !== 'running' || state.step === 'expired') return current;
      state.checkpoint += 1;
      if (state.checkpoint === 1) state.releases = state.scenario === 'empty' ? [] : [...ids];
      if (state.scenario === 'partial' && !state.faultUsed && state.checkpoint === 2) {
        state.importStatus = 'partial'; state.faultUsed = true;
      } else if (state.checkpoint === 3) state.importStatus = 'complete';
      return state;
    case 'retry-import':
      editable(); at('import', 'coverage');
      requireThat(state.importStatus === 'partial' && state.connection === 'connected', 'There is no interrupted import to resume.');
      state.importStatus = 'running'; state.step = 'import';
      return state;
    case 'select':
      editable(); at('selection');
      requireThat(Array.isArray(event.ids) && event.ids.length > 0 && event.ids.every(id => state.releases.includes(id)), 'Choose at least one listed release.');
      state.selected = [...new Set(event.ids)]; state.consent = false; state.step = 'rights';
      return state;
    case 'edit-rights': {
      editable(); at('rights');
      const allowed = { ownership: ['', 'owned', 'shared', 'unknown'], scope: ['', 'masters', 'royalties', 'unsure'], obligations: ['', 'yes', 'no', 'unknown'] };
      requireThat(event.field === 'share' ? typeof event.value === 'string' && /^[-+0-9.eE]{0,24}$/.test(event.value) : Object.hasOwn(allowed, event.field) && allowed[event.field].includes(event.value), 'Invalid demo answer');
      state.rightsDraft[event.field] = event.value;
      if (event.field === 'ownership' && event.value === 'unknown') state.rightsDraft.share = '';
      return state;
    }
    case 'rights': {
      editable(); at('rights');
      requireThat(['owned', 'shared', 'unknown'].includes(event.ownership), 'Choose what you know about ownership.');
      requireThat(['masters', 'royalties', 'unsure'].includes(event.scope), 'Choose the rights to discuss.');
      requireThat(['yes', 'no', 'unknown'].includes(event.obligations), 'Choose the agreement status.');
      const share = event.ownership === 'unknown' ? null : event.share;
      requireThat(event.ownership === 'unknown' || (typeof share === 'string' && /^(\d{1,2}(\.\d{1,2})?|100(\.0{1,2})?)$/.test(share) && Number(share) > 0), 'Enter an owned share above 0 and up to 100, or choose Ownership needs clarification.');
      state.rights = { ownership: event.ownership, scope: event.scope, share, obligations: event.obligations };
      state.rightsDraft = copy(state.rights);
      state.consent = false; state.step = 'documents';
      return state;
    }
    case 'add-document':
      editable(); at('documents');
      requireThat(DOCUMENTS.some(doc => doc.id === event.id), 'Only bundled sample documents are allowed.');
      state.documents = [...new Set([...state.documents, event.id])]; state.consent = false;
      return state;
    case 'remove-document':
      editable(); at('documents');
      state.documents = state.documents.filter(id => id !== event.id); state.consent = false;
      return state;
    case 'missing-evidence':
      editable(); at('documents');
      state.missingEvidence = event.value === true; state.consent = false;
      return state;
    case 'confirm-scope':
      editable(); at('summary');
      state.consent = event.value === true;
      return state;
    case 'submit':
      if (state.submission) return current;
      editable(); at('summary');
      requireThat(submissionIssues(state).length === 0, submissionIssues(state).join(' '));
      state.submission = { id: 'DEMO-001-v1', version: 1, selected: [...state.selected], rights: copy(state.rights), documents: [...state.documents], missingEvidence: state.missingEvidence, source: state.source };
      state.status = 'submitted'; state.step = 'status';
      return state;
    case 'request-information':
      at('status'); requireThat(!!state.submission, 'Submit a demo package first.');
      state.status = 'needs_information';
      return state;
    case 'reply':
      at('status'); requireThat(state.status === 'needs_information' && Object.hasOwn(REPLIES, event.id), 'Choose a sample response.');
      state.reply = event.id; state.status = 'under_review';
      return state;
    case 'disconnect':
      at('settings');
      state.connection = 'disconnected'; state.run += 1;
      if (['running', 'partial'].includes(state.importStatus)) state.importStatus = 'cancelled';
      return state;
    case 'request-deletion':
      at('settings'); state.deletionRequested = true;
      return state;
    case 'expire':
      if (state.step !== 'expired') state.resume = state.step;
      state.step = 'expired';
      return state;
    case 'resume-session':
      at('expired'); state.step = state.resume === 'expired' ? 'source' : state.resume;
      return state;
    default: fail('Unknown event');
  }
}
