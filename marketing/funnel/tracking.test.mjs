import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
const code = (await readFile(new URL('./tracking.js', import.meta.url), 'utf8')).replace('__PUBLIC_PATHS__', JSON.stringify(['/', '/calculator/', '/apply/', '/sell/']));
function setup({ pathname = '/calculator/', storage = new Map(), blocked = false, hostname = 'spacemusic.io', referrer = '' } = {}) {
  const calls = [], listeners = {};
  const location = { pathname, hostname, origin: `https://${hostname}`, href: `https://${hostname}${pathname}?token=SECRET` };
  const context = { URL, location, document: { referrer, addEventListener: (name, callback) => listeners[name] = callback },
    sessionStorage: { getItem: key => { if (blocked) throw Error('blocked'); return storage.get(key); }, setItem: (key,value) => { if (blocked) throw Error('blocked'); storage.set(key,value); } },
    window: { plausible: (...args) => calls.push(args) } };
  vm.runInNewContext(code,context);
  return { api: context.window.spaceFunnel, calls, context, storage, listeners };
}
const run = setup();
assert.equal(run.api.sources().landing_path, '/calculator/');
for (const bad of ['/private/token/', '//evil.test/', '/apply/?email=private', '/apply/#secret', 'https://spacemusic.io/apply/', '/calculator/../apply/', '/apply%2f', '/apply\\']) assert.equal(run.api.publicPath(bad), '');
assert.equal(run.api.publicPath('/apply'),'/apply/');
run.api.once('calculator_used'); run.api.once('calculator_used');
assert.equal(run.calls.length,1);
run.listeners.click({ target: { closest: () => ({ href: 'https://spacemusic.io/apply/?token=PRIVATE' }) } });
assert.equal(run.api.sources().apply_source_path,'/calculator/');
const apply = setup({ pathname:'/apply/', storage:run.storage });
assert.equal(apply.api.sources().landing_path,'/calculator/');
assert.equal(apply.api.sources().apply_source_path,'/calculator/');
const sanitized = apply.api.transformRequest({ n:'application_submitted', u:'https://spacemusic.io/apply/?email=PRIVATE#TOKEN', d:'bad', r:'https://google.com/search?q=PRIVATE', p:{ landing_path:'/calculator/', apply_source_path:'/calculator/', email:'PRIVATE', revenue:999, token:'TOKEN' }, revenue:{ amount:999 }, arbitrary:'PRIVATE' });
assert.equal(JSON.stringify(sanitized).includes('PRIVATE'),false);
assert.equal(sanitized.u,'https://spacemusic.io/apply/');
assert.equal(sanitized.r,'https://google.com');
assert.deepEqual(Object.keys(sanitized.p).sort(),['apply_source_path','landing_path']);
assert.equal(apply.api.transformRequest({ n:'Form: Submission', u:'https://spacemusic.io/apply/' }), null);
assert.equal(apply.api.transformRequest({ n:'pageview', u:'https://spacemusic.io/seller/PRIVATE' }),null);
assert.equal(setup({ hostname:'preview.pages.dev' }).api.transformRequest({ n:'calculator_used', u:'https://spacemusic.io/calculator/' }),null);
const direct = setup({ pathname:'/apply/' });
assert.equal(direct.api.sources().apply_source_path,undefined);
const blocked = setup({ blocked:true });
assert.equal(blocked.api.sources().landing_path,'/calculator/');
blocked.context.window.plausible = () => { throw Error('blocked'); };
assert.doesNotThrow(() => blocked.api.track('calculator_used'));
assert.doesNotThrow(() => blocked.api.once('application_started'));
const dirty = setup({ storage:new Map([['space.funnel.v1.landing_path','/token/SECRET']]) });
assert.equal(dirty.api.sources().landing_path,'/calculator/');
console.log('Tracking privacy, attribution, deduplication, failure isolation and preview exclusions passed');
