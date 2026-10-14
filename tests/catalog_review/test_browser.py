"""Real Chromium -> real UI -> ASGI -> disposable PostgreSQL; synthetic only.

The temporary loopback bridge is a test transport, not a portal server. Every
browser request is intercepted and the only app origin remains review.test.
No fixture endpoint or credential is added to the application itself.
"""

import base64
import json
import os
import secrets
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from urllib.parse import urlsplit

from conftest import owner_cursor, receipt
from fastapi.testclient import TestClient
from test_review import reviewer

from services.catalog_review.http import create_test_app
from services.catalog_review.workers import scan_document


def test_browser_customer_and_reviewer_journey(backend, tmp_path):
    workspace = backend.ingest(receipt())["workspace_id"]
    invitation = backend.claim_invitation(workspace)["url"]
    staff = reviewer(backend, workspace)
    bridge_key = secrets.token_urlsafe(32)
    lock = Lock()
    failures = []

    class SyntheticScanner:
        def inspect(self, **kwargs):
            return True

    with TestClient(
        create_test_app(backend, document_store=backend.test_blobs),
        base_url="https://review.test",
    ) as client:

        class Bridge(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.headers.get("x-test-bridge") != bridge_key:
                    self.send_error(403)
                    return
                length = int(self.headers.get("content-length", "0"))
                if not 0 < length < 2 * 1024 * 1024:
                    self.send_error(413)
                    return
                try:
                    with lock:
                        request = json.loads(self.rfile.read(length))
                        if self.path == "/scan-synthetic":
                            with owner_cursor(backend) as cur:
                                cur.execute(
                                    "SELECT document_id FROM documents WHERE workspace_id=%s",
                                    (workspace,),
                                )
                                ids = [
                                    str(row["document_id"]) for row in cur.fetchall()
                                ]
                            for document in ids:
                                scan_document(
                                    backend,
                                    workspace,
                                    document,
                                    backend.test_blobs,
                                    SyntheticScanner(),
                                )
                            result = {"ok": True}
                        elif self.path == "/expire-synthetic":
                            backend.clock.advance(3601)
                            result = {"ok": True}
                        elif self.path == "/asgi":
                            parsed = urlsplit(request["url"])
                            assert (
                                parsed.scheme == "https"
                                and parsed.netloc == "review.test"
                            )
                            client.cookies.clear()
                            response = client.request(
                                request["method"],
                                request["url"],
                                headers=request["headers"],
                                content=base64.b64decode(request.get("body", "")),
                                follow_redirects=False,
                            )
                            result = {
                                "status": response.status_code,
                                "headers": dict(response.headers),
                                "body": base64.b64encode(response.content).decode(),
                            }
                        else:
                            raise ValueError("Unknown test transport operation")
                    body = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as error:
                    failures.append(type(error).__name__)
                    self.send_error(500)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Bridge)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = {
                **os.environ,
                "SPACE_TEST_BRIDGE": f"http://127.0.0.1:{server.server_port}",
                "SPACE_TEST_BRIDGE_KEY": bridge_key,
                "SPACE_TEST_INVITATION": invitation,
                "SPACE_TEST_REVIEWER": staff,
                "SPACE_TEST_SCREENSHOTS": str(tmp_path),
                "SPACE_TEST_NOW": backend.clock().isoformat(),
            }
            result = subprocess.run(
                ["node", "tests/catalog_review/browser.mjs"],
                env=env,
                capture_output=True,
                text=True,
                timeout=100,
            )
            assert not failures, failures
            assert result.returncode == 0, result.stdout + result.stderr
            assert "Browser journey passed" in result.stdout
            assert (tmp_path / "workspace-desktop.png").exists()
            assert (tmp_path / "workspace-mobile.png").exists()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    with owner_cursor(backend) as cur:
        cur.execute(
            "SELECT snapshot FROM submissions WHERE workspace_id=%s", (workspace,)
        )
        snapshot = cur.fetchone()["snapshot"]
        assert snapshot["draft"]["rights"][0]["share_percent"] == "50"
        assert snapshot["missing_evidence"] is False
        assert snapshot["rights_verified"] is False
        cur.execute("SELECT count(*) AS count FROM review_questions")
        assert cur.fetchone()["count"] == 2
        cur.execute("SELECT count(*) AS count FROM review_replies")
        assert cur.fetchone()["count"] == 2
        cur.execute("SELECT version,documents FROM review_supplements")
        supplement = cur.fetchone()
        assert supplement["version"] == 1
        assert supplement["documents"][0]["filename"] == "follow-up.csv"
        assert len(snapshot["documents"]) == 1
