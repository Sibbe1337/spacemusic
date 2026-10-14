"""Loopback-only synthetic acceptance preview backed by disposable PostgreSQL.

Never included in the production image. No real customer input, mail, storage,
provider calls, persistent database, cookies, or production credentials.
"""

import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/catalog_review"))

import conftest
from fastapi.testclient import TestClient
from test_dealflow import make_case, record

from services.catalog_review.http import ASSETS, COOKIE, create_test_app

ORIGIN = "http://127.0.0.1:4208"


def main():
    cluster = conftest.cluster.__wrapped__()
    backend = None
    server = None
    try:
        backend = conftest.backend.__wrapped__(next(cluster))
        service = next(backend)
        service.clock.now = datetime.now(timezone.utc)
        _, owner, reviewer, _ = make_case(service)
        example = record(service, reviewer, ready=False)
        example["buyers"][0].update(
            checked_on=service.clock().date().isoformat(),
            expires_on=(service.clock().date() + timedelta(days=30)).isoformat(),
        )
        service.save_dealflow_review(reviewer, example)
        app = create_test_app(service, document_store=service.test_blobs)
        with TestClient(app, base_url="https://review.test") as api:

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_):
                    pass

                def reply(self, status, content, kind="text/plain"):
                    self.send_response(status)
                    self.send_header("Content-Type", kind)
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Robots-Tag", "noindex,nofollow,noarchive")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header(
                        "Content-Security-Policy",
                        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
                    )
                    self.end_headers()
                    self.wfile.write(content)

                def handle_request(self):
                    if (
                        self.headers.get("Host") != "127.0.0.1:4208"
                        or self.headers.get("Origin") not in (None, ORIGIN)
                        or self.headers.get("Sec-Fetch-Site")
                        in ("cross-site", "same-site")
                    ):
                        return self.reply(403, b"Preview origin denied")
                    if "?" in self.path:
                        return self.reply(400, b"Queries are not supported")
                    if self.command == "GET" and self.path in ("/", "/dealflow/"):
                        content = (
                            (ROOT / "services/catalog_review_ui/dealflow.html")
                            .read_text()
                            .replace('data-autostart="true"', 'data-autostart="false"')
                            .replace('src="/dealflow/dealflow.mjs"', 'src="/demo.mjs"')
                            .replace(
                                "Private deal preparation. No automated valuation, outreach or lead resale.",
                                "SYNTHETIC PREVIEW / Fictional cases only. No AI calls, messages or real customer data.",
                            )
                            .replace(
                                "<nav>",
                                '<nav><label>Demo role <select id="demo-role"><option value="reviewer">Reviewer</option><option value="owner">Catalog owner</option></select></label>',
                                1,
                            )
                        )
                        return self.reply(
                            200, content.encode(), "text/html; charset=utf-8"
                        )
                    if self.command == "GET" and self.path == "/demo.mjs":
                        return self.reply(
                            200,
                            (
                                ROOT / "experiments/dealflow-preview/demo.mjs"
                            ).read_bytes(),
                            "text/javascript",
                        )
                    if self.command == "GET" and self.path == "/workspace/":
                        return self.reply(
                            200,
                            (
                                ROOT / "experiments/dealflow-preview/handoff.html"
                            ).read_bytes(),
                            "text/html; charset=utf-8",
                        )
                    if self.command == "GET" and self.path in ASSETS:
                        filename, kind = ASSETS[self.path]
                        return self.reply(200, (ROOT / filename).read_bytes(), kind)
                    if not self.path.startswith("/api/portal/"):
                        return self.reply(404, b"Not found")
                    if self.path not in (
                        "/api/portal/workspace",
                        "/api/portal/dealflow",
                        "/api/portal/session",
                    ) and not self.path.startswith("/api/portal/dealflow/"):
                        return self.reply(404, b"Not part of this synthetic preview")
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 <= length <= 65536:
                            raise ValueError()
                    except ValueError:
                        return self.reply(413, b"Body too large")
                    if self.command != "GET" and self.headers.get("Origin") != ORIGIN:
                        return self.reply(403, b"Origin required")
                    # Test identity selection exists ONLY in this loopback fixture.
                    role = self.headers.get("X-Demo-Role")
                    if role not in ("owner", "reviewer"):
                        return self.reply(403, b"Synthetic role required")
                    token = owner if role == "owner" else reviewer
                    api.cookies.clear()
                    api.cookies.set(COOKIE, token)
                    result = api.request(
                        self.command,
                        self.path,
                        content=self.rfile.read(length),
                        headers={
                            "Origin": "https://review.test",
                            "Sec-Fetch-Site": "same-origin",
                            "Content-Type": self.headers.get(
                                "Content-Type", "application/json"
                            ),
                            "X-CSRF-Token": self.headers.get("X-CSRF-Token", ""),
                        },
                    )
                    return self.reply(
                        result.status_code,
                        result.content,
                        result.headers.get("content-type", "application/json"),
                    )

                do_GET = handle_request
                do_POST = handle_request
                do_DELETE = handle_request

            server = HTTPServer(("127.0.0.1", 4208), Handler)
            print("Synthetic dealflow preview: " + ORIGIN, flush=True)
            server.serve_forever()
    finally:
        if server:
            server.server_close()
        if backend:
            backend.close()
        cluster.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
