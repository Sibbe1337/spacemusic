from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from services.spacemusic.portal.app import COOKIE, Settings, create_app
from services.spacemusic.portal.contracts import (
    FIXTURES,
    verified_signature,
)
from services.spacemusic.portal.store import LocalPortalStore

ORIGIN = "http://127.0.0.1:4194"
SECRET = b"a" * 32
HOOK_SECRET = b"b" * 32
HEADERS = {"Origin": ORIGIN, "X-Space-Request": "portal-v1"}
CATALOG = dict(
    artistLink="https://example.com/music",
    distributor="DistroKid",
    tracks=12,
    rights="masters",
    owned="50",
    offered="50",
    cutoff="2026-08-31",
    revenue="0",
    currency="USD",
    periodStart="2026-08",
    periodEnd="2026-08",
    basis="own-share",
    agreements="unknown",
)


@pytest.fixture
def portal(tmp_path):
    now = [1_789_000_000]
    store = LocalPortalStore(tmp_path / "private", SECRET, lambda: now[0])
    app = create_app(Settings(tmp_path / "private", SECRET, HOOK_SECRET), store)
    with TestClient(app, base_url=ORIGIN, headers=HEADERS) as client:
        yield client, store, now, app
    store.close()


def seed(store, email="alex@example.com"):
    return store.ingest(
        "local-test-form",
        {
            "_date": "2026-09-10T12:00:00Z",
            "email": email,
            "artistLabel": "Fictional <Catalog>",
            "firstName": "Alex",
            "landing_path": "/?email=secret",
            "apply_source_path": "/calculator/",
        },
        {"/", "/calculator/"},
    )[0]


def login(client, store, email="alex@example.com"):
    token = store.issue_link(email)
    response = client.post("/api/auth/consume", json={"token": token})
    assert response.status_code == 200, response.text
    data = client.get("/api/session").json()
    client.headers["X-CSRF-Token"] = data["csrf"]
    return token, response


def upload(client, rid, kind, revision, body=None, name=None):
    fixture_name, fixture_body = FIXTURES[kind]
    return client.post(
        f"/api/reviews/{rid}/documents/{kind}?revision={revision}",
        content=fixture_body if body is None else body,
        headers={
            "X-File-Name": name or fixture_name,
            "Content-Type": "application/octet-stream",
        },
    )


def prepare(client, store):
    rid = seed(store)
    login(client, store)
    response = client.put(
        f"/api/reviews/{rid}/catalog", json={"revision": 0, "catalog": CATALOG}
    )
    assert response.status_code == 200, response.text
    assert upload(client, rid, "royalties", 1).status_code == 200
    assert upload(client, rid, "tracks", 2).status_code == 200
    return rid


def signature(raw, now):
    return (
        f"t={now},v1="
        + hmac.new(
            HOOK_SECRET, str(now).encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
    )


def test_startup_fails_closed(tmp_path):
    for kwargs in (
        {"mode": "production"},
        {"origin": "https://spacemusic.io"},
        {"secret": b"short"},
        {"webhook_secret": SECRET},
        {"directory": Path.cwd() / "tmp/private-not-allowed"},
    ):
        values = dict(directory=tmp_path, secret=SECRET, webhook_secret=HOOK_SECRET)
        values.update(kwargs)
        with pytest.raises(RuntimeError):
            create_app(Settings(**values))


def test_rejected_cli_storage_has_no_side_effects():
    forbidden = Path.cwd() / "tmp/portal-forbidden-regression-directory"
    assert not forbidden.exists()
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.spacemusic.portal.app",
            "--local",
            "--directory",
            str(forbidden),
        ],
        capture_output=True,
        text=True,
    )
    assert process.returncode != 0
    assert not forbidden.exists()


def test_no_release_scratch_dependency(tmp_path, monkeypatch):
    def missing_parse(*args, **kwargs):
        raise FileNotFoundError("Release snapshots are unavailable")

    import xml.etree.ElementTree as ET

    monkeypatch.setattr(ET, "parse", missing_parse)
    app = create_app(Settings(tmp_path, SECRET, HOOK_SECRET))
    app.state.store.close()


def test_webhook_auth_timestamp_form_scope_dedupe_and_metadata(portal):
    client, store, now, _ = portal
    data = {
        "form": "local-test-form",
        "submission": {
            "_date": "2026-09-10T12:00:00Z",
            "email": "alex@example.com",
            "artistLabel": "Synthetic",
            "landing_path": "/?email=secret",
            "apply_source_path": "/calculator/",
        },
    }
    raw = json.dumps(data).encode()
    assert client.post("/api/integrations/formspree", content=raw).status_code == 401
    for timestamp in (now[0] - 301, now[0] + 301):
        assert (
            client.post(
                "/api/integrations/formspree",
                content=raw,
                headers={"Formspree-Signature": signature(raw, timestamp)},
            ).status_code
            == 401
        )
    headers = {"Formspree-Signature": signature(raw, now[0])}
    response = client.post("/api/integrations/formspree", content=raw, headers=headers)
    assert response.status_code == 200, response.text
    rid = response.json()["reference"]
    assert response.json()["created"] is True
    assert (
        client.post("/api/integrations/formspree", content=raw, headers=headers).json()[
            "created"
        ]
        is False
    )
    reordered = json.dumps(data, sort_keys=True).encode()
    assert (
        client.post(
            "/api/integrations/formspree",
            content=reordered,
            headers={"Formspree-Signature": signature(reordered, now[0])},
        ).json()["created"]
        is False
    )
    assert (
        client.post(
            "/api/integrations/formspree", content=raw + b" ", headers=headers
        ).status_code
        == 401
    )
    data["form"] = "another-form"
    changed = json.dumps(data).encode()
    assert (
        client.post(
            "/api/integrations/formspree",
            content=changed,
            headers={"Formspree-Signature": signature(changed, now[0])},
        ).status_code
        == 400
    )
    view = store.view(rid, "alex@example.com")
    assert view["contact"]["landing_path"] == ""
    assert view["contact"]["apply_source_path"] == "/calculator/"
    with pytest.raises(ValueError):
        seed(store, "real-person@gmail.com")


def test_signature_malformed_duplicates_and_raw_bytes():
    raw = b'{"field":"non-ascii: \xc3\xb6"}'
    good = signature(raw, 1000)
    assert verified_signature(HOOK_SECRET, good, raw, 1000)
    for header in (
        "",
        "bad",
        good + ",t=1000",
        good.replace("v1=", "v2="),
        "t=1000,v1=z",
        good.replace("t=1000", "t=-1000"),
    ):
        assert not verified_signature(HOOK_SECRET, header, raw, 1000)
    assert not verified_signature(HOOK_SECRET, good, raw + b" ", 1000)


def test_generic_link_response_and_no_raw_tokens(portal):
    client, store, _, app = portal
    seed(store)
    known = client.post("/api/auth/request", json={"email": "alex@example.com"})
    unknown = client.post("/api/auth/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert "token" not in known.text and "url" not in known.text
    mail = app.state.mailbox[-1]
    token = urlsplit(mail["url"]).fragment.removeprefix("sign-in=")
    row = dict(store.db.execute("SELECT * FROM links").fetchone())
    assert token not in str(row) and len(row["hash"]) == 64
    assert "?" not in mail["url"]


def test_single_use_expiry_and_concurrency(portal):
    client, store, now, _ = portal
    seed(store)
    token = store.issue_link("alex@example.com")
    now[0] += 900
    assert client.post("/api/auth/consume", json={"token": token}).status_code == 401
    token = store.issue_link("alex@example.com")

    def consume(_):
        try:
            return store.consume_link(token)
        except PermissionError:
            return None

    with ThreadPoolExecutor(2) as pool:
        values = list(pool.map(consume, range(2)))
    assert sum(value is not None for value in values) == 1
    assert client.post("/api/auth/consume", json={"token": token}).status_code == 401


def test_cookie_flags_csrf_origin_host_and_idle_expiry(portal):
    client, store, now, _ = portal
    rid = seed(store)
    _, response = login(client, store)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    token = client.cookies.get(COOKIE)
    assert token not in str(dict(store.db.execute("SELECT * FROM sessions").fetchone()))
    assert (
        client.get(f"/api/reviews/{rid}", headers={"Host": "evil.test"}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/logout", json={}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/logout", json={}, headers={"X-CSRF-Token": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.get("/api/session", headers={"X-Space-Request": ""}).status_code == 403
    )
    assert (
        client.get(
            "/api/development/mailbox", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    now[0] += 1800
    assert client.get("/api/session").status_code == 401


def test_cross_site_sign_in_navigation_does_not_consume_link(portal):
    client, store, _, _ = portal
    seed(store)
    token = store.issue_link("alex@example.com")
    headers = {
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
    }
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-store"
    assert "noindex" in response.headers["x-robots-tag"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "set-cookie" not in response.headers
    assert client.get("/api/session").status_code == 401
    assert client.post("/api/auth/consume", json={"token": token}).status_code == 200
    assert client.post("/api/auth/consume", json={"token": token}).status_code == 401
    assert client.get("/", headers={**headers, "Host": "evil.test"}).status_code == 400


@pytest.mark.parametrize(
    "method,path,mode,destination",
    [
        ("GET", "/", "navigate", "iframe"),
        ("GET", "/", "navigate", "frame"),
        ("GET", "/", "cors", "empty"),
        ("GET", "/", "no-cors", "image"),
        ("GET", "/", "", ""),
        ("GET", "/", "navigate", ""),
        ("GET", "/", "", "document"),
        ("POST", "/", "navigate", "document"),
        ("GET", "/app.mjs", "navigate", "document"),
        ("GET", "/api/session", "navigate", "document"),
        ("GET", "/api/development/mailbox", "navigate", "document"),
        ("GET", "/api/reviews/fake/documents/fake/content", "navigate", "document"),
        ("POST", "/api/auth/consume", "navigate", "document"),
        ("POST", "/api/development/email-test", "navigate", "document"),
    ],
)
def test_cross_site_non_entry_requests_remain_denied(
    portal, method, path, mode, destination
):
    client, _, _, _ = portal
    response = client.request(
        method,
        path,
        headers={
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": mode,
            "Sec-Fetch-Dest": destination,
        },
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-site request denied"}


def test_absolute_expiry_even_when_active_and_logout_all(portal):
    client, store, now, _ = portal
    seed(store)
    first = store.consume_link(store.issue_link("alex@example.com"))
    for _ in range(44):
        now[0] += 900
        store.authenticate(first)
    now[0] += 4 * 900
    with pytest.raises(PermissionError):
        store.authenticate(first)
    login(client, store)
    other = store.consume_link(store.issue_link("alex@example.com"))
    assert client.post("/api/logout", json={}).status_code == 200
    assert client.get("/api/session").status_code == 401
    with pytest.raises(PermissionError):
        store.authenticate(other)


def test_owner_boundaries_on_all_review_operations(portal):
    client, store, _, _ = portal
    rid = prepare(client, store)
    document = store.view(rid, "alex@example.com")["documents"][0]
    seed(store, "bob@example.com")
    login(client, store, "bob@example.com")
    requests = [
        ("GET", f"/api/reviews/{rid}", None),
        ("GET", f"/api/reviews/{rid}/documents/{document['id']}/content", None),
        ("PUT", f"/api/reviews/{rid}/catalog", {"revision": 3, "catalog": CATALOG}),
        ("DELETE", f"/api/reviews/{rid}/documents/{document['id']}", {"revision": 3}),
        ("POST", f"/api/reviews/{rid}/submit", {"revision": 3}),
        ("POST", f"/api/reviews/{rid}/reply", {"revision": 3, "message": "forged"}),
        ("POST", f"/api/development/reviews/{rid}/question", {}),
    ]
    for method, url, data in requests:
        assert client.request(method, url, json=data).status_code == 404, url
    assert upload(client, rid, "royalties", 3).status_code == 404


def test_persisted_catalog_documents_submit_retry_and_clarification(portal):
    client, store, _, _ = portal
    rid = prepare(client, store)
    view = client.get(f"/api/reviews/{rid}").json()
    assert view["catalog"]["revenue"] == "0"
    assert view["catalog"]["owned"] == "50" and view["catalog"]["offered"] == "50"
    doc = view["documents"][0]
    download = client.get(f"/api/reviews/{rid}/documents/{doc['id']}/content")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    assert download.headers["cache-control"] == "no-store"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert not (store.files / doc["id"]).stat().st_mode & 0o077
    assert upload(client, rid, doc["kind"], 3).status_code == 409
    for _ in range(2):
        result = client.post(f"/api/reviews/{rid}/submit", json={"revision": 3})
        assert result.status_code == 200
        assert result.json()["status"] == "UNDER_REVIEW"
    assert (
        store.db.execute(
            "SELECT count(*) FROM events WHERE action='PACKAGE_SUBMITTED_FOR_MANUAL_REVIEW'"
        ).fetchone()[0]
        == 1
    )
    assert (
        client.put(
            f"/api/reviews/{rid}/catalog", json={"revision": 4, "catalog": CATALOG}
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/development/reviews/{rid}/question", json={}).json()[
            "status"
        ]
        == "DATA_REQUIRED"
    )
    assert (
        client.post(
            f"/api/reviews/{rid}/reply", json={"revision": 5, "message": " "}
        ).status_code
        == 422
    )
    response = client.post(
        f"/api/reviews/{rid}/reply",
        json={"revision": 5, "message": "Fictional own share <script>no</script>"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "UNDER_REVIEW"
    assert response.json()["messages"][-1]["role"] == "SELLER"
    # A new DB connection proves the package is not just in browser state.
    reopened = LocalPortalStore(store.root, SECRET)
    assert reopened.view(rid, "alex@example.com")["messages"][-1]["body"].startswith(
        "Fictional own share"
    )
    reopened.close()


def test_quarantine_cannot_download_or_submit_and_removal(portal):
    client, store, _, _ = portal
    rid = seed(store)
    login(client, store)
    result = upload(
        client, rid, "royalties", 0, b"synthetic,unknown\n1,2\n", "unknown.csv"
    )
    assert result.status_code == 200
    doc = result.json()["documents"][0]
    assert doc["scan"] == "QUARANTINED"
    assert (
        client.get(f"/api/reviews/{rid}/documents/{doc['id']}/content").status_code
        == 409
    )
    assert (
        client.post(f"/api/reviews/{rid}/submit", json={"revision": 1}).status_code
        == 409
    )
    response = client.request(
        "DELETE", f"/api/reviews/{rid}/documents/{doc['id']}", json={"revision": 1}
    )
    assert response.status_code == 200
    assert not (store.files / doc["id"]).exists()


@pytest.mark.parametrize("damage", ["missing", "corrupt", "symlink"])
def test_missing_or_corrupt_evidence_cannot_be_submitted(portal, damage, tmp_path):
    client, store, _, _ = portal
    rid = prepare(client, store)
    doc = store.view(rid, "alex@example.com")["documents"][0]
    target = store.files / doc["id"]
    if damage == "missing":
        target.unlink()
    elif damage == "corrupt":
        target.write_bytes(b"corrupted synthetic fixture")
    else:
        target.unlink()
        target.symlink_to(tmp_path / "unrelated")
    response = client.post(f"/api/reviews/{rid}/submit", json={"revision": 3})
    assert response.status_code == 409
    assert store.view(rid, "alex@example.com")["status"] == "SUBMITTED"
    assert store.view(rid, "alex@example.com")["revision"] == 3
    assert (
        client.get(f"/api/reviews/{rid}/documents/{doc['id']}/content").status_code
        == 409
    )


@pytest.mark.parametrize(
    "name,body",
    [
        ("../secret.csv", b"x"),
        ("evil.exe", b"x"),
        ("zero.csv", b""),
        ("..%2Fsecret.csv", b"x"),
    ],
)
def test_invalid_files_never_persist(portal, name, body):
    client, store, _, _ = portal
    rid = seed(store)
    login(client, store)
    assert upload(client, rid, "royalties", 0, body, name).status_code == 422
    assert list(store.files.iterdir()) == []


def test_limits_malformed_ids_and_no_static_private_files(portal):
    client, store, _, _ = portal
    assert (
        client.post(
            "/api/auth/request",
            content=b"x" * 65537,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )
    rid = seed(store)
    login(client, store)
    assert (
        upload(client, rid, "royalties", 0, b"x" * (25 * 1024 * 1024 + 1)).status_code
        == 413
    )
    for url in (
        "/portal.sqlite",
        "/documents/test",
        "/../store.py",
        "/%2e%2e%2fstore.py",
        "/openapi.json",
        "/api/reviews/not-a-uuid",
    ):
        assert client.get(url).status_code in (404, 422), url
    assert list(store.files.iterdir()) == []


def test_server_catalog_validation_and_revision_conflicts(portal):
    client, store, _, _ = portal
    rid = seed(store)
    login(client, store)
    for change in (
        {"owned": "101"},
        {"offered": "0"},
        {"revenue": "-1"},
        {"revenue": "NaN"},
        {"tracks": 1.5},
        {"periodEnd": "2026-07"},
        {"cutoff": "2026-02-30"},
        {"verified": True},
        {"artistLink": "javascript:alert(1)"},
    ):
        response = client.put(
            f"/api/reviews/{rid}/catalog",
            json={"revision": 0, "catalog": {**CATALOG, **change}},
        )
        assert response.status_code == 422, response.text
    assert (
        client.put(
            f"/api/reviews/{rid}/catalog", json={"revision": 0, "catalog": CATALOG}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/reviews/{rid}/catalog", json={"revision": 0, "catalog": CATALOG}
        ).status_code
        == 409
    )
    assert store.view(rid, "alex@example.com")["revision"] == 1


def test_auth_rate_limits_persist_and_unknown_matches_known_response(portal):
    client, store, _, app = portal
    seed(store)
    for _ in range(4):
        assert (
            client.post(
                "/api/auth/request", json={"email": "alex@example.com"}
            ).status_code
            == 202
        )
    assert len(app.state.mailbox) == 3
    for i in range(8):
        assert (
            client.post(
                "/api/auth/request", json={"email": f"unknown{i}@example.com"}
            ).status_code
            == 202
        )
    response = client.post("/api/auth/request", json={"email": "unknown@example.com"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "600"
