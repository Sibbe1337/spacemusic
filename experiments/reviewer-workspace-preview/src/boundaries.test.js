// @vitest-environment node
import { it, expect } from "vitest";
import { readFileSync } from "node:fs";

const read = (p) => readFileSync(new URL(p, import.meta.url), "utf8");
const app = read("./App.jsx") + read("./review.js");

it("has no network, upload, persistence, analytics or HTML injection code", () => {
  for (const forbidden of [
    /\bfetch\s*\(/,
    /XMLHttpRequest/,
    /WebSocket/,
    /sendBeacon/,
    /localStorage/,
    /sessionStorage/,
    /indexedDB/,
    /document\.cookie/,
    /dangerouslySetInnerHTML/,
    /type=["']file/,
    /mailto:/,
  ])
    expect(app).not.toMatch(forbidden);
});
it("uses only local fonts and the existing local brand asset", () => {
  expect(read("./styles.css")).not.toMatch(/https?:|@import/);
  expect(app).not.toMatch(/https?:\/\//);
  expect(read("../index.html")).not.toMatch(/https?:\/\//);
});
it("marks the preview as non-indexable and keeps it local", () => {
  expect(read("../index.html")).toContain("noindex,nofollow,noarchive");
  const config = read("../vite.config.mjs");
  expect(config).toContain("127.0.0.1");
  expect(config).toContain("no-store");
  expect(config).toContain("X-Robots-Tag");
});
