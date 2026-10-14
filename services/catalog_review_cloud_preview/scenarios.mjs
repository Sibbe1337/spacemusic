// Public, fictional examples only. This module must never import portal records.
export const SCENARIOS = ['draft', 'submitted', 'followup', 'completed', 'reviewer'];
const id = number => `10000000-0000-4000-8000-${String(number).padStart(12, '0')}`;
const created = '2026-09-18T10:00:00Z';

export function workspaceFor(scenario, now = Date.now()) {
  if (!SCENARIOS.includes(scenario)) throw new Error('Unknown preview scenario');
  const documents = [
    { document_id: id(10), question_id: null, filename: 'EXAMPLE-royalty-history.csv', status: 'accepted_for_review' },
    { document_id: id(11), question_id: null, filename: 'EXAMPLE-release-metadata.xlsx', status: 'accepted_for_review' },
  ];
  const draft = {
    source: 'documents', future_music_excluded: true,
    rights: [
      { release_reference: 'EXAMPLE-001', title: 'Northern Lines (fictional)', artist: 'Example Recordings', ownership: 'known', share_percent: '100', rights_scope: 'masters', obligations: 'none_declared' },
      { release_reference: 'EXAMPLE-002', title: 'After Hours (fictional)', artist: 'Example Recordings', ownership: 'known', share_percent: '50', rights_scope: 'masters', obligations: 'present' },
    ],
    document_ids: documents.map(document => document.document_id),
  };
  const submission = scenario === 'draft' ? null : {
    submission_id: id(20), revision: 2, created_at: created,
    snapshot: { draft: structuredClone(draft), documents: structuredClone(documents), missing_evidence: false },
  };
  const questions = ['followup', 'completed', 'reviewer'].includes(scenario) ? [{
    question_id: id(30), request_documents: true, created_at: created, reply: null,
    body: 'For After Hours, please provide the agreement showing your 50% master share and explain any ongoing distributor or collaborator obligations. Future releases remain outside this review.',
  }] : [];
  if (['completed', 'reviewer'].includes(scenario)) {
    const supplementDocuments = [{ document_id: id(12), question_id: id(30), filename: 'EXAMPLE-master-split-agreement.pdf', status: 'accepted_for_review' }];
    documents.push(...supplementDocuments);
    questions[0].reply = {
      body: 'Fictional example: the agreement records a 50% master share. The distribution agreement remains in place and needs review before any transaction.',
      created_at: created, document_ids: [id(12)],
      supplement: { supplement_id: id(40), submission_id: id(20), version: 1, created_at: created, documents: supplementDocuments },
    };
  }
  return {
    workspace_id: id(1), environment: 'test', role: scenario === 'reviewer' ? 'reviewer' : 'owner',
    revision: 2, draft, documents, submission, questions,
    review_status: scenario === 'draft' ? 'not_submitted' : scenario === 'followup' ? 'needs_information' : scenario === 'submitted' ? 'submitted' : 'under_review',
    session_expires_at: new Date(now + 60 * 60 * 1000).toISOString(),
    csrf: 'public-preview-not-a-real-session', capabilities: { document_upload: true, toolost: false },
  };
}
