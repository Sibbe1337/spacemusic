"""Opt-in staff router. Main application owns mounting and callback boundary exceptions."""

import asyncio
import hmac
import json

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from .config import GOOGLE_ISSUER, StaffError

SESSION_COOKIE = "__Host-space_staff"
OIDC_COOKIE = "__Host-space_staff_oidc"
CALLBACK_PATH = "/api/staff/oidc/callback"
START_PATH = "/api/staff/oidc/start"
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
}


def _cookie(response, name, value, max_age):
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )


def _clear(response, name):
    response.delete_cookie(name, secure=True, httponly=True, samesite="lax", path="/")


async def _payload(request, required=(), optional=()):
    if (
        request.headers.get("content-type", "").split(";")[0].strip()
        != "application/json"
    ):
        raise StaffError("staff_json_required", 415)

    async def read():
        content = bytearray()
        async for chunk in request.stream():
            if len(content) + len(chunk) > 65536:
                raise StaffError("staff_request_too_large", 413)
            content.extend(chunk)
        return bytes(content)

    try:

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError()
                result[key] = value
            return result

        value = json.loads(
            await asyncio.wait_for(read(), timeout=10), object_pairs_hook=unique
        )
        if (
            not isinstance(value, dict)
            or not set(required) <= value.keys()
            or value.keys() - set(required) - set(optional)
        ):
            raise ValueError()
        return value
    except StaffError:
        raise
    except asyncio.TimeoutError:
        raise StaffError("staff_request_timeout", 408) from None
    except (ValueError, TypeError, UnicodeError):
        raise StaffError("invalid_staff_fields", 422) from None


def create_staff_router(service, *, establish_context=None, workspace_guard=None):
    """establish_context(db, identity) -> Response runs in the authorization txn.

    The coordinator sets core tenant context, locks/rechecks membership, writes
    its portal session/link and returns its own secure cookie Response. Staff
    identities contain session_reference (a digest), never the raw staff cookie.
    workspace_guard(db, workspace_id) -> bool gates the assigned-ID list against
    the external deletion journal AND current core row; absent/errors fail closed.
    """
    service.settings.validate()

    def token(request):
        value = request.cookies.get(SESSION_COOKIE)
        if not value:
            raise StaffError()
        return value

    class StaffRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()

            async def guarded(request):
                callback = request.url.path == CALLBACK_PATH and request.method == "GET"
                try:
                    if (
                        request.url.scheme != "https"
                        or request.headers.get("host") != service.settings.rp_id
                    ):
                        raise StaffError("invalid_staff_origin", 400)
                    if not callback and request.url.query:
                        raise StaffError("staff_query_denied", 400)
                    if callback:
                        if (
                            request.headers.get("sec-fetch-mode", "navigate")
                            != "navigate"
                            or request.headers.get("sec-fetch-dest", "document")
                            != "document"
                        ):
                            raise StaffError("staff_callback_navigation_required", 403)
                    elif request.headers.get("sec-fetch-site") == "cross-site":
                        raise StaffError("staff_cross_site_denied", 403)
                    if request.method not in ("GET", "HEAD", "OPTIONS"):
                        if request.headers.get("origin") != service.settings.origin:
                            raise StaffError("staff_origin_denied", 403)
                        if not (
                            request.url.path == START_PATH and request.method == "POST"
                        ):
                            expected = service.csrf(token(request))
                            if not hmac.compare_digest(
                                request.headers.get("x-csrf-token", ""), expected
                            ):
                                raise StaffError("staff_csrf_denied", 403)
                    response = await original(request)
                except StaffError as error:
                    response = JSONResponse(
                        {"error": error.code}, status_code=error.status
                    )
                except Exception:
                    response = JSONResponse(
                        {"error": "staff_temporarily_unavailable"}, status_code=503
                    )
                if callback:
                    _clear(response, OIDC_COOKIE)
                response.headers.update(HEADERS)
                return response

            return guarded

    router = APIRouter(prefix="/api/staff", route_class=StaffRoute)

    @router.post("/oidc/start")
    async def start(request: Request):
        await _payload(request)
        result = await run_in_threadpool(service.begin_oidc)
        response = JSONResponse({"authorization_url": result["authorization_url"]})
        _cookie(response, OIDC_COOKIE, result["browser_binding"], 300)
        return response

    @router.get("/oidc/callback")
    async def callback(request: Request):
        items = list(request.query_params.multi_items())
        query = dict(items)
        allowed = {"state", "code", "error", "scope", "authuser", "prompt", "iss"}
        if (
            len(request.url.query) > 8192
            or len(items) != len(query)
            or not query.get("state")
            or query.keys() - allowed
            or ("code" in query) == ("error" in query)
            or ("iss" in query and query["iss"] != GOOGLE_ISSUER)
        ):
            raise StaffError("invalid_staff_callback", 400)
        binding = request.cookies.get(OIDC_COOKIE, "")
        if "error" in query:
            await run_in_threadpool(
                service.cancel_oidc, state=query["state"], browser_binding=binding
            )
            raise StaffError("staff_oidc_cancelled", 401)
        session = await run_in_threadpool(
            service.complete_oidc,
            state=query["state"],
            browser_binding=binding,
            code=query["code"],
        )
        response = RedirectResponse("/staff/", status_code=303)
        _cookie(response, SESSION_COOKIE, session, 3600)
        return response

    @router.get("/session")
    def session_status(request: Request):
        session = token(request)
        with service.require_session(session) as identity:
            return JSONResponse(
                jsonable_encoder(
                    {
                        "principal_id": identity.principal_id,
                        "display_name": identity.display_name,
                        "role": identity.role,
                        "state": identity.state,
                        "uv_at": identity.uv_at,
                        "expires_at": identity.expires_at,
                        "csrf": service.csrf(session),
                    }
                )
            )

    @router.delete("/session")
    def logout(request: Request):
        try:
            service.logout(token(request))
        except StaffError as error:
            if error.status != 401:
                raise
        response = Response(status_code=204)
        _clear(response, SESSION_COOKIE)
        _clear(response, OIDC_COOKIE)
        return response

    @router.post("/enrollment/options")
    async def enrollment_options(request: Request):
        item = await _payload(request, ("permit",))
        return await run_in_threadpool(
            service.begin_enrollment, token(request), item["permit"]
        )

    @router.post("/enrollment/verify")
    async def enrollment_verify(request: Request):
        item = await _payload(request, ("challenge_id", "credential"))
        return await run_in_threadpool(
            service.complete_enrollment,
            token(request),
            item["challenge_id"],
            item["credential"],
        )

    @router.post("/assertion/options")
    async def assertion_options(request: Request):
        item = await _payload(request, optional=("confirm_credential",))
        return await run_in_threadpool(
            service.begin_uv,
            token(request),
            confirm_credential=item.get("confirm_credential"),
        )

    @router.post("/assertion/verify")
    async def assertion_verify(request: Request):
        item = await _payload(
            request, ("challenge_id", "credential"), ("confirmation",)
        )
        if type(item.get("confirmation", False)) is not bool:
            raise StaffError("invalid_staff_fields", 422)
        return await run_in_threadpool(
            service.complete_uv,
            token(request),
            item["challenge_id"],
            item["credential"],
            confirmation=item.get("confirmation", False),
        )

    @router.get("/workspaces")
    def workspaces(request: Request):
        return service.list_workspaces(token(request), workspace_guard=workspace_guard)

    @router.post("/workspaces/{workspace}/context")
    async def context(request: Request, workspace: str):
        await _payload(request)
        if establish_context is None:
            raise StaffError("staff_context_unavailable", 503)
        session = token(request)

        def establish():
            with service.repo.transaction() as db:
                identity = service.authorize_in_transaction(db, session, workspace)
                response = establish_context(db, identity)
                if not isinstance(response, Response):
                    raise RuntimeError(
                        "Context hook must return its secure cookie Response"
                    )
                return response

        return await run_in_threadpool(establish)

    return router
