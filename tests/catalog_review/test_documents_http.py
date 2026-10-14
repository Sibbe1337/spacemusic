import asyncio
from uuid import uuid4

import httpx
import pytest
from conftest import draft, owner_cursor, sign_in
from fastapi.testclient import TestClient

from services.catalog_review.http import COOKIE, create_test_app
from services.catalog_review.workers import scan_document


def browser(service, session, *, enabled=True):
    result = TestClient(
        create_test_app(
            service, document_store=service.test_blobs if enabled else None
        ),
        base_url="https://review.test",
    )
    result.cookies.set(COOKIE, session)
    result.headers.update(
        {"origin": "https://review.test", "x-csrf-token": service.csrf(session)}
    )
    return result


def headers(filename="statement.csv", request_id=None):
    return {
        "content-type": "application/octet-stream",
        "x-document-name": filename,
        "x-upload-id": request_id or str(uuid4()),
    }


def test_document_gate_off_by_default(backend):
    _, owner, _ = sign_in(backend)
    with browser(backend, owner, enabled=False) as client:
        assert client.get("/api/portal/workspace").json()["capabilities"] == {
            "document_upload": False,
            "toolost": False,
            "dealflow": False,
        }
        assert (
            client.post(
                "/api/portal/documents", content=b"x", headers=headers()
            ).status_code
            == 404
        )
        assert client.get(f"/api/portal/documents/{uuid4()}").status_code == 404


def test_upload_idempotency_quarantine_and_authorized_attachment(backend):
    workspace, owner, _ = sign_in(backend)
    content = b"period,amount\n2026-08,10\n"
    upload_headers = headers()
    with browser(backend, owner) as client:
        first = client.post(
            "/api/portal/documents", content=content, headers=upload_headers
        )
        assert first.status_code == 202
        assert first.json()["status"] == "quarantined"
        doc = first.json()["document_id"]
        assert (
            client.post(
                "/api/portal/documents", content=content, headers=upload_headers
            ).json()
            == first.json()
        )
        assert len(backend.test_blobs.objects) == 1
        assert (
            client.post(
                "/api/portal/documents", content=b"different", headers=upload_headers
            ).status_code
            == 409
        )
        assert client.get(f"/api/portal/documents/{doc}").status_code == 404

        class SyntheticScanner:
            def inspect(self, **kwargs):
                return True

        scan_document(backend, workspace, doc, backend.test_blobs, SyntheticScanner())
        response = client.get(f"/api/portal/documents/{doc}")
        assert response.content == content
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"
        _, other, _ = sign_in(backend, "other")
        client.cookies.set(COOKIE, other)
        assert client.get(f"/api/portal/documents/{doc}").status_code == 404


@pytest.mark.parametrize(
    "changes,content,status",
    [
        ({"content-type": "text/plain"}, b"x", 415),
        ({"x-upload-id": "invalid"}, b"x", 422),
        ({"x-document-name": "../x.csv"}, b"x", 422),
        ({"x-document-name": "code.exe"}, b"x", 422),
        ({"x-document-name": "%FF.csv"}, b"x", 422),
        ({}, b"", 413),
        ({"content-length": "26214401"}, b"x", 413),
        ({"content-length": "-1"}, b"x", 413),
        ({"x-document-name": "not-pdf.pdf"}, b"x", 422),
    ],
)
def test_upload_rejects_invalid_headers_type_size(backend, changes, content, status):
    _, owner, _ = sign_in(backend)
    with browser(backend, owner) as client:
        response = client.post(
            "/api/portal/documents", content=content, headers={**headers(), **changes}
        )
        assert response.status_code == status
        assert not backend.test_blobs.objects


def test_no_cleanup_if_storage_cannot_confirm_object_creation(backend):
    _, owner, _ = sign_in(backend)

    class AmbiguousStore:
        deleted = False

        def put_if_absent(self, *args):
            raise TimeoutError("unknown write result")

        def delete(self, key):
            self.deleted = True

    store = AmbiguousStore()
    with pytest.raises(TimeoutError):
        backend.quarantine(owner, "x.csv", b"data", store)
    assert store.deleted is False
    with owner_cursor(backend) as cur:
        cur.execute("SELECT count(*) AS count FROM documents")
        assert cur.fetchone()["count"] == 0


def test_uploaded_request_can_be_replayed_after_submission_but_new_upload_cannot(
    backend,
):
    _, owner, _ = sign_in(backend)
    request_headers = headers()
    with browser(backend, owner) as client:
        first = client.post(
            "/api/portal/documents", content=b"data", headers=request_headers
        )
        backend.save_draft(owner, {"revision": 0, "draft": draft()})
        backend.submit(
            owner, {"request_id": str(uuid4()), "revision": 1, "consent": True}
        )
        replay = client.post(
            "/api/portal/documents", content=b"data", headers=request_headers
        )
        assert replay.status_code == 202
        assert replay.json() == first.json()
        assert client.post(
            "/api/portal/documents", content=b"data", headers=headers()
        ).json() == {"error": "submission_locked"}
        assert len(backend.test_blobs.objects) == 1


@pytest.mark.parametrize("declared_length", [None, "1"])
def test_stream_limit_is_enforced_without_trusting_content_length(
    backend, declared_length
):
    _, owner, _ = sign_in(backend)

    async def scenario():
        async def body():
            for _ in range(26):
                yield b"x" * (1024 * 1024)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_test_app(backend, document_store=backend.test_blobs)
            ),
            base_url="https://review.test",
        ) as client:
            client.cookies.set(COOKIE, owner)
            request_headers = {
                **headers(),
                "origin": "https://review.test",
                "x-csrf-token": backend.csrf(owner),
            }
            if declared_length is not None:
                request_headers["content-length"] = declared_length
            response = await client.post(
                "/api/portal/documents", content=body(), headers=request_headers
            )
            assert response.status_code == 413
            assert not backend.test_blobs.objects
            assert (
                await client.post(
                    "/api/portal/documents",
                    content=b"next",
                    headers={**request_headers, "x-upload-id": str(uuid4())},
                )
            ).status_code == 202

    asyncio.run(scenario())


def test_upload_deadline_releases_slot_for_next_request(backend, monkeypatch):
    import services.catalog_review.http as adapter

    monkeypatch.setattr(adapter, "UPLOAD_TIMEOUT_SECONDS", 0.03)
    _, owner, _ = sign_in(backend)

    async def scenario():
        async def body():
            await asyncio.sleep(1)
            yield b"late"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_test_app(backend, document_store=backend.test_blobs)
            ),
            base_url="https://review.test",
        ) as client:
            client.cookies.set(COOKIE, owner)
            request_headers = {
                **headers(),
                "origin": "https://review.test",
                "x-csrf-token": backend.csrf(owner),
            }
            assert (
                await client.post(
                    "/api/portal/documents", content=body(), headers=request_headers
                )
            ).status_code == 408
            assert not backend.test_blobs.objects
            assert (
                await client.post(
                    "/api/portal/documents", content=b"next", headers=request_headers
                )
            ).status_code == 202

    asyncio.run(scenario())


def test_concurrent_upload_limit_and_slot_recovery(backend):
    _, owner, _ = sign_in(backend)

    async def scenario():
        entered = [asyncio.Event(), asyncio.Event()]
        release = asyncio.Event()

        async def body(index):
            entered[index].set()
            await release.wait()
            yield b"data"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(
                app=create_test_app(backend, document_store=backend.test_blobs)
            ),
            base_url="https://review.test",
        ) as client:
            client.cookies.set(COOKIE, owner)
            auth = {
                "origin": "https://review.test",
                "x-csrf-token": backend.csrf(owner),
            }
            tasks = [
                asyncio.create_task(
                    client.post(
                        "/api/portal/documents",
                        content=body(index),
                        headers={**headers(), **auth},
                    )
                )
                for index in range(2)
            ]
            try:
                for event in entered:
                    await asyncio.wait_for(event.wait(), timeout=5)
                blocked = await client.post(
                    "/api/portal/documents",
                    content=b"data",
                    headers={**headers(), **auth},
                )
                assert blocked.status_code == 429
                assert blocked.json() == {"error": "uploads_busy"}
            finally:
                release.set()
                responses = await asyncio.gather(*tasks)
            assert all(response.status_code == 202 for response in responses)
            assert (
                await client.post(
                    "/api/portal/documents",
                    content=b"next",
                    headers={**headers(), **auth},
                )
            ).status_code == 202

    asyncio.run(scenario())
