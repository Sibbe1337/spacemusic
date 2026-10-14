import secrets
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from conftest import receipt
from fastapi.testclient import TestClient

from services.catalog_review.http import ASSETS, create_application, create_test_app


def test_only_explicit_ui_assets_are_served_with_private_headers(backend):
    with TestClient(
        create_test_app(backend), base_url="https://review.test"
    ) as browser:
        for path in ASSETS:
            response = browser.get(path)
            assert response.status_code == 200, path
            assert response.headers["cache-control"] == "no-store"
            assert "noindex" in response.headers["x-robots-tag"]
            assert "connect-src 'self'" in response.headers["content-security-policy"]
            assert "unsafe-inline" not in response.headers["content-security-policy"]
        for path in [
            "/workspace/schema.sql",
            "/workspace/fixtures.mjs",
            "/workspace/../schema.sql",
            "/.env",
            "/api/test/login",
        ]:
            assert browser.get(path).status_code == 404


def test_email_navigation_opens_shell_but_does_not_consume_invitation(backend):
    workspace = backend.ingest(receipt())["workspace_id"]
    token = backend.claim_invitation(workspace)["url"].split("#invitation=")[1]
    with TestClient(
        create_test_app(backend), base_url="https://review.test"
    ) as browser:
        headers = {
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document",
        }
        assert browser.get("/workspace/", headers=headers).status_code == 200
        assert browser.get("/api/portal/workspace", headers=headers).status_code == 403
        assert (
            browser.get(
                "/workspace/", headers={"sec-fetch-site": "cross-site"}
            ).status_code
            == 403
        )
        assert (
            browser.get("/workspace/?invitation=" + token, headers=headers).status_code
            == 400
        )
        assert (
            browser.post(
                "/api/portal/session",
                json={"token": token},
                headers={"origin": "https://review.test"},
            ).status_code
            == 200
        )


def test_no_fixture_import_external_scripts_or_local_storage_in_connected_ui():
    root = Path("services/catalog_review_ui")
    for filename in ["app.mjs", "client.mjs", "index.html"]:
        source = (root / filename).read_text()
        assert "fixtures.mjs" not in source
        assert "localStorage" not in source
        assert "sessionStorage" not in source
        assert "plausible" not in source.lower()
        assert "https://" not in source


def test_production_shells_have_explicit_production_copy_and_private_headers(backend):
    # Asset-only test: no customer identity, credential or provider is supplied.
    backend.settings = replace(
        backend.settings,
        mode="production",
        origin="https://review.spacemusic.io",
        source_identity_key=secrets.token_bytes(32),
        generation=str(uuid4()),
    )
    with TestClient(
        create_application(backend), base_url=backend.settings.origin
    ) as browser:
        for path in ("/workspace/", "/staff/"):
            response = browser.get(path)
            assert response.status_code == 200
            assert 'data-environment="production"' in response.text
            assert "Synthetic information only" not in response.text
            assert "noindex" in response.headers["x-robots-tag"]
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["strict-transport-security"] == "max-age=31536000"
