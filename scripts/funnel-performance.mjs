import { spawn } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { serve } from './funnel-support.mjs';
const [directory, output, ...pages] = process.argv.slice(2);
const server = await serve(directory);
await mkdir(output, { recursive: true });
const results = [];
try {
  for (const page of pages.length ? pages : ['/', '/calculator/', '/apply/', '/guides/music-catalog-valuation-2026/']) {
    const runs = [];
    for (let i = 0; i < 3; i++) {
      const report = `${output}/${page.replaceAll('/', '_') || 'home'}-${i + 1}.json`;
      await new Promise((resolve, reject) => {
        const child = spawn('npx', ['--yes', 'lighthouse@13.4.1', server.origin + page, '--only-categories=performance', '--chrome-flags=--headless=new', '--output=json', `--output-path=${report}`, '--blocked-url-patterns=*plausible.io/api/event*', '--quiet'], { stdio: 'inherit' });
        child.on('exit', code => code === 0 ? resolve() : reject(Error(`Lighthouse ${code}`)));
      });
      const data = JSON.parse(await readFile(report, 'utf8'));
      if (data.runtimeError) throw Error(JSON.stringify(data.runtimeError));
      runs.push({ lcp: data.audits['largest-contentful-paint'].numericValue, cls: data.audits['cumulative-layout-shift'].numericValue, score: data.categories.performance.score, lighthouse: data.lighthouseVersion, environment: data.environment, settings: data.configSettings });
    }
    const medianLcp = runs.map(run => run.lcp).sort((a,b) => a-b)[1];
    results.push({ page, medianLcp, runs });
    console.log(JSON.stringify({ page, medianLcp, scores: runs.map(run => run.score) }));
    await writeFile(`${output}/summary.json`, JSON.stringify(results, null, 2));
  }
} finally { server.close(); }
