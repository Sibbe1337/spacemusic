from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import hmac
import json
import os
from pathlib import Path
import secrets
from typing import Literal
from urllib.parse import quote, urlsplit
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from .contracts import (
    CatalogSave,
    EmailInput,
    LinkInput,
    RevisionInput,
    ReplyInput,
    FIXTURES,
    verified_signature,
)
from .store import Conflict, LocalPortalStore
from .mail import MailUnavailable, RECIPIENT, ResendTestSender, read_key

ROOT = Path(__file__).resolve().parents[3]
UI = Path(__file__).parent / "ui"
COOKIE = "space_portal_local_session"
GENERIC_LINK_MESSAGE = "If an application matches this address, a sign-in link will be available. Check the local test mailbox; no real email is sent."
PUBLIC_SOURCE_PATHS = {
    "/",
    "/calculator/",
    "/apply/",
    "/sell/",
    "/guides/music-catalog-valuation-2026/",
}


class OwnerEmailTest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    confirm_owner_test: Literal[True]


def validate_directory(directory):
    if directory.resolve().is_relative_to(ROOT):
        raise RuntimeError(
            "Private portal storage must be outside the repository and web roots"
        )


@dataclass(frozen=True)
class Settings:
    directory: Path
    secret: bytes
    webhook_secret: bytes
    origin: str = "http://127.0.0.1:4194"
    form_id: str = "local-test-form"
    mode: str = "local"

    def validate(self):
        parsed = urlsplit(self.origin)
        if (
            self.mode != "local"
            or parsed.scheme not in ("http", "https")
            or parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise RuntimeError(
                "Production is disabled: managed storage, email delivery and scanning are not configured"
            )
        if len(self.secret) < 32 or len(self.webhook_secret) < 32:
            raise RuntimeError(
                "Explicit independent secrets of at least 32 bytes are required"
            )
        if self.secret == self.webhook_secret:
            raise RuntimeError("Session and webhook secrets must be different")
        validate_directory(self.directory)


async def limited_body(request: Request, limit: int):
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            raise HTTPException(413, "Request exceeds the allowed size")
        chunks.append(chunk)
    return b"".join(chunks)


async def payload(request, model):
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Use application/json")
    try:
        return model.model_validate_json(await limited_body(request, 64 * 1024))
    except ValidationError as exc:
        errors = [
            {"field": ".".join(str(p) for p in item["loc"]), "message": item["msg"]}
            for item in exc.errors()
        ]
        raise HTTPException(422, errors)


def create_app(settings: Settings, store=None, test_sender=None):
    settings.validate()
    db = store or LocalPortalStore(settings.directory, settings.secret)
    # Local mail sink only. Tokens are not persisted in plaintext or returned by auth endpoints.
    mailbox = []
    # Conservative, versioned local-test allowlist. Never depend on a scratch release.
    public_paths = PUBLIC_SOURCE_PATHS

    @asynccontextmanager
    async def lifespan(_):
        app.state.mail_lock = asyncio.Lock()
        yield
        if store is None:
            db.close()

    app = FastAPI(
        title="SpaceMusic local seller integration",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.store, app.state.mailbox = db, mailbox

    @app.middleware("http")
    async def boundary(request, call_next):
        expected_host = urlsplit(settings.origin).netloc
        api = request.url.path.startswith("/api/")
        webhook = request.url.path == "/api/integrations/formspree"
        download = request.url.path.endswith("/content")
        # Email links may open the inert shell, never an API or embedded document.
        entry_navigation = (
            request.method == "GET"
            and request.url.path == "/"
            and request.headers.get("sec-fetch-mode") == "navigate"
            and request.headers.get("sec-fetch-dest") == "document"
        )
        if request.headers.get("host") != expected_host:
            response = JSONResponse({"detail": "Invalid host"}, status_code=400)
        elif (
            request.headers.get("sec-fetch-site") == "cross-site"
            and not webhook
            and not entry_navigation
        ):
            response = JSONResponse(
                {"detail": "Cross-site request denied"}, status_code=403
            )
        elif (
            api
            and not webhook
            and (request.method != "GET" or not download)
            and request.headers.get("x-space-request") != "portal-v1"
        ):
            response = JSONResponse(
                {"detail": "Same-origin application request required"}, status_code=403
            )
        elif (
            api
            and not webhook
            and request.method not in ("GET", "HEAD")
            and request.headers.get("origin") != settings.origin
        ):
            response = JSONResponse({"detail": "Origin denied"}, status_code=403)
        else:
            response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Robots-Tag": "noindex, nofollow, noarchive",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'",
            }
        )
        return response

    @app.exception_handler(Conflict)
    async def conflict(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(PermissionError)
    async def permission(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=401)

    @app.exception_handler(KeyError)
    async def not_found(_, exc):
        return JSONResponse({"detail": "Review or document not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def bad_request(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_, exc):
        return JSONResponse({"detail": "Invalid request parameters"}, status_code=422)

    def session(request, write=False):
        token = request.cookies.get(COOKIE, "")
        email = db.authenticate(token)
        csrf = db.digest("csrf:" + token)
        if write and not hmac.compare_digest(
            request.headers.get("x-csrf-token", ""), csrf
        ):
            raise HTTPException(403, "Session check failed. Reload before trying again")
        return email, csrf

    def throttle(request, category, maximum=12):
        # Never trust user-supplied X-Forwarded-For in this local service.
        address = request.client.host if request.client else "unknown"
        if not db.rate_limit(category + ":" + address, maximum, 600):
            raise HTTPException(
                429,
                "Too many attempts. Wait ten minutes and try again",
                headers={"Retry-After": "600"},
            )

    @app.post("/api/integrations/formspree")
    async def webhook(request: Request):
        raw = await limited_body(request, 64 * 1024)
        if not verified_signature(
            settings.webhook_secret,
            request.headers.get("formspree-signature", ""),
            raw,
            int(db.clock()),
        ):
            raise HTTPException(401, "Webhook signature rejected")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "Invalid JSON")
        if not isinstance(data, dict) or data.get("form") != settings.form_id:
            raise HTTPException(400, "Unexpected form")
        review_id, created = db.ingest(
            settings.form_id, data.get("submission"), public_paths
        )
        return {"received": True, "created": created, "reference": review_id}

    @app.post("/api/auth/request", status_code=202)
    async def request_link(request: Request):
        throttle(request, "request-link")
        data = await payload(request, EmailInput)
        allowed = db.rate_limit("email:" + data.email, 3, 600)
        if allowed:
            token = db.issue_link(data.email)
            if token:
                mailbox[:] = [item for item in mailbox if item["expires"] > db.clock()][
                    -49:
                ]
                mailbox.append(
                    {
                        "recipient": data.email,
                        "url": settings.origin + "/#sign-in=" + token,
                        "expires": int(db.clock()) + 900,
                    }
                )
        return {"message": GENERIC_LINK_MESSAGE}

    @app.post("/api/auth/consume")
    async def consume(request: Request):
        throttle(request, "consume-link", 20)
        data = await payload(request, LinkInput)
        token = db.consume_link(data.token, request.cookies.get(COOKIE, ""))
        response = JSONResponse({"authenticated": True})
        response.set_cookie(
            COOKIE,
            token,
            max_age=12 * 3600,
            httponly=True,
            secure=settings.origin.startswith("https:"),
            samesite="strict",
            path="/",
        )
        return response

    @app.get("/api/session")
    async def read_session(request: Request):
        email, csrf = session(request)
        return {"email": email, "csrf": csrf, "reviews": db.list_reviews(email)}

    @app.post("/api/logout")
    async def logout(request: Request):
        session(request, write=True)
        db.revoke(request.cookies[COOKIE], all_sessions=True)
        response = JSONResponse({"signed_out": True})
        response.delete_cookie(
            COOKIE,
            path="/",
            httponly=True,
            secure=settings.origin.startswith("https:"),
            samesite="strict",
        )
        return response

    @app.get("/api/reviews/{review_id}")
    async def review(review_id: UUID, request: Request):
        email, _ = session(request)
        return db.view(str(review_id), email)

    @app.put("/api/reviews/{review_id}/catalog")
    async def save_catalog(review_id: UUID, request: Request):
        email, _ = session(request, write=True)
        data = await payload(request, CatalogSave)
        db.save_catalog(str(review_id), email, data.revision, data.catalog)
        return db.view(str(review_id), email)

    @app.post("/api/reviews/{review_id}/documents/{kind}")
    async def upload(
        review_id: UUID,
        kind: Literal["royalties", "tracks"],
        revision: int,
        request: Request,
    ):
        email, _ = session(request, write=True)
        # Authorize before buffering document bytes.
        with db.lock:
            db.owned_review(str(review_id), email)
        name = request.headers.get("x-file-name", "")
        from urllib.parse import unquote

        name = unquote(name)
        body = await limited_body(request, 25 * 1024 * 1024)
        db.add_document(str(review_id), email, revision, kind, name, body)
        return db.view(str(review_id), email)

    @app.delete("/api/reviews/{review_id}/documents/{document_id}")
    async def remove(review_id: UUID, document_id: UUID, request: Request):
        email, _ = session(request, write=True)
        data = await payload(request, RevisionInput)
        db.remove_document(str(review_id), email, data.revision, str(document_id))
        return db.view(str(review_id), email)

    @app.get("/api/reviews/{review_id}/documents/{document_id}/content")
    async def download(review_id: UUID, document_id: UUID, request: Request):
        email, _ = session(request)
        content, name = db.document_content(str(review_id), email, str(document_id))
        return Response(
            content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename*=UTF-8''"
                + quote(name, safe="")
            },
        )

    @app.post("/api/reviews/{review_id}/submit")
    async def submit(review_id: UUID, request: Request):
        email, _ = session(request, write=True)
        data = await payload(request, RevisionInput)
        db.submit(str(review_id), email, data.revision)
        return db.view(str(review_id), email)

    @app.post("/api/reviews/{review_id}/reply")
    async def reply(review_id: UUID, request: Request):
        email, _ = session(request, write=True)
        data = await payload(request, ReplyInput)
        db.reply(str(review_id), email, data.revision, data.message)
        return db.view(str(review_id), email)

    # Deliberately local-only test harness. Settings refuse any non-local deployment.
    @app.post("/api/development/seed")
    async def seed(request: Request):
        review_id, created = db.ingest(
            settings.form_id,
            {
                "_date": "2026-09-10T12:00:00Z",
                "email": "alex@example.com",
                "artistLabel": "Night Window",
                "firstName": "Alex Example",
                "landing_path": "/",
                "apply_source_path": "/calculator/",
            },
            public_paths,
        )
        return {"reference": review_id, "created": created, "email": "alex@example.com"}

    @app.get("/api/development/mailbox")
    async def test_mailbox():
        return {"messages": [m for m in mailbox if m["expires"] > db.clock()]}

    @app.get("/api/development/email-test")
    async def email_test_config():
        return {
            "enabled": test_sender is not None,
            "recipient": RECIPIENT,
            "last_test": db.latest_owner_email(),
        }

    @app.post("/api/development/email-test")
    async def email_test(request: Request):
        if test_sender is None:
            raise HTTPException(
                503, "Real email testing is disabled on this local server"
            )
        data = await payload(request, OwnerEmailTest)
        async with app.state.mail_lock:
            if not db.rate_limit("owner-email-attempts", 5, 600) or not db.rate_limit(
                "owner-email-daily", 20, 86400
            ):
                raise HTTPException(
                    429, "Owner email test limit reached. Try again later"
                )
            request_id = str(data.request_id)
            token, provider_id = db.prepare_owner_email(request_id, settings.origin)
            if provider_id is None:
                try:
                    provider_id = await test_sender.send(
                        request_id, settings.origin, token
                    )
                except MailUnavailable as exc:
                    raise HTTPException(502, str(exc)) from None
                db.accept_owner_email(request_id, provider_id)
        return {
            "status": "accepted_by_provider",
            "provider_id": provider_id,
            "recipient": RECIPIENT,
            "message": "Resend accepted the test email for hello@spacemusic.io. Inbox delivery is not yet verified. Open its link on this computer; it signs into the fictional alex@example.com review.",
        }

    @app.get("/api/development/fixtures/{kind}")
    async def fixture(kind: Literal["royalties", "tracks"]):
        name, content = FIXTURES[kind]
        return Response(
            content, media_type="text/csv", headers={"X-Fixture-Name": name}
        )

    @app.post("/api/development/reviews/{review_id}/question")
    async def question(review_id: UUID, request: Request):
        email, _ = session(request, write=True)
        db.ask(str(review_id), email)
        return db.view(str(review_id), email)

    assets = {
        "/": (UI / "index.html", "text/html"),
        "/app.mjs": (UI / "app.mjs", "text/javascript"),
        "/portal.css": (UI / "portal.css", "text/css"),
        "/styles.css": (
            ROOT / "marketing/seller-journey-preview/styles.css",
            "text/css",
        ),
        "/model.mjs": (
            ROOT / "marketing/seller-journey-preview/model.mjs",
            "text/javascript",
        ),
        "/inter.woff2": (
            ROOT / "marketing/catalog-readiness-draft/preview/fonts/inter.woff2",
            "font/woff2",
        ),
    }

    @app.get("/{asset_path:path}")
    async def asset(asset_path: str):
        item = assets.get("/" + asset_path)
        if not item:
            raise HTTPException(404, "Not found")
        return Response(item[0].read_bytes(), media_type=item[1])

    return app


def main():
    parser = argparse.ArgumentParser(
        description="LOCAL ONLY: seller integration with synthetic identities"
    )
    parser.add_argument("--local", action="store_true", required=True)
    parser.add_argument("--port", type=int, default=4194)
    parser.add_argument(
        "--resend-key-file",
        type=Path,
        help="Opt in to owner-only real email tests using a private 0600 file outside the repository",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path.home()
        / "Library/Application Support/SpaceMusic/seller-portal-local",
    )
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be between 1024 and 65535")
    validate_directory(args.directory)
    sender = (
        ResendTestSender(read_key(args.resend_key_file))
        if args.resend_key_file
        else None
    )
    args.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key_path = args.directory / "local-secret"
    try:
        with open(key_path, "xb") as stream:
            os.chmod(key_path, 0o600)
            stream.write(secrets.token_bytes(32))
    except FileExistsError:
        pass
    config = Settings(
        args.directory,
        key_path.read_bytes(),
        secrets.token_bytes(32),
        origin=f"http://127.0.0.1:{args.port}",
    )
    import uvicorn

    uvicorn.run(
        create_app(config, test_sender=sender),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
