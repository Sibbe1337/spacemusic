import http from "node:http";
import { readFile, realpath } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = await realpath(
  path.join(path.dirname(fileURLToPath(import.meta.url)), "preview"),
);
const mime = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".csv": "text/csv; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".pdf": "application/pdf",
  ".txt": "text/plain; charset=utf-8",
};
export function createServer() {
  return http.createServer(async (req, res) => {
    res.setHeader("X-Robots-Tag", "noindex, nofollow, noarchive");
    res.setHeader("Cache-Control", "no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "no-referrer");
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'none'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'",
    );
    if (!["GET", "HEAD"].includes(req.method)) {
      res.writeHead(405, { Allow: "GET, HEAD" });
      res.end("No submissions accepted");
      return;
    }
    try {
      const url = new URL(req.url, "http://127.0.0.1");
      let relative = decodeURIComponent(url.pathname);
      if (relative === "/") relative = "/index.html";
      const file = await realpath(path.resolve(root, "." + relative));
      if (!file.startsWith(root + path.sep)) throw new Error("Outside preview");
      const body = await readFile(file);
      res.setHeader(
        "Content-Type",
        mime[path.extname(file)] || "application/octet-stream",
      );
      res.setHeader("Content-Length", body.length);
      res.end(req.method === "HEAD" ? undefined : body);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  });
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const port = Number(process.env.PORT || 4186);
  if (!Number.isInteger(port) || port < 1024 || port > 65535)
    throw new Error("Invalid local port");
  const server = createServer();
  server.listen(port, "127.0.0.1", () =>
    console.log(
      `Private draft: http://127.0.0.1:${port}/ (no data submission)`,
    ),
  );
}
