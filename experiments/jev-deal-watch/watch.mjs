// Deal watch for the Music Catalog Deal Tracker. Reads industry RSS feeds, asks Jev
// whether each new article reports a completed or agreed music catalog acquisition and
// whether a price is disclosed, and queues likely deals for human review.
// Nothing is published automatically: approved rows are added to
// marketing/growth-20260930/data/deals.json by a person.
// Usage: node experiments/jev-deal-watch/watch.mjs
import {readFile, writeFile} from 'node:fs/promises';
import {ask} from '../jev-site-review/jev.mjs';

const FEEDS = [
  'https://www.musicbusinessworldwide.com/feed/',
  'https://www.digitalmusicnews.com/feed/',
  'https://musically.com/feed/',
  'https://variety.com/v/music/feed/',
  'https://www.billboard.com/feed/',
];
const DATA = 'marketing/growth-20260930/data/';
const SEEN = 'experiments/jev-deal-watch/seen.json';
const QUEUE = DATA + 'deal-queue.json';
const decode = s => s.replace(/<!\[CDATA\[|\]\]>/g, '').replace(/<[^>]+>/g, ' ').replace(/&#8216;|&#8217;/g, "'").replace(/&#8220;|&#8221;/g, '"').replace(/&#8211;|&#8212;/g, '-').replace(/&amp;/g, '&').replace(/&#\d+;/g, ' ').replace(/\s+/g, ' ').trim();
const tag = (x, t) => decode((x.match(new RegExp(`<${t}[^>]*>([\\s\\S]*?)</${t}>`)) || [])[1] || '');

const seen = new Set(JSON.parse(await readFile(SEEN, 'utf8').catch(() => '[]')));
const known = new Set(JSON.parse(await readFile(DATA + 'deals.json', 'utf8')).deals.map(d => d.url));
const queue = JSON.parse(await readFile(QUEUE, 'utf8').catch(() => '{"items":[]}'));
const items = [];
for (const feed of FEEDS) {
  const xml = await fetch(feed, {headers: {'user-agent': 'Mozilla/5.0 (Macintosh) Chrome/140 SPACE deal watch'}, signal: AbortSignal.timeout(20000)}).then(r => r.text()).catch(() => '');
  for (const raw of xml.split(/<item[ >]/).slice(1)) {
    const link = tag(raw, 'link') || (raw.match(/<guid[^>]*>([^<]+)</) || [])[1];
    if (!link || seen.has(link) || known.has(link)) continue;
    items.push({feed, link, title: tag(raw, 'title'), date: tag(raw, 'pubDate'), summary: tag(raw, 'description').slice(0, 800)});
  }
}
let added = 0;
for (let i = 0; i < items.length; i += 10) {
  const batch = items.slice(i, i + 10);
  const questions = {};
  batch.forEach((_, j) => {
    questions[`${j}_deal`] = {type: 'noul', instructions: `Does \`articles[${j}]\` report that a company or investor bought, or agreed to buy, music rights (a song catalog, publishing, master recordings or royalty streams) from an artist, songwriter, estate or company? Funding rounds, lawsuits, charts, tours and label signings do not count.`};
    questions[`${j}_price`] = {type: 'noul', instructions: `Does \`articles[${j}]\` state a price or a reported price for that deal?`};
  });
  const r = await ask({articles: batch.map(b => ({title: b.title, summary: b.summary}))}, questions);
  batch.forEach((b, j) => {
    seen.add(b.link);
    const p = r.answers[`${j}_deal`].noul;
    if (p >= 0.6) { queue.items.push({...b, pDeal: +p.toFixed(2), pPrice: +r.answers[`${j}_price`].noul.toFixed(2), status: 'needs review', found: new Date().toISOString().slice(0, 10)}); added++; }
  });
}
await writeFile(SEEN, JSON.stringify([...seen].slice(-5000), null, 0));
await writeFile(QUEUE, JSON.stringify(queue, null, 1));
console.log(`deal watch: ${items.length} new articles, ${added} queued for review (${queue.items.filter(x => x.status === 'needs review').length} waiting)`);
