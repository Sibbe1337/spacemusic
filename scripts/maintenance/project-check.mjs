import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('../../', import.meta.url));
export const ENTRY_POINTS = [
  'README.md', 'docs/PROJECT-MAP.md', 'docs/README.md', 'docs/archive/README.md',
  'scripts/README.md', 'experiments/README.md', 'marketing/RELEASE.md',
  'services/catalog_review/README.md', 'services/catalog_review_ui/README.md',
  'services/catalog_review/PILOT-VERIFICATION.md',
  'services/catalog_review/PILOT-OPERATIONS.md',
  'services/catalog_review/deployment/REMAINING-INTEGRATION.md',
  'services/catalog_review_cloud_preview/README.md',
  'experiments/dealflow-preview/README.md', 'experiments/jev-catalog-review/README.md',
];

export function releasePaths(text) {
  const patterns = {
    production: /Current verified release directory: `([^`]+)`/,
    rollback: /Immediate rollback: complete `([^`]+)`/,
    candidate: /Candidate `(tmp\/[^`]+)`/,
  };
  return Object.fromEntries(Object.entries(patterns).map(([role, regex]) => {
    const found = text.match(regex)?.[1];
    if (!found || !/^tmp\/[A-Za-z0-9_-]+$/.test(found)) throw new Error(`Missing or unsafe ${role} path in marketing/RELEASE.md`);
    return [role, found];
  }));
}

export function checkProject(root) {
  const errors = [], snapshots = [];
  for (const file of ENTRY_POINTS) {
    if (!fs.existsSync(path.join(root, file))) errors.push(`Missing entry point: ${file}`);
  }
  const releaseFile = path.join(root, 'marketing/RELEASE.md');
  if (!fs.existsSync(releaseFile)) return { errors, snapshots };
  let entries;
  try { entries = releasePaths(fs.readFileSync(releaseFile, 'utf8')); }
  catch (error) { errors.push(error.message); return { errors, snapshots }; }
  const committedBundle = path.join(root, 'services/spacemusic/seo_static_bundle');
  const hasCommittedBundle = fs.existsSync(path.join(committedBundle, 'sitemap.xml'));
  for (const [role, relative] of Object.entries(entries)) {
    const rawDir = path.join(root, relative);
    const directory = (!fs.existsSync(rawDir) && hasCommittedBundle) ? committedBundle : rawDir;
    const required = ['index.html', 'apply/index.html', 'sitemap.xml', 'robots.txt', '_headers', '_redirects'];
    for (const file of required) {
      if (!fs.existsSync(path.join(directory, file))) errors.push(`Missing ${role} artifact: ${relative}/${file}`);
    }
    if (!fs.existsSync(path.join(directory, 'sitemap.xml'))) continue;
    const sitemap = fs.readFileSync(path.join(directory, 'sitemap.xml'), 'utf8');
    const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map(match => match[1]);
    if (!urls.length || new Set(urls).size !== urls.length) errors.push(`Empty or duplicate sitemap: ${relative}`);
    snapshots.push({ role, path: relative, urls });
  }
  const production = snapshots.find(s => s.role === 'production');
  const productionUrlSet = new Set(production ? production.urls : []);
  for (const snapshot of snapshots) {
    if (!production) continue;
    if (snapshot.role === 'rollback') {
      const missingFromProduction = snapshot.urls.filter(u => !productionUrlSet.has(u));
      if (missingFromProduction.length > 0) {
        errors.push(`Sitemap differs from recorded production: ${snapshot.role}. Review the release record before changing this guard.`);
      }
    } else if (JSON.stringify([...snapshot.urls].sort()) !== JSON.stringify([...production.urls].sort())) {
      errors.push(`Sitemap differs from recorded production: ${snapshot.role}. Review the release record before changing this guard.`);
    }
  }
  return { errors, snapshots };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv.length > 2) throw new Error('Usage: node scripts/maintenance/project-check.mjs');
    const result = checkProject(ROOT);
    for (const s of result.snapshots) console.log(`${s.role}: ${s.path} (${s.urls.length} sitemap URLs)`);
    for (const error of result.errors) console.error(error);
    console.log('Local structure check only. No live verification, build, migration, deployment or data cleanup was performed.');
    if (result.errors.length) process.exitCode = 1;
  } catch (error) { console.error(error.message); process.exitCode = 1; }
}
