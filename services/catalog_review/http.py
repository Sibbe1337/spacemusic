"""Private HTTP adapter; no fixture routes or ambient deployment credentials."""

import asyncio
import hmac
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import unquote, urlsplit
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from .contracts import (
    ContinueInterest,
    ExchangeInvitation,
    LiveRequestAccess,
    RequestAccess,
    ReviewQuestion,
    ReviewReply,
    SaveDraft,
    Submit,
    Upload,
)
from .security import ReviewError
from .dealflow_contracts import PackageRequest, ReviewRecord, ShareDecision

COOKIE = "__Host-space_review"
UPLOAD_TIMEOUT_SECONDS = 30
HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}
UI_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self'; font-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
ROOT = Path(__file__).resolve().parents[2]
ASSETS = {
    "/dealflow/": ("services/catalog_review_ui/dealflow.html", "text/html"),
    "/dealflow/dealflow.mjs": ("services/catalog_review_ui/dealflow.mjs", "text/javascript"),
    "/dealflow/dealflow.css": ("services/catalog_review_ui/dealflow.css", "text/css"),
    "/dealflow/client.mjs": ("services/catalog_review_ui/client.mjs", "text/javascript"),
    "/workspace/": ("services/catalog_review_ui/index.html", "text/html"),
    "/workspace/app.mjs": ("services/catalog_review_ui/app.mjs", "text/javascript"),
    "/workspace/client.mjs": (
        "services/catalog_review_ui/client.mjs",
        "text/javascript",
    ),
    "/workspace/portal.css": ("services/catalog_review_ui/portal.css", "text/css"),
    "/workspace/review.css": (
        "services/catalog_review_preview/ui/review.css",
        "text/css",
    ),
    "/workspace/space-wordmark.svg": (
        "marketing/identity-20260916/space-wordmark.svg",
        "image/svg+xml",
    ),
    "/workspace/inter.woff2": (
        "marketing/design/fonts/inter-latin-c940764593d0.woff2",
        "font/woff2",
    ),
    # The approved shared stylesheet uses this absolute font path.
    "/inter.woff2": (
        "marketing/design/fonts/inter-latin-c940764593d0.woff2",
        "font/woff2",
    ),
    "/staff/": ("services/catalog_review_ui/staff.html", "text/html"),
    "/staff/staff.mjs": ("services/catalog_review_ui/staff.mjs", "text/javascript"),
}


async def payload(request, contract):
    if (
        request.headers.get("content-type", "").split(";")[0].strip()
        != "application/json"
    ):
        raise ReviewError("json_required", 415)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 64 * 1024:
            raise ReviewError("request_too_large", 413)
    try:
        return contract.model_validate_json(bytes(data))
    except ValidationError:
        # Do not echo input values, tokens, financial details or validation bodies.
        raise ReviewError("invalid_fields", 422) from None


def create_test_app(service, *, document_store=None):
    if service.settings.mode != "test":
        raise RuntimeError("Test entrypoint rejects deployed environments")
    return create_application(service, document_store=document_store)


def create_application(
    service, *, document_store=None, staff_router=None, intake_router=None
):
    service.settings.validate()
    origin = service.settings.origin
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    uploads = BoundedSemaphore(2)
    signed_webhooks = {"/api/intake/typeform"} if intake_router is not None else set()
    oauth_callbacks = (
        {"/api/staff/oidc/callback"} if staff_router is not None else set()
    )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        try:
            if request.headers.get("host") != urlsplit(origin).netloc:
                raise ReviewError("invalid_host", 400)
            if request.url.scheme != "https":
                raise ReviewError("https_required", 400)
            callback = request.method == "GET" and request.url.path in oauth_callbacks
            webhook = (
                request.method == "POST"
                and request.url.path in signed_webhooks
                and not request.headers.get("origin")
                and not request.headers.get("sec-fetch-site")
            )
            if request.url.query and not callback:
                raise ReviewError("query_not_allowed", 400)
            shell_navigation = (
                request.method in ("GET", "HEAD")
                and request.url.path in ("/workspace/", "/staff/", "/dealflow/")
                and request.headers.get("sec-fetch-mode") == "navigate"
                and request.headers.get("sec-fetch-dest") == "document"
            )
            if (
                request.headers.get("sec-fetch-site") in ("cross-site", "same-site")
                and not shell_navigation
                and not callback
            ):
                raise ReviewError("cross_site_denied", 403)
            if request.headers.get("origin") not in (None, origin):
                raise ReviewError("origin_denied", 403)
            if (
                request.method not in ("GET", "HEAD", "OPTIONS")
                and request.headers.get("origin") != origin
                and not webhook
            ):
                raise ReviewError("origin_denied", 403)
            if (
                request.method
                not in (
                    "GET",
                    "HEAD",
                    "OPTIONS",
                )
                and not webhook
                and not request.url.path.startswith("/api/staff/")
                and request.url.path
                not in (
                    "/api/portal/session",
                    "/api/portal/access-request",
                )
            ):
                token = request.cookies.get(COOKIE, "")
                if not token or not hmac.compare_digest(
                    request.headers.get("x-csrf-token", ""), service.csrf(token)
                ):
                    raise ReviewError("csrf_denied", 403)
            response = await call_next(request)
        except ReviewError as error:
            response = JSONResponse({"error": error.code}, status_code=error.status)
        except Exception:
            # No raw exception/request logging in this test adapter. Production
            # needs separately reviewed, redacted telemetry and rate limiting.
            response = JSONResponse(
                {"error": "temporarily_unavailable"}, status_code=503
            )
        response.headers.update(HEADERS)
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.path in ASSETS:
            response.headers["Content-Security-Policy"] = UI_CSP
        if service.settings.mode != "test":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(ReviewError)
    async def domain_error(_, error):
        return JSONResponse({"error": error.code}, status_code=error.status)

    @app.exception_handler(HTTPException)
    async def route_error(_, error):
        return JSONResponse(
            {"error": "route_unavailable"}, status_code=error.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, error):
        return JSONResponse({"error": "invalid_fields"}, status_code=422)

    def asset(request: Request):
        filename, media_type = ASSETS[request.url.path]
        if request.url.path == "/workspace/" and service.settings.mode == "production":
            filename = "services/catalog_review_ui/index.production.html"
        content = (ROOT / filename).read_bytes()
        if request.url.path == "/staff/" and service.settings.mode == "production":
            content = content.replace(
                b'data-environment="test"', b'data-environment="production"', 1
            )
            content = content.replace(
                b"Integration test", b"Restricted staff access", 1
            )
            content = content.replace(
                b"Synthetic information only. Do not enter real customer information.",
                b"Named staff access with verified passkeys is required.",
                1,
            )
        return Response(content, media_type=media_type)

    for path in ASSETS:
        app.add_api_route(path, asset, methods=["GET", "HEAD"], include_in_schema=False)

    def token(request):
        value = request.cookies.get(COOKIE)
        if not value:
            raise ReviewError("authentication_required", 401)
        return value

    @app.post("/api/portal/session")
    async def exchange(request: Request):
        # X-Forwarded-For is deliberately not trusted. Configure proxy trust only
        # with approved hosting; local tests use the real ASGI peer.
        await run_in_threadpool(
            service.throttle_exchange,
            request.client.host if request.client else "unknown",
        )
        item = await payload(request, ExchangeInvitation)
        session = await run_in_threadpool(service.exchange_invitation, item.token)
        response = JSONResponse({"csrf": service.csrf(session)})
        response.set_cookie(
            COOKIE,
            session,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
            max_age=3600,
        )
        return response

    @app.get("/api/portal/workspace")
    def view(request: Request):
        session = token(request)
        return JSONResponse(
            jsonable_encoder(
                {
                    **service.view(session),
                    "csrf": service.csrf(session),
                    "capabilities": {
                        "document_upload": document_store is not None,
                        "toolost": False,
                        "dealflow": service.dealflow_enabled,
                    },
                }
            )
        )

    @app.post("/api/portal/access-request", status_code=202)
    async def recovery(request: Request):
        await run_in_threadpool(
            service.throttle_exchange,
            request.client.host if request.client else "unknown",
        )
        item = await payload(
            request,
            LiveRequestAccess
            if service.settings.mode == "production"
            else RequestAccess,
        )
        return await run_in_threadpool(service.request_access, item)

    if document_store is not None:

        async def read_document(request):
            content = bytearray()
            async for chunk in request.stream():
                if len(content) + len(chunk) > 25 * 1024 * 1024:
                    raise ReviewError("invalid_document_size", 413)
                content.extend(chunk)
            return bytes(content)

        @app.post("/api/portal/documents", status_code=202)
        @app.post("/api/portal/questions/{question_id}/documents", status_code=202)
        async def upload(request: Request, question_id: UUID = None):
            session = token(request)
            state = await run_in_threadpool(service.view, session)
            if state["role"] != "owner":
                raise ReviewError("owner_required", 403)
            if request.headers.get("content-type") != "application/octet-stream":
                raise ReviewError("binary_document_required", 415)
            try:
                request_id = UUID(request.headers.get("x-upload-id", ""))
                filename = unquote(
                    request.headers.get("x-document-name", ""), errors="strict"
                )
                filename = Upload(filename=filename).filename
                length = int(request.headers.get("content-length", "0"))
            except (ValueError, UnicodeError):
                raise ReviewError("invalid_fields", 422) from None
            if length < 0 or length > 25 * 1024 * 1024:
                raise ReviewError("invalid_document_size", 413)
            if not uploads.acquire(blocking=False):
                raise ReviewError("uploads_busy", 429)
            try:
                try:
                    content = await asyncio.wait_for(
                        read_document(request), timeout=UPLOAD_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    raise ReviewError("upload_timed_out", 408) from None
                return await run_in_threadpool(
                    service.quarantine,
                    session,
                    filename,
                    content,
                    document_store,
                    request_id,
                    str(question_id) if question_id else None,
                )
            finally:
                uploads.release()

        @app.get("/api/portal/documents/{document_id}")
        def download(request: Request, document_id: UUID):
            # Downloads are same-origin and session-authorized on every read.
            # Never render PDF/CSV/XLSX in the portal's origin.
            _, content = service.download(
                token(request), str(document_id), document_store
            )
            return Response(
                content,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": 'attachment; filename="catalog-document"',
                },
            )

    @app.put("/api/portal/draft")
    async def save(request: Request):
        item = await payload(request, SaveDraft)
        return await run_in_threadpool(service.save_draft, token(request), item)

    if service.dealflow_enabled:
        @app.get("/api/portal/dealflow")
        def dealflow(request: Request):
            return service.dealflow_view(token(request))

        @app.post("/api/portal/dealflow/reviews")
        async def review_dealflow(request: Request):
            item = await payload(request, ReviewRecord)
            return await run_in_threadpool(service.save_dealflow_review, token(request), item)

        @app.post("/api/portal/dealflow/packages")
        async def prepare_package(request: Request):
            item = await payload(request, PackageRequest)
            return await run_in_threadpool(service.prepare_dealflow_package, token(request), item)

        @app.post("/api/portal/dealflow/packages/{package_id}/decision")
        async def decide_package(request: Request, package_id: UUID):
            item = await payload(request, ShareDecision)
            return await run_in_threadpool(service.decide_dealflow_package, token(request), package_id, item)

        @app.get("/api/portal/dealflow/packages/{package_id}/approved")
        def approved_package(request: Request, package_id: UUID):
            return service.approved_dealflow_package(token(request), package_id)

    @app.post("/api/portal/submission")
    async def submit(request: Request):
        item = await payload(request, Submit)
        return await run_in_threadpool(service.submit, token(request), item)

    @app.post("/api/portal/deletion-request")
    def delete(request: Request):
        return service.request_deletion(token(request))

    @app.post("/api/portal/continue-interest")
    async def keep(request: Request):
        item = await payload(request, ContinueInterest)
        return await run_in_threadpool(
            service.continue_interest, token(request), item.request_id
        )

    @app.get("/api/portal/export")
    def export(request: Request):
        return JSONResponse(
            jsonable_encoder(service.export_case(token(request))),
            headers={
                "Content-Disposition": 'attachment; filename="space-review-export.json"'
            },
        )

    @app.post("/api/portal/questions")
    async def ask(request: Request):
        item = await payload(request, ReviewQuestion)
        return await run_in_threadpool(service.ask_question, token(request), item)

    @app.post("/api/portal/questions/{question_id}/reply")
    async def reply(request: Request, question_id: UUID):
        item = await payload(request, ReviewReply)
        return await run_in_threadpool(
            service.reply_to_question, token(request), question_id, item
        )

    @app.delete("/api/portal/session")
    def logout(request: Request):
        service.logout(token(request))
        response = Response(status_code=204)
        response.delete_cookie(
            COOKIE, secure=True, httponly=True, samesite="lax", path="/"
        )
        return response

    if staff_router is not None:
        app.include_router(staff_router)
    if intake_router is not None:
        app.include_router(intake_router)

    return app
