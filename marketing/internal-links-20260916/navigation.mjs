export const primary = [
  {to:'/how-it-works/', label:'How It Works'},
  {to:'/sell/', label:'Sell'},
  {to:'/calculator/', label:'Calculator'},
  {to:'/blog/', label:'Resources'}
];
export const explore = [
  {to:'/how-it-works/', label:'How It Works'},
  {to:'/sell/', label:'Sell Your Catalog'},
  {to:'/calculator/', label:'Calculator'},
  {to:'/for/', label:'Creators & Labels'},
  {to:'/about/', label:'About'},
  {to:'/apply/', label:'Request a free catalog review'}
];
export const learn = [
  {to:'/blog/', label:'All Resources'},
  {to:'/guides/how-to-sell-music-rights/', label:'Selling Guide'},
  {to:'/guides/music-rights-101/', label:'Music Rights 101'},
  {to:'/guides/music-catalog-valuation-2026/', label:'Valuation Guide'},
  {to:'/guides/what-are-your-streams-worth-2026/', label:'Streams Worth'},
  {to:'/compare/', label:'Compare Your Options'},
  {to:'/glossary/', label:'Rights Glossary'},
  {to:'/streaming-rates/', label:'Streaming Rates'}
];
export const aliases = {
  '/guides/partial-rights-explained':'/compare/partial-sale-vs-full-sale/',
  '/guides/music-catalog-tax-guide':'/guides/how-to-sell-music-rights/#tax-implications',
  ...Object.fromEntries(['spotify','apple-music','youtube-music','amazon-music','tidal','deezer','soundcloud'].map(s=>['/streaming-rates/'+s,'/streaming-rates/'+s+'-2026/']))
};
export const topics = {
  'Music Rights':'/guides/music-rights-101/',
  Monetization:'/guides/how-to-sell-music-rights/',
  'Industry News':'/blog/#articles',
  Tutorials:'/blog/#guides',
  'Success Stories':'/blog/#archive',
  Streaming:'/streaming-rates/',
  royalties:'/glossary/streaming-royalties/',
  streaming:'/streaming-rates/',
  monetization:'/guides/how-to-sell-music-rights/',
  rights:'/guides/music-rights-101/',
  valuation:'/guides/music-catalog-valuation-2026/',
  catalog:'/glossary/music-catalog/',
  ambient:'/sell/sell-ambient-music-catalog/',
  'lo-fi':'/sell/sell-lo-fi-beats-catalog/'
};
// These existing operational routes are preserved, not promoted to visitors.
export const operational = ['/data/conversion-intelligence/', '/data/space-market-index/'];
export const resourceTitle = 'Resources for your next catalog decision';
export const resourceDescription = 'Find SPACE guides, seller checklists, funding comparisons and royalty resources. Explore your options, prepare your documents and request a free catalog review.';
export const resourceGroups = [
  {id:'start', title:'Choose your next step', intro:'Start with the task you want to complete.', items:[
    ['/apply/','Request a free catalog review'],
    ['/calculator/','Explore a catalog-sale scenario'],
    ['/blog/independent-record-label-funding-options/','Compare funding options for your label'],
    ['/sell/','Browse catalogs by genre'],
    ['/for/','Find guidance for your situation'],
    ['/compare/','Compare buyers and deal structures']
  ]},
  {id:'guides', title:'Guides', intro:'Understand the process, rights and evidence before deciding.', prefix:'/guides/'},
  {id:'articles', title:'Articles & seller checklists', intro:'Practical reading for the next stage of your review.', paths:[
    '/blog/music-catalog-sale-documents-checklist/',
    '/blog/music-catalog-offer-checklist/',
    '/blog/independent-record-label-funding-options/',
    '/blog/sell-music-catalog-lump-sum-2026/',
    '/blog/royalty-exchange-alternatives/',
    '/blog/beatbread-vs-catalog-buyers/',
    '/blog/ambient-lo-fi-music-catalog-buyers/',
    '/blog/what-is-a-blanket-license/'
  ]},
  {id:'archive', title:'Earlier articles', intro:'Previously published articles, kept available in their original locations.', paths:[
    '/blog/maximizing-your-lo-fi-catalog-value/',
    '/blog/streaming-royalties-guide-for-ambient-music/',
    '/blog/why-selling-partial-rights-makes-sense/',
    '/blog/how-to-register-your-ambient-music-with-pros/',
    '/blog/case-study-ambient-producer-catalog-sale/',
    '/blog/future-of-ai-in-ambient-music/'
  ]},
  {id:'reference', title:'Tools & reference', intro:'Look up a term, explore royalties or learn more about SPACE.', items:[
    ['/tools/streaming-calculator/','Streaming royalty calculator'],
    ['/streaming-rates/','Platform royalty guides'],
    ['/glossary/','Music rights glossary'],
    ['/data/music-catalog-market-2026/','Music catalog market report (2026)'],
    ['/about/','About SPACE'],
    ['/brand-facts/','SPACE brand facts'],
    ['/pricing.md','Pricing and offer policy'],
    ['/llms.txt','Plain-text site index']
  ]}
];

export function createLinkResolver(publicPaths) {
  const known = new Set(publicPaths);
  return function resolveLink(value) {
    if (typeof value !== 'string' || value.startsWith('#') || !/^(\/[^/]|\/$|https?:\/\/)/.test(value)) return value;
    let url;
    try { url = new URL(value, 'https://spacemusic.io'); } catch { return value; }
    if (!['spacemusic.io','www.spacemusic.io'].includes(url.hostname)) return value;
    const key = url.pathname.replace(/\/$/, '') || '/';
    if (['/blog','/'].includes(key)) {
      const topic = url.searchParams.get('category') || url.searchParams.get('tag');
      if (topic && topics[topic]) return topics[topic];
    }
    if (aliases[key]) {
      const target = new URL(aliases[key], 'https://spacemusic.io');
      target.search = url.search;
      if (!target.hash) target.hash = url.hash;
      return target.pathname + target.search + target.hash;
    }
    const canonical = known.has(url.pathname) ? url.pathname : known.has(key + '/') ? key + '/' : null;
    return canonical ? canonical + url.search + url.hash : value;
  };
}
