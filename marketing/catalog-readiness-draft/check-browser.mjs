import assert from "node:assert/strict";
import { mkdir, writeFile, copyFile, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "./serve.mjs";
import { playwrightModule } from "../../scripts/funnel-support.mjs";
const root = path.dirname(fileURLToPath(import.meta.url));
const qa = path.join(root, "qa");
await mkdir(qa, { recursive: true });
const server = createServer();
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const { chromium } = await import(playwrightModule);
const browser = await chromium.launch({ channel: "chrome", headless: true });
const axeSource = await readFile(
  path.resolve(
    root,
    "../../tmp/catalog-readiness-tools/node_modules/axe-core/axe.min.js",
  ),
  "utf8",
);
const errors = [],
  remoteRequests = [],
  failures = [];
const record = {
  checkedAt: new Date().toISOString(),
  widths: [320, 390, 768, 1024, 1440],
  pages: ["index.html", "sample.html", "review.html", "sources.html"],
  localLinks: 0,
  externalSubmissions: 0,
  accessibility: [],
};
try {
  const context = await browser.newContext();
  await context.route("**/*", (route) => {
    if (new URL(route.request().url()).origin !== origin) {
      remoteRequests.push(route.request().url());
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("response", (r) => {
    if (r.status() >= 400) failures.push(`${r.status()} ${r.url()}`);
  });
  // A single HTML source produces both the web sample and the downloadable PDF.
  await page.goto(origin + "/sample.html");
  await page.addStyleTag({
    content:
      [400, 550, 650, 700]
        .map(
          (weight) =>
            `@font-face{font-family:InterPrint;src:url('${origin}/fonts/inter-print-${weight}.ttf') format('truetype');font-weight:${weight};font-style:normal} `,
        )
        .join("") + "body{font-family:InterPrint,sans-serif}",
  });
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    // Local source filenames remain visible, but an exported PDF must not link to an ephemeral test server.
    for (const a of document.querySelectorAll(".report-sheet a[href]")) {
      if (new URL(a.href).origin === location.origin)
        a.replaceWith(document.createTextNode(a.textContent));
    }
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
    );
    while (walker.nextNode())
      walker.currentNode.textContent = walker.currentNode.textContent.replace(
        /[\u2010-\u2015\u2212]/g,
        "-",
      );
  });
  const pdfDirectory = path.resolve(root, "../../output/pdf");
  await page.emulateMedia({ media: "print" });
  assert.equal(await page.locator(".skip").count(), 1);
  assert.equal(await page.locator(".skip").isVisible(), false);
  await mkdir(pdfDirectory, { recursive: true });
  const pdf = path.join(pdfDirectory, "space-catalog-readiness-sample.pdf");
  await page.pdf({
    path: pdf,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    tagged: true,
    outline: true,
  });
  await copyFile(pdf, path.join(root, "preview/sample-report.pdf"));
  await page.emulateMedia({ media: "screen" });
  const evidenceDirectory = path.join(
    pdfDirectory,
    "space-catalog-readiness-evidence",
  );
  await mkdir(evidenceDirectory, { recursive: true });
  for (const name of [
    "synthetic-receipts.csv",
    "synthetic-summary.csv",
    "synthetic-track-register.csv",
    "synthetic-document-inventory.csv",
  ])
    await copyFile(
      path.join(root, "preview", name),
      path.join(evidenceDirectory, name),
    );
  record.pdf = pdf;
  for (const name of record.pages) {
    for (const width of record.widths) {
      await page.setViewportSize({ width, height: 1000 });
      const response = await page.goto(`${origin}/${name}`, {
        waitUntil: "networkidle",
      });
      assert.equal(response.status(), 200);
      assert.match(response.headers()["x-robots-tag"], /noindex/);
      assert.match(
        await page.locator('meta[name="robots"]').getAttribute("content"),
        /noindex/,
      );
      assert.equal(await page.locator("h1").count(), 1);
      assert.equal(
        await page.locator("form").count(),
        0,
        "No customer/payment forms allowed",
      );
      assert.equal(await page.locator('input[type="file"]').count(), 0);
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
        `Overflow ${name} ${width}`,
      );
      assert(await page.evaluate(() => document.fonts.check("16px Inter")));
      if ([390, 1440].includes(width)) {
        await page.evaluate(axeSource);
        const audit = await page.evaluate(async () => {
          const result = await axe.run(document, {
            runOnly: {
              type: "tag",
              values: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"],
            },
          });
          return {
            violations: result.violations.map((v) => ({
              id: v.id,
              impact: v.impact,
              nodes: v.nodes.map((n) => ({
                target: n.target,
                summary: n.failureSummary,
              })),
            })),
            incomplete: result.incomplete.map((v) => v.id),
          };
        });
        record.accessibility.push({ page: name, width, ...audit });
        assert.deepEqual(
          audit.violations,
          [],
          `Accessibility ${name} ${width}: ${JSON.stringify(audit.violations)}`,
        );
      }
      if ([390, 1440].includes(width)) {
        await page.screenshot({
          path: path.join(qa, `${name.replace(".html", "")}-${width}.png`),
          fullPage: true,
        });
        if (name === "index.html")
          await page.screenshot({
            path: path.join(qa, `offer-${width}-viewport.png`),
          });
      }
    }
    const links = await page
      .locator("a[href]")
      .evaluateAll((nodes) => nodes.map((a) => a.getAttribute("href")));
    for (const href of new Set(links)) {
      const url = new URL(href, `${origin}/${name}`);
      if (url.origin !== origin) continue;
      const response = await context.request.get(url.href);
      assert.equal(response.status(), 200, `Broken ${href}`);
      if (url.hash) {
        const content = await response.text();
        assert(
          content.includes(`id="${url.hash.slice(1)}"`),
          `Missing anchor ${url.hash}`,
        );
      }
      record.localLinks++;
    }
  }
  await page.goto(origin + "/index.html");
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(":focus").innerText(), "Skip to content");
  await page.keyboard.press("Enter");
  const faq = page.getByText("Why pay when the purchase review is free?", {
    exact: true,
  });
  await faq.focus();
  await faq.press("Enter");
  assert(
    await page
      .getByText("Only if you want a separate, reusable deliverable.", {
        exact: false,
      })
      .isVisible(),
  );
  await page
    .getByRole("link", { name: "Read the sample report" })
    .press("Enter");
  assert.equal(new URL(page.url()).pathname, "/sample.html");
  await page.goto(origin + "/review.html");
  assert.equal(await page.locator("html").getAttribute("lang"), "sv");
  for (const selector of [".draft-strip", ".site-header", ".skip", ".end-note"])
    assert.equal(await page.locator(selector).getAttribute("lang"), "en");
  assert.match(await page.locator("#contribution").innerText(), /10,22/);
  await page.locator("#minutes").fill("90");
  assert.match(await page.locator("#contribution").innerText(), /[−-]1,03/);
  await page.locator("#gross").fill("149");
  assert.match(await page.locator("#contribution").innerText(), /35,22/);
  await page.locator("#gross").fill("");
  assert.equal(await page.locator("#contribution").innerText(), "Ej beräknat");
  assert.equal(
    await page.locator("#gross").getAttribute("aria-invalid"),
    "true",
  );
  await page.locator("#gross").fill("149");
  await page.locator("#taxPercent").fill("101");
  assert.equal(await page.locator("#contribution").innerText(), "Ej beräknat");
  await page.locator("#taxPercent").fill("25");
  await page.locator("#hourlyCost").fill("0");
  assert.match(
    await page.locator("#break-even").innerText(),
    /kan inte beräknas/,
  );
  await page.locator("#gross").fill("1");
  assert.match(await page.locator("#break-even").innerText(), /täcker inte/);
  assert.equal(await page.evaluate(() => localStorage.length), 0);
  assert.equal(await page.evaluate(() => sessionStorage.length), 0);
  assert.equal((await context.cookies()).length, 0);
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const staticPage = await noJs.newPage();
  for (const name of record.pages) {
    await staticPage.goto(`${origin}/${name}`);
    assert.equal(await staticPage.locator("h1").count(), 1);
    assert((await staticPage.locator("main").innerText()).length > 1000);
  }
  await staticPage.goto(origin + "/review.html");
  assert(await staticPage.locator("noscript > p").isVisible());
  assert.match(
    await staticPage.locator("noscript > p").innerText(),
    /JavaScript är avstängt/,
  );
  await staticPage.goto(origin + "/sample.html");
  assert.equal(await staticPage.locator(".report-sheet").count(), 4);
  await noJs.close();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(origin + "/index.html");
  assert.equal(
    await page
      .locator(".reveal")
      .first()
      .evaluate((el) => getComputedStyle(el).animationName),
    "none",
  );
  assert.equal((await context.request.post(origin + "/")).status(), 405);
  assert.equal(
    (await context.request.get(origin + "/../README.md")).status(),
    404,
  );
  assert.equal(
    (await context.request.get(origin + "/%2e%2e%2fREADME.md")).status(),
    404,
  );
  assert.equal(
    (await context.request.get(origin + "/fonts/../../README.md")).status(),
    404,
  );
  const head = await context.request.head(origin + "/sample.html");
  assert.equal(head.status(), 200);
  assert.equal((await head.body()).length, 0);
  assert.match(head.headers()["content-security-policy"], /connect-src 'none'/);
  for (const file of [
    "index.html",
    "sample.html",
    "review.html",
    "sources.html",
  ]) {
    const html = await readFile(path.join(root, "preview", file), "utf8");
    assert(
      !/https?:\/\/[^"']+\.(?:js|css)["']/.test(html),
      "External runtime dependency",
    );
    assert(
      !/buy\.stripe\.com|checkout\.stripe\.com|formspree\.io/.test(html),
      "No checkout/receiver wiring",
    );
  }
  assert.deepEqual(remoteRequests, []);
  assert.deepEqual(errors, []);
  assert.deepEqual(failures, []);
  Object.assign(record, {
    keyboard: true,
    noJavaScript: true,
    reducedMotion: true,
    formSubmissionRejected: true,
    pathTraversalRejected: true,
    allArithmeticUiCases: true,
    noStorageOrCookies: true,
    remoteRequests,
    errors,
    failures,
  });
  await writeFile(
    path.join(qa, "browser-results.json"),
    JSON.stringify(record, null, 2),
  );
  console.log(JSON.stringify(record, null, 2));
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
