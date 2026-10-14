import { readFileSync } from 'node:fs';
import { buildRequest, sha256, validateLabels } from './core.mjs';

export const CORPUS_SHA256 = 'a5302b2919c7a1b698073564fbf7869b057f93f8c97bb170f7b8191ba868f11c';

function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

export function loadCorpus() {
  const bytes = readFileSync(new URL('./cases.json', import.meta.url));
  if (sha256(bytes) !== CORPUS_SHA256) throw new Error('corpus_changed_review_required');
  const corpus = JSON.parse(bytes);
  if (corpus.synthetic !== true || corpus.version !== 'synthetic-development-v1' || corpus.cases.length !== 20) {
    throw new Error('invalid_corpus');
  }
  const ids = new Set();
  for (const item of corpus.cases) {
    if (!/^s\d{2}$/.test(item.id) || ids.has(item.id) || typeof item.message !== 'string'
      || !['en', 'sv', 'es'].includes(item.language) || !Array.isArray(item.documents) || item.documents.length > 4) {
      throw new Error('invalid_corpus');
    }
    ids.add(item.id);
    const docs = new Set();
    for (const doc of item.documents) {
      if (!/^d\d$/.test(doc.id) || docs.has(doc.id) || typeof doc.text !== 'string') throw new Error('invalid_corpus');
      docs.add(doc.id);
    }
    if (!item.critical_document_ids.every(id => docs.has(id))) throw new Error('invalid_corpus');
    validateLabels(item.expected, buildRequest(item).questions);
  }
  return freeze(corpus);
}
