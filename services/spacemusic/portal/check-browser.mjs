import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import net from "node:net";
import http from "node:http";
import { fileURLToPath } from "node:url";
import { playwrightModule } from "../../../scripts/funnel-support.mjs";

const root = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(root, "../../..");
const qa = path.join(root, "qa");
await mkdir(qa, { recursive: true });
const directory = await mkdtemp(
  path.join(os.tmpdir(), "space-portal-browser-"),
);
const socket = net.createServer();
await new Promise((resolve) => socket.listen(0, "127.0.0.1", resolve));
const port = socket.address().port;
await new Promise((resolve) => socket.close(resolve));
const origin = `http://127.0.0.1:${port}`;
const server = spawn(
  "python3",
  [
    "-m",
    "services.spacemusic.portal.app",
    "--local",
    "--port",
    String(port),
    "--directory",
    directory,
  ],
  { cwd: repo, stdio: ["ignore", "pipe", "pipe"] },
);
let serverLog = "";
server.stderr.on("data", (data) => {
  serverLog += data;
});
const { chromium } = await import(playwrightModule);
const browser = await chromium.launch({ channel: "chrome", headless: true });
const results = {
  checkedAt: new Date().toISOString(),
  widths: [320, 390, 768, 1440],
  screens: [],
  accessibility: [],
  errors: [],
  remoteRequests: [],
  checks: [],
};
const axe = await readFile(
  path.join(
    repo,
    "tmp/catalog-readiness-tools/node_modules/axe-core/axe.min.js",
  ),
  "utf8",
);
const context = await browser.newContext();
let failSave = false;
let mailPreviewLink = "";
// A real second loopback site keeps Chrome's Fetch Metadata headers intact.
const mailServer = http.createServer((_request, response) => {
  response.writeHead(200, { "Content-Type": "text/html" });
  response.end(
    `<a href="${mailPreviewLink}">Open single-use sign-in link</a><a href="${origin}/api/session">External API link</a>`,
  );
});
await new Promise((resolve) => mailServer.listen(0, "127.0.0.1", resolve));
const mailPreview = `http://localhost:${mailServer.address().port}/`;
const routeHandler = (route) => {
  const req = route.request();
  if (new URL(req.url()).origin !== origin) {
    results.remoteRequests.push(req.url());
    return route.abort();
  }
  if (failSave && req.url().endsWith("/catalog") && req.method() === "PUT") {
    failSave = false;
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Synthetic connection failure. Try again.",
      }),
    });
  }
  return route.continue();
};
await context.route("**/*", routeHandler);
context.on("request", (request) => {
  if (
    ![origin, new URL(mailPreview).origin].includes(
      new URL(request.url()).origin,
    )
  ) {
    results.remoteRequests.push(request.url());
  }
});
const page = await context.newPage();
page.on("pageerror", (e) => results.errors.push(e.message));
const action = (name) => page.locator(`[data-action="${name}"]`).click();
const visibleText = (text) =>
  page.locator("main").getByText(text, { exact: false });
async function ready() {
  for (let i = 0; i < 80; i++) {
    if (server.exitCode !== null) throw new Error(serverLog);
    try {
      if ((await fetch(origin)).ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("Local server did not start");
}
async function audit(name) {
  await page.evaluate(() => document.fonts.ready);
  for (const width of results.widths) {
    await page.setViewportSize({ width, height: 1000 });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
      `${name} overflow ${width}`,
    );
    if ([390, 1440].includes(width)) {
      await page.evaluate(axe);
      const report = await page.evaluate(async () => {
        const r = await axe.run(document, {
          runOnly: {
            type: "tag",
            values: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"],
          },
        });
        return {
          violations: r.violations.map((v) => ({
            id: v.id,
            nodes: v.nodes.map((n) => n.target),
          })),
          incomplete: r.incomplete.map((v) => v.id),
        };
      });
      results.accessibility.push({ screen: name, width, ...report });
      assert.deepEqual(
        report.violations,
        [],
        JSON.stringify({ name, width, report }),
      );
      await page.locator("#main").focus();
      await page.screenshot({
        path: path.join(qa, `${name}-${width}.png`),
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  results.screens.push(name);
  console.log(`Checked ${name}`);
}
try {
  await ready();
  await page.goto(origin);
  await page.locator("#login-form").waitFor();
  assert.equal(
    await page.locator('[data-action="owner-email"]').isDisabled(),
    true,
  );
  await audit("sign-in");
  await page.reload();
  await page.locator("#login-form").waitFor();
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(":focus").innerText(), "Skip to content");
  await page.locator("summary").click();
  await action("seed");
  await visibleText("Fictional application is ready.").waitFor();
  assert.equal(await page.locator("#email").inputValue(), "alex@example.com");
  await page
    .locator("#login-form button[type=submit], #login-form button:not([type])")
    .click();
  await visibleText("If an application matches this address,").waitFor();
  await page.locator("summary").click();
  await action("mailbox");
  await page
    .getByRole("link", { name: "Open single-use sign-in link" })
    .waitFor();
  const link = await page
    .getByRole("link", { name: "Open single-use sign-in link" })
    .getAttribute("href");
  mailPreviewLink = link;
  // Interception omits browser-generated Fetch Metadata in this Chrome runtime.
  await context.unroute("**/*", routeHandler);
  await page.goto(mailPreview);
  const deniedNavigation = page.waitForResponse(`${origin}/api/session`);
  await page.getByRole("link", { name: "External API link" }).click();
  const denied = await deniedNavigation;
  assert.equal(denied.status(), 403);
  assert.deepEqual(await denied.json(), {
    detail: "Cross-site request denied",
  });
  await page.goto(mailPreview);
  const entryResponse = page.waitForResponse(`${origin}/`);
  await page
    .getByRole("link", { name: "Open single-use sign-in link" })
    .click();
  const entry = await entryResponse;
  assert.equal(entry.status(), 200);
  const entryHeaders = await entry.request().allHeaders();
  assert.equal(entryHeaders["sec-fetch-site"], "cross-site");
  assert.equal(entryHeaders["sec-fetch-mode"], "navigate");
  assert.equal(entryHeaders["sec-fetch-dest"], "document");
  await page.locator("[data-action=consume]").waitFor();
  assert.equal(new URL(page.url()).hash, "");
  assert.equal((await context.cookies(origin)).length, 0);
  await audit("confirm-sign-in");
  await action("consume");
  await page.locator("#catalog-form").waitFor();
  await context.route("**/*", routeHandler);
  assert.equal(await page.evaluate(() => document.cookie), "");
  assert.equal(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
    0,
  );
  const cookie = (await context.cookies()).find(
    (c) => c.name === "space_portal_local_session",
  );
  assert(cookie.httpOnly);
  assert.equal(cookie.sameSite, "Strict");
  await page.locator("#catalog-form button:not([type])").click();
  await page.locator("[aria-invalid=true]").first().waitFor();
  await action("sample-catalog");
  await page.locator("#tracks").fill("25");
  failSave = true;
  await page.locator("#catalog-form button:not([type])").click();
  await visibleText("Synthetic connection failure.").waitFor();
  assert.equal(await page.locator("#tracks").inputValue(), "25");
  await audit("catalog");
  await page.locator("#catalog-form button:not([type])").click();
  await page
    .getByRole("heading", { name: "Bring the source, not just the total." })
    .waitFor();
  await page.locator("input[data-kind=royalties]").setInputFiles({
    name: "synthetic-unknown.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("synthetic,unknown\n1,2\n"),
  });
  await page.getByText("Quarantined. Scanning is not configured.").waitFor();
  assert.equal(
    await page.getByRole("link", { name: "Download your test file" }).count(),
    0,
  );
  await page.locator('[data-action^="remove:"]').click();
  await page.locator("input[data-kind=royalties]").waitFor();
  await action("fixture:royalties");
  await page
    .getByText("Known test fixture. Not commercially verified.")
    .waitFor();
  await action("fixture:tracks");
  await page.locator(".uploaded").nth(1).waitFor();
  await audit("documents");
  await page.reload();
  await page
    .getByRole("heading", { name: "Bring the source, not just the total." })
    .waitFor();
  assert.equal(await page.locator(".uploaded").count(), 2);
  await page
    .getByRole("button", { name: "Review your package", exact: true })
    .click();
  await audit("review");
  await action("submit");
  await page
    .getByRole("heading", { name: "Your package is in the review stage." })
    .waitFor();
  await audit("under-review");
  await page.locator("summary").click();
  await action("question");
  await page.locator("#reply-form").waitFor();
  await audit("clarification");
  await page
    .locator("#reply")
    .fill("Fictional own share. <img src=x onerror=alert(1)>");
  await page.locator("#reply-form button").click();
  await page
    .getByRole("heading", { name: "Your clarification", exact: true })
    .waitFor();
  assert.equal(await page.locator(".message-body img").count(), 0);
  await page.reload();
  await page
    .getByRole("heading", { name: "Your clarification", exact: true })
    .waitFor();
  assert.match(await page.locator("main").innerText(), /Fictional own share/);
  await action("logout");
  await page.locator("#login-form").waitFor();
  await page.reload();
  await page.locator("#login-form").waitFor();
  assert.equal(
    (await context.cookies()).filter(
      (c) => c.name === "space_portal_local_session",
    ).length,
    0,
  );
  await page.goto(link);
  await page.locator("[data-action=consume]").waitFor();
  await action("consume");
  await visibleText(
    "This sign-in link is invalid, expired or already used",
  ).waitFor();
  assert.equal(await page.locator("#catalog-form").count(), 0);
  assert.equal(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
    0,
  );
  // The owner-mail UI is exercised with simulated provider responses only.
  // The server used by this suite never loads a real credential.
  const ownerRequests = [];
  let ownerAccepted = false;
  await context.route(`${origin}/api/development/email-test`, async (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        json: {
          enabled: true,
          recipient: "hello@spacemusic.io",
          last_test: ownerRequests.length
            ? {
                request_id: ownerRequests.at(-1).request_id,
                accepted: ownerAccepted,
                expired: false,
              }
            : null,
        },
      });
    }
    ownerRequests.push(route.request().postDataJSON());
    await new Promise((resolve) => setTimeout(resolve, 200));
    if (ownerRequests.length === 1) {
      return route.fulfill({
        status: 502,
        json: { detail: "Synthetic Resend timeout. Retry the same request." },
      });
    }
    ownerAccepted = true;
    return route.fulfill({
      status: 200,
      json: {
        status: "accepted_by_provider",
        message:
          "Resend accepted the test email. Inbox delivery is not yet verified.",
      },
    });
  });
  await page.goto(origin);
  await page.locator("#login-form").waitFor();
  await page.locator("summary").click();
  await audit("owner-email-test");
  await page.locator('[data-action="owner-email"]').dblclick();
  await visibleText("Synthetic Resend timeout").waitFor();
  assert.equal(
    ownerRequests.length,
    1,
    "A double click must not send two requests",
  );
  assert.equal(
    await page.locator(".preview-controls").getAttribute("open"),
    "",
  );
  await page.reload();
  await page
    .getByRole("button", { name: "Retry the same email test" })
    .waitFor();
  await action("owner-email");
  await visibleText("Inbox delivery is not yet verified").waitFor();
  assert.deepEqual(
    ownerRequests[0],
    ownerRequests[1],
    "Retries keep the same idempotency key",
  );
  assert.equal(
    await page.locator('[data-action="owner-email"]').isDisabled(),
    true,
  );
  await page.reload();
  await page.getByRole("button", { name: "Accepted by Resend" }).waitFor();
  assert.equal(
    await page.locator('[data-action="owner-email"]').isDisabled(),
    true,
  );
  await action("new-owner-email");
  assert.equal(
    await page.locator('[data-action="owner-email"]').isDisabled(),
    false,
  );
  assert.equal(
    ownerRequests.length,
    2,
    "Reload/new-test preparation must not send automatically",
  );
  assert.equal(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
    0,
  );
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const staticPage = await noJs.newPage();
  await staticPage.goto(origin);
  assert.match(
    await staticPage.locator("main").innerText(),
    /requires JavaScript/,
  );
  assert.equal(await staticPage.locator("form").count(), 0);
  await noJs.close();
  assert.deepEqual(results.errors, []);
  assert.deepEqual(results.remoteRequests, []);
  results.checks = [
    "actual local API round trips",
    "local mailbox and explicit one-time link confirmation",
    "cross-site mail link click opens the shell; cross-site API navigation remains denied",
    "fragment removed before authentication",
    "HttpOnly SameSite cookie and no browser storage",
    "keyboard and responsive reflow",
    "server validation and connection-failure retry",
    "unknown files quarantined",
    "fixture upload, remove, download link and persistence",
    "submit and human-review clarification",
    "escaped user text",
    "reload and sign-out revocation",
    "consumed link rejection",
    "no-JavaScript explanation",
    "no external requests",
    "owner email UI opt-in, simulated timeout/reload/retry and double-click prevention",
  ];
  await writeFile(
    path.join(qa, "browser-results.json"),
    JSON.stringify(results, null, 2),
  );
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
  await new Promise((resolve) => mailServer.close(resolve));
  server.kill("SIGTERM");
  await new Promise((resolve) => {
    if (server.exitCode !== null) return resolve();
    server.once("exit", resolve);
  });
}
