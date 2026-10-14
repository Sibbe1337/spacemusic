import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import path from 'node:path';

// Override these paths for another workstation; no package/browser installation.
const packages = process.env.SPACE_TEST_NODE_MODULES || `${process.env.HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`;
const require = createRequire(path.join(packages, 'package.json'));
const { chromium } = require('playwright');
const executablePath = process.env.SPACE_TEST_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
assert.ok(existsSync(executablePath), 'An installed Chromium browser is required');
const bridge = async (route, body = {}) => {
  const response = await fetch(process.env.SPACE_TEST_BRIDGE + route, {method: 'POST', headers: {'content-type': 'application/json', 'x-test-bridge': process.env.SPACE_TEST_BRIDGE_KEY}, body: JSON.stringify(body)});
  assert.equal(response.status, 200);
  return response.json();
};
const browser = await chromium.launch({headless: true, executablePath});
const errors = [];
const external = [];
let dropSubmission = true;
let submissionAttempts = 0;
let dropReply = true;
const replyRequests = [];
async function context(options = {}) {
  const ctx = await browser.newContext({viewport: {width: 1365, height: 1000}, ...options});
  await ctx.route('**/*', async route => {
    const request = route.request();
    if (new URL(request.url()).origin !== 'https://review.test') {
      external.push(request.url());
      return route.abort();
    }
    const result = await bridge('/asgi', {url: request.url(), method: request.method(), headers: await request.allHeaders(), body: request.postDataBuffer()?.toString('base64') || ''});
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/portal/submission') {
      submissionAttempts += 1;
      if (dropSubmission && result.status === 200) {
        dropSubmission = false;
        return route.abort('connectionfailed');
      }
    }
    if (request.method() === 'POST' && /\/questions\/[^/]+\/reply$/.test(new URL(request.url()).pathname)) {
      replyRequests.push(request.postData());
      if (dropReply && result.status === 200) {
        dropReply = false;
        return route.abort('connectionfailed');
      }
    }
    await route.fulfill({status: result.status, headers: result.headers, body: Buffer.from(result.body, 'base64')});
  });
  return ctx;
}
async function page(ctx) {
  const p = await ctx.newPage();
  p.setDefaultTimeout(12000);
  p.on('pageerror', error => errors.push(error.message));
  await p.clock.setFixedTime(new Date(process.env.SPACE_TEST_NOW));
  return p;
}
async function idle(p) { await p.waitForFunction(() => document.querySelector('main')?.getAttribute('aria-busy') === 'false'); }
async function noOverflow(p) { assert.ok(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); }

try {
  const ownerContext = await context();
  const owner = await page(ownerContext);
  await owner.goto(process.env.SPACE_TEST_INVITATION);
  await owner.getByRole('button', {name: 'Open invitation', exact: true}).waitFor();
  assert.equal(new URL(owner.url()).hash, '');
  assert.equal((await ownerContext.cookies()).length, 0, 'GET must not authenticate');
  await owner.getByRole('button', {name: 'Open invitation', exact: true}).focus();
  await owner.keyboard.press('Enter');
  await owner.locator('#title-0').waitFor();
  await idle(owner);
  await owner.locator('#title-0').fill('Northline synthetic catalog');
  await owner.locator('#artist-0').fill('Example Records');
  await owner.locator('#ownership-0').selectOption('known');
  await owner.locator('#share-0').fill('50');
  await owner.locator('#scope-0').selectOption('masters');
  await owner.locator('#obligations-0').selectOption('unknown');
  await owner.getByRole('button', {name: 'Save draft', exact: true}).click();
  await idle(owner);
  assert.match(await owner.locator('#screen-message').innerText(), /Draft saved/);
  await owner.locator('#synthetic-file').setInputFiles({name: 'sample-statement.csv', mimeType: 'text/csv', buffer: Buffer.from('period,amount\n2026-08,10\n')});
  await owner.getByRole('button', {name: 'Upload synthetic document', exact: true}).click();
  await idle(owner);
  assert.match(await owner.locator('#screen-message').innerText(), /awaiting checks/i);
  await bridge('/scan-synthetic');
  await owner.getByRole('button', {name: 'Refresh workspace', exact: true}).click();
  await idle(owner);
  await owner.locator('input[data-document="0"]').check();
  await owner.getByRole('button', {name: 'Save draft', exact: true}).click();
  await idle(owner);
  await noOverflow(owner);
  await owner.screenshot({path: path.join(process.env.SPACE_TEST_SCREENSHOTS, 'workspace-desktop.png'), fullPage: true, animations: 'disabled'});
  await owner.setViewportSize({width: 390, height: 844});
  await noOverflow(owner);
  await owner.screenshot({path: path.join(process.env.SPACE_TEST_SCREENSHOTS, 'workspace-mobile.png'), fullPage: true, animations: 'disabled'});
  await owner.locator('#consent').check();
  await owner.getByRole('button', {name: 'Submit saved draft', exact: true}).click();
  await idle(owner);
  await owner.getByRole('button', {name: 'Retry same submission', exact: true}).click();
  await idle(owner);
  assert.match(await owner.locator('#screen-message').innerText(), /Submission received/);
  assert.equal(submissionAttempts, 2);
  assert.equal(await owner.locator('#draft-form').count(), 0);

  const staffContext = await context();
  await staffContext.addCookies([{name: '__Host-space_review', value: process.env.SPACE_TEST_REVIEWER, url: 'https://review.test', httpOnly: true, secure: true, sameSite: 'Lax'}]);
  const staff = await page(staffContext);
  await staff.goto('https://review.test/workspace/');
  await staff.getByRole('button', {name: 'Refresh existing session', exact: true}).click();
  await staff.locator('#body-new').waitFor();
  await idle(staff);
  assert.equal(await staff.locator('#draft-form').count(), 0);
  await staff.locator('#body-new').fill('Are the missing statements available? <script>window.bad=1</script>');
  await staff.locator('#request-documents').check();
  await staff.getByRole('button', {name: 'Send question', exact: true}).click();
  await idle(staff);
  assert.match(await staff.locator('#screen-message').innerText(), /Message received/);
  await staff.locator('#body-new').fill('Which existing releases need a rights follow-up?');
  await staff.getByRole('button', {name: 'Send question', exact: true}).click();
  await idle(staff);
  await owner.getByRole('button', {name: 'Refresh workspace', exact: true}).click();
  await idle(owner);
  const questionUpload = owner.locator('[data-question-upload]').first();
  const questionId = await questionUpload.getAttribute('data-question-upload');
  await questionUpload.locator('input[type="file"]').setInputFiles({name:'follow-up.csv',mimeType:'text/csv',buffer:Buffer.from('period,net\n2026-07,12\n')});
  await questionUpload.getByRole('button',{name:'Upload for this question',exact:true}).click();
  await idle(owner);
  await bridge('/scan-synthetic');
  await owner.locator(`[data-action="refresh-question-documents"][data-question-id="${questionId}"]`).click();
  await idle(owner);
  await owner.locator(`[data-document-question="${questionId}"]`).check();
  await staff.getByRole('button',{name:'Refresh workspace',exact:true}).click();
  await idle(staff);
  assert.ok(!(await staff.locator('main').innerText()).includes('follow-up.csv'),'Unpublished documents remain private');
  await owner.locator(`#body-${questionId}`).fill('Attached the requested synthetic statement.');
  await owner.locator(`#body-${questionId}`).locator('xpath=ancestor::form').getByRole('button',{name:'Send reply',exact:true}).click();
  await idle(owner);
  await owner.getByRole('button', {name: 'Refresh workspace', exact: true}).click();
  if (await owner.getByRole('button', {name: 'Reload server version', exact: true}).count()) {
    await owner.getByRole('button', {name: 'Reload server version', exact: true}).click();
  }
  await idle(owner);
  await owner.getByRole('button', {name: 'Retry same message', exact: true}).click();
  await idle(owner);
  assert.equal(replyRequests.length, 2);
  assert.equal(replyRequests[0], replyRequests[1], 'Reply replay must preserve its exact request');
  await owner.locator('[data-question-form="reply"] textarea').fill('The selected existing release needs follow-up.');
  await owner.getByRole('button', {name: 'Send reply', exact: true}).click();
  await idle(owner);
  assert.match(await owner.locator('#screen-message').innerText(), /Message received/);
  await staff.getByRole('button',{name:'Refresh workspace',exact:true}).click();
  await idle(staff);
  await staff.getByRole('heading',{name:'Published supplement version 1',exact:true}).waitFor();
  assert.match(await staff.locator('main').innerText(),/follow-up\.csv/);
  assert.equal(await owner.evaluate(() => window.bad), undefined);
  assert.equal(await owner.evaluate(() => localStorage.length + sessionStorage.length), 0);

  await bridge('/expire-synthetic');
  await owner.getByRole('button', {name: 'Refresh workspace', exact: true}).click();
  await idle(owner);
  assert.equal(await owner.locator('#draft-form').count(), 0);
  assert.ok(!(await owner.locator('main').innerText()).includes('Northline synthetic catalog'));
  assert.match(await owner.locator('main').innerText(), /expired/);
  assert.equal(errors.length, 0, errors.join('\n'));
  assert.equal(external.length, 0, 'Unexpected network destinations');
  console.log('Browser journey passed: real UI, ASGI, PostgreSQL, upload, retry, reviewer Q&A, mobile, expiry.');
} finally {
  await browser.close();
}
