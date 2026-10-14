import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "./serve.mjs";
import { STORAGE_KEY, DEMO } from "./model.mjs";
import { playwrightModule } from "../../scripts/funnel-support.mjs";

const root = path.dirname(fileURLToPath(import.meta.url));
const qa = path.join(root, "qa");
await mkdir(qa, { recursive: true });
const server = createServer();
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const { chromium } = await import(playwrightModule);
const browser = await chromium.launch({ channel: "chrome", headless: true });
const axe = await readFile(
  path.resolve(
    root,
    "../../tmp/catalog-readiness-tools/node_modules/axe-core/axe.min.js",
  ),
  "utf8",
);
const result = {
  checkedAt: new Date().toISOString(),
  widths: [320, 390, 768, 1024, 1440],
  accessibility: [],
  checks: [],
  remoteRequests: [],
  posts: [],
  errors: [],
};
const context = await browser.newContext();
const isolateRequests = (target) =>
  target.route("**/*", (route) => {
    const request = route.request();
    if (request.method() !== "GET") {
      result.posts.push(request.url());
      return route.abort();
    }
    if (new URL(request.url()).origin !== origin) {
      result.remoteRequests.push(request.url());
      return route.abort();
    }
    return route.continue();
  });
await isolateRequests(context);
const page = await context.newPage();
page.on("pageerror", (error) => result.errors.push(error.message));
const click = (action) =>
  page.locator(`[data-action="${action}"]`).first().click();
async function heading(text) {
  await page.getByRole("heading", { name: text, level: 1 }).waitFor();
}
async function audit(name) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() =>
    Promise.all(
      document.getAnimations().map((animation) => animation.finished),
    ),
  );
  for (const width of result.widths) {
    await page.setViewportSize({ width, height: 950 });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      `${name} overflow at ${width}`,
    );
    assert.equal(await page.locator("h1").count(), 1);
    assert.equal(await page.locator('input[type="file"]').count(), 0);
    if ([390, 1440].includes(width)) {
      await page.evaluate(axe);
      const findings = await page.evaluate(async () => {
        const data = await axe.run(document, {
          runOnly: {
            type: "tag",
            values: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"],
          },
        });
        return {
          violations: data.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            nodes: v.nodes.map((n) => ({
              target: n.target,
              summary: n.failureSummary,
            })),
          })),
          incomplete: data.incomplete.map((v) => v.id),
        };
      });
      result.accessibility.push({ screen: name, width, ...findings });
      assert.deepEqual(
        findings.violations,
        [],
        `${name} ${width}: ${JSON.stringify(findings.violations)}`,
      );
      await page.locator("#main").focus();
      await page.screenshot({
        path: path.join(qa, `${name}-${width}.png`),
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 950 });
  console.log(`Checked ${name}`);
}
try {
  const response = await page.goto(origin);
  assert.equal(response.status(), 200);
  assert.match(response.headers()["x-robots-tag"], /noindex/);
  await heading("We buy your music catalog.");
  await audit("apply");
  await page.reload();
  await heading("We buy your music catalog.");
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(":focus").innerText(), "Skip to content");
  await page.keyboard.press("Enter");
  assert.equal(await page.locator(":focus").getAttribute("id"), "main");
  await page.locator('#apply-form button[type="submit"]').click();
  assert.equal(await page.locator(":focus").getAttribute("id"), "email");
  await click("sample-contact");
  await page.locator('#apply-form button[type="submit"]').press("Enter");
  await heading("Your first step is done.");
  await audit("received");
  await click("continue-catalog");
  await page.locator('#catalog-form button[type="submit"]').click();
  assert.equal(await page.locator(":focus").getAttribute("id"), "distributor");
  await click("sample-catalog");
  await page.locator("#owned").fill("101");
  await page.locator('#catalog-form button[type="submit"]').click();
  assert.equal(await page.locator(":focus").getAttribute("id"), "owned");
  assert.equal(
    await page.locator("#artistLink").inputValue(),
    DEMO.details.artistLink,
  );
  await page.locator("#owned").fill("50");
  await page.locator("#offered").fill("50");
  await page.locator("#revenue").fill("0");
  await page.locator('#catalog-form button[type="submit"]').click();
  await heading("Bring the source, not just the total.");
  await click("back:catalog");
  assert.equal(await page.locator("#revenue").inputValue(), "0");
  await click("sample-catalog");
  await audit("catalog");
  await click("pause");
  await audit("paused");
  await page.reload();
  await heading("Pick up where you left off.");
  await click("resume");
  assert.equal(await page.locator("#tracks").inputValue(), "12");
  await page.locator('#catalog-form button[type="submit"]').click();
  await heading("Bring the source, not just the total.");
  assert.equal(
    await page.locator('#documents-form button[type="submit"]').isDisabled(),
    true,
  );
  await page.locator(".preview-controls summary").click();
  await click("upload-failure");
  await page.locator('.field-error[role="alert"]').waitFor();
  assert.equal(await page.locator(".uploaded").count(), 0);
  await click("add:royalties");
  await page.locator('[data-action="remove:royalties"]').waitFor();
  await click("add:tracks");
  await page.locator('[data-action="remove:tracks"]').waitFor();
  assert.equal(await page.locator(".uploaded").count(), 2);
  await audit("documents");
  await click("remove:tracks");
  assert.equal(
    await page.locator('#documents-form button[type="submit"]').isDisabled(),
    true,
  );
  await click("add:tracks");
  await page.locator('[data-action="remove:tracks"]').waitFor();
  await page.locator('#documents-form button[type="submit"]').click();
  await heading("Your catalog. Clearly defined.");
  await page.locator('[data-step="1"]').click();
  await page.locator("#tracks").fill("13");
  assert.equal(await page.locator('[data-step="2"]').isDisabled(), true);
  assert.equal(await page.locator('[data-step="3"]').isDisabled(), true);
  await page.locator("#tracks").fill("12");
  await page.locator('#catalog-form button[type="submit"]').click();
  await page.locator('#documents-form button[type="submit"]').click();
  await audit("review");
  await page.locator(".preview-controls summary").click();
  await click("fail-submit");
  await page.locator('#review-form button[type="submit"]').click();
  await page
    .getByText("Simulated submission failed.", { exact: false })
    .waitFor();
  assert.match(await page.locator("main").innerText(), /USD 4,800.00/);
  // Two synchronous submission events must still perform only one transition.
  await page.locator("#review-form").evaluate((form) => {
    form.requestSubmit();
    form.requestSubmit();
  });
  await heading("Everything in one place.");
  await audit("under-review");
  await page.locator(".preview-controls summary").click();
  await click("request-clarification");
  await heading("One detail to clarify.");
  await audit("clarification");
  await page.locator('#reply-form button[type="submit"]').click();
  assert.match(
    await page.locator(".error-summary").innerText(),
    /clarification/,
  );
  await page
    .locator("#reply")
    .fill(
      "The fictional amount is my own share after splits. <img src=x onerror=alert(1)>",
    );
  await page.locator('#reply-form button[type="submit"]').click();
  await heading("Your reply is ready for review.");
  assert.equal(await page.locator(".reply-note img").count(), 0);
  assert.match(await page.locator(".reply-note").innerText(), /<img src=x/);
  await page.reload();
  await heading("Pick up where you left off.");
  await click("resume");
  await heading("Your reply is ready for review.");
  assert.match(await page.locator(".reply-note").innerText(), /my own share/);
  await page.evaluate(() => localStorage.setItem("unrelated-demo-key", "keep"));
  await click("reset");
  await click("confirm-reset");
  await heading("We buy your music catalog.");
  assert.equal(
    await page.evaluate(() => localStorage.getItem("unrelated-demo-key")),
    "keep",
  );
  assert.equal(
    await page.evaluate((key) => localStorage.getItem(key), STORAGE_KEY),
    null,
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  assert.equal(
    await page
      .locator(".panel-enter")
      .evaluate((el) => getComputedStyle(el).animationName),
    "none",
  );
  // 200% layout zoom at 1280-equivalent viewport, plus 320px reflow audited above.
  await page.setViewportSize({ width: 1280, height: 950 });
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "200% zoom overflow",
  );
  await page.evaluate(() => {
    document.documentElement.style.zoom = "";
  });
  await click("sample-contact");
  await page.locator('#apply-form button[type="submit"]').click();
  await heading("Your first step is done.");
  await click("continue-catalog");
  await page.evaluate(() => {
    Storage.prototype.setItem = function () {
      throw new DOMException("Full", "QuotaExceededError");
    };
  });
  await page.locator("#tracks").fill("12");
  assert.equal(
    await page.locator(".save-indicator").innerText(),
    "Temporary demo",
  );
  assert.match(
    await page.locator("#storage-note").innerText(),
    /recent changes may be lost/,
  );
  const noStorage = await browser.newContext();
  await isolateRequests(noStorage);
  await noStorage.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new DOMException("Blocked", "SecurityError");
      },
    });
  });
  const blocked = await noStorage.newPage();
  await blocked.goto(origin);
  await blocked
    .getByText("Browser storage is unavailable.", { exact: false })
    .waitFor();
  await blocked.locator('[data-action="sample-contact"]').click();
  await blocked.locator('#apply-form button[type="submit"]').click();
  await blocked
    .getByRole("heading", { name: "Your first step is done." })
    .waitFor();
  await blocked.locator('[data-action="pause"]').first().click();
  assert.match(
    await blocked.locator("main").innerText(),
    /still available in this tab/,
  );
  await noStorage.close();
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  await isolateRequests(noJs);
  const staticPage = await noJs.newPage();
  await staticPage.goto(origin);
  assert.match(
    await staticPage.locator("main").innerText(),
    /needs JavaScript/,
  );
  assert.equal(await staticPage.locator("form").count(), 0);
  await noJs.close();
  assert.equal((await context.request.post(origin)).status(), 405);
  for (const url of [
    "/README.md",
    "/qa/browser-results.json",
    "/%2e%2e%2fRELEASE.md",
    "/services/seller_ui/index.html",
  ])
    assert.equal((await context.request.get(origin + url)).status(), 404, url);
  const head = await context.request.head(origin);
  assert.equal((await head.body()).length, 0);
  assert.match(
    head.headers()["content-security-policy"],
    /connect-src 'none'; form-action 'none'/,
  );
  assert.equal((await context.cookies()).length, 0);
  assert.deepEqual(result.remoteRequests, []);
  assert.deepEqual(result.posts, []);
  assert.deepEqual(result.errors, []);
  result.checks = [
    "full simulated journey",
    "validation and zero income",
    "keyboard",
    "local save/resume and reload",
    "sample upload failure/retry/removal",
    "submission failure/retry/double event",
    "manual clarification",
    "HTML escaping",
    "reset preserves unrelated storage",
    "blocked storage",
    "late storage failure updates save indicator",
    "catalog edits disable stale progress links",
    "no JavaScript fallback",
    "reduced motion",
    "200% layout zoom",
    "no real file inputs",
    "no remote requests or submissions",
    "no cookies",
    "HTTP method and asset allowlist",
  ];
  await writeFile(
    path.join(qa, "browser-results.json"),
    JSON.stringify(result, null, 2),
  );
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
