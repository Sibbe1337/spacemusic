"""Mountable intake router; no ASGI app creation or changes to core middleware.

Main must make ONLY /api/intake/typeform a provider-authenticated middleware
exception. It is not cookie/CSRF authenticated; all staff routes remain private.
staff_identity(request) returns an opaque server-authentication handle, not claims
from JSON. IntakeService reauthorizes that handle through authorize_staff.
validate_csrf(request, principal) must return True or raise. admit_webhook(request)
must enforce server-side peer throttling and return True or raise.
"""

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .intake import MAX_BODY, _strict_object
from .mail import PORTAL_ORIGINS
from .security import ReviewError

HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


def _response(value, status=200):
    return JSONResponse(jsonable_encoder(value), status_code=status, headers=HEADERS)


async def _body(request, limit):
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise ReviewError("json_required", 415)
    lengths = request.headers.getlist("content-length")
    try:
        if len(lengths) > 1 or (lengths and not 0 <= int(lengths[0]) <= limit):
            raise ValueError()
    except ValueError:
        raise ReviewError("intake_body_limit", 413) from None

    async def read():
        result = bytearray()
        async for chunk in request.stream():
            if len(result) + len(chunk) > limit:
                raise ReviewError("intake_body_limit", 413)
            result.extend(chunk)
        return bytes(result)

    try:
        return await asyncio.wait_for(read(), timeout=10)
    except asyncio.TimeoutError:
        raise ReviewError("intake_read_timeout", 408) from None


async def _fields(request, required, optional=()):
    raw = await _body(request, 16384)
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
        if (
            not isinstance(value, dict)
            or not set(required) <= set(value)
            or set(value) - set(required) - set(optional)
        ):
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ReviewError("invalid_fields", 422) from None


def create_intake_router(
    service, *, origin, staff_identity, validate_csrf, admit_webhook
):
    if origin not in PORTAL_ORIGINS or not all(
        callable(f) for f in (staff_identity, validate_csrf, admit_webhook)
    ):
        raise ValueError("Trusted intake router dependencies required")
    router = APIRouter()

    def boundary(request):
        if str(request.base_url).rstrip("/") != origin or request.url.query:
            raise ReviewError("invalid_intake_origin", 403)

    async def staff(request):
        boundary(request)
        origins = request.headers.getlist("origin")
        sites = request.headers.getlist("sec-fetch-site")
        if (
            sites != ["same-origin"]
            or len(origins) > 1
            or (origins and origins != [origin])
        ):
            raise ReviewError("origin_denied", 403)
        principal = await run_in_threadpool(staff_identity, request)
        if principal is None:
            raise ReviewError("authentication_required", 401)
        if request.method != "GET":
            if (
                origins != [origin]
                or await run_in_threadpool(validate_csrf, request, principal)
                is not True
            ):
                raise ReviewError("csrf_denied", 403)
        return principal

    async def handle(operation):
        try:
            return await operation()
        except ReviewError as error:
            return _response({"error": error.code}, error.status)
        except Exception:
            return _response({"error": "temporarily_unavailable"}, 503)

    @router.post("/api/intake/typeform")
    async def typeform(request: Request):
        async def operation():
            boundary(request)
            if request.headers.getlist("origin") or request.headers.getlist(
                "sec-fetch-site"
            ):
                raise ReviewError("provider_request_required", 403)
            if await run_in_threadpool(admit_webhook, request) is not True:
                raise ReviewError("try_again_later", 429)
            signatures = request.headers.getlist("typeform-signature")
            if len(signatures) != 1:
                raise ReviewError("invalid_intake_signature", 401)
            raw = await _body(request, MAX_BODY)
            await run_in_threadpool(service.receive_typeform, raw, signatures[0])
            # Never expose intake IDs, suppression state or contact data publicly.
            return _response({"status": "request_received"}, 202)

        return await handle(operation)

    @router.get("/api/staff/intakes")
    async def listing(request: Request):
        async def operation():
            principal = await staff(request)
            return _response(
                {"intakes": await run_in_threadpool(service.list_receipts, principal)}
            )

        return await handle(operation)

    @router.get("/api/staff/intakes/{intake_id}")
    async def detail(request: Request, intake_id: str):
        async def operation():
            principal = await staff(request)
            return _response(
                await run_in_threadpool(service.read_receipt, principal, intake_id)
            )

        return await handle(operation)

    @router.post("/api/staff/intakes/formspree-receipt")
    async def manual(request: Request):
        async def operation():
            principal = await staff(request)
            fields = await _fields(
                request, ("receipt_id", "email", "submitted_at"), ("landing_path",)
            )
            return _response(
                await run_in_threadpool(
                    service.record_formspree_receipt, principal, **fields
                ),
                202,
            )

        return await handle(operation)

    @router.post("/api/staff/intakes/{intake_id}/approve")
    async def approve(request: Request, intake_id: str):
        async def operation():
            principal = await staff(request)
            fields = await _fields(request, ("request_id", "owner_authority_confirmed"))
            return _response(
                await run_in_threadpool(
                    service.approve, principal, intake_id=intake_id, **fields
                )
            )

        return await handle(operation)

    return router
