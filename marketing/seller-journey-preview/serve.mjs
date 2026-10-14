import http from "node:http";
import { readFile, realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const assets = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/index.html", ["index.html", "text/html; charset=utf-8"]],
  ["/styles.css", ["styles.css", "text/css; charset=utf-8"]],
  ["/app.mjs", ["app.mjs", "text/javascript; charset=utf-8"]],
  ["/model.mjs", ["model.mjs", "text/javascript; charset=utf-8"]],
  [
    "/inter.woff2",
    ["../catalog-readiness-draft/preview/fonts/inter.woff2", "font/woff2"],
  ],
]);
export function createServer() {
  return http.createServer(async (req, res) => {
    res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "no-referrer");
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'none'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'",
    );
    if (!["GET", "HEAD"].includes(req.method)) {
      res.writeHead(405, { Allow: "GET, HEAD" });
      res.end("This preview does not accept submissions.");
      return;
    }
    try {
      const pathname = new URL(req.url, "http://127.0.0.1").pathname;
      const asset = assets.get(pathname);
      if (!asset) {
        res.writeHead(404);
        res.end("Not part of this preview.");
        return;
      }
      const file = await realpath(path.join(root, asset[0]));
      const body = await readFile(file);
      res.setHeader("Content-Type", asset[1]);
      res.setHeader("Content-Length", body.length);
      res.end(req.method === "HEAD" ? undefined : body);
    } catch {
      res.writeHead(500);
      res.end("Preview asset unavailable.");
    }
  });
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const port = Number(process.env.PORT || 4193);
  if (!Number.isInteger(port) || port < 1024 || port > 65535)
    throw new Error("Invalid local port");
  createServer().listen(port, "127.0.0.1", () =>
    console.log(
      `Seller journey preview: http://127.0.0.1:${port}/ (local, fictional data only)`,
    ),
  );
}
