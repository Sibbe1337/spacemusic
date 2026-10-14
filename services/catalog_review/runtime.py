"""Composition hook for reviewed deployments; no ambient secrets or test doubles.

The safe operations entrypoint stays closed until real adapters and current
deployment evidence are explicitly supplied here. This module does not provision
resources, enroll staff, enable invitations, or enable Too Lost.
"""

import hmac

from fastapi.responses import JSONResponse

from .http import COOKIE, create_application
from .intake_http import create_intake_router
from .operations.asgi import GuardedApplication
from .security import ReviewError


def compose_portal(
    *,
    config,
    gate,
    status_provider,
    service,
    document_store,
    staff,
    intake,
    wrap_guard=True,
):
    from .staff.config import StaffError
    from .staff.http import SESSION_COOKIE, create_staff_router

    config.validate()
    if type(wrap_guard) is not bool:
        raise ValueError("Explicit guard selection required")
    service.settings.validate()
    if (
        service.settings.mode != config.environment
        or service.settings.origin != config.origin
    ):
        raise RuntimeError("Core deployment binding mismatch")
    if (
        staff.settings.origin != config.origin
        or staff.settings.generation != config.generation
        or staff.settings.client_id != config.google_client_id
    ):
        raise RuntimeError("Staff deployment binding mismatch")
    if (
        service.settings.generation != config.generation
        or document_store is None
        or service.deletion_journal is None
        or not hmac.compare_digest(
            service.settings.source_identity_key, intake._source_key
        )
    ):
        raise RuntimeError("Private portal dependencies missing")

    def reviewer_authorizer(db, reference, workspace):
        try:
            return staff.authorize_reviewer_digest_in_transaction(
                db, reference, workspace
            )
        except StaffError as error:
            raise ReviewError(error.code, error.status) from None

    service.staff_authorizer = reviewer_authorizer

    def context(db, identity):
        session = service.establish_reviewer_context(db, identity)
        response = JSONResponse({"csrf": service.csrf(session), "next": "/workspace/"})
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

    def principal(request):
        token = request.cookies.get(SESSION_COOKIE, "")
        try:
            with staff.require_operator(token):
                return token
        except StaffError as error:
            raise ReviewError(error.code, error.status) from None

    def csrf(request, token):
        return hmac.compare_digest(
            request.headers.get("x-csrf-token", ""), staff.csrf(token)
        )

    def ingress(request):
        service.throttle_exchange(request.client.host if request.client else "unknown")
        return True

    def actor(db, token, action):
        if action == "intake.approve":
            runtime, restore = status_provider()
            if config.environment == "production":
                gate.require_invitations(
                    now=service.clock(), runtime=runtime, restore=restore
                )
            elif not gate.evaluate(
                now=service.clock(), runtime=runtime, restore=restore
            ).ready:
                raise ReviewError("staging_not_ready", 503)
        mapped = "intake_approve" if action == "intake.approve" else "intake_list"
        try:
            return staff.authorize_operator_in_transaction(
                db, token, mapped
            ).principal_id
        except StaffError as error:
            raise ReviewError(error.code, error.status) from None

    # Bind intake to current staff authorization, not a cached role boolean.
    intake._authorize_staff = actor
    intake._ingest = service.ingest_in_transaction
    intake._source_suppressed = service.deletion_journal.suppresses
    service.intake_exporter = intake.export_in_transaction

    def workspace_guard(db, workspace):
        db.execute("SET LOCAL search_path TO public,pg_catalog")
        db.execute("SELECT set_config('space.workspace_id',%s,true)", (workspace,))
        try:
            service._active(db, workspace)
            return True
        except ReviewError as error:
            if error.code == "workspace_unavailable":
                return False
            raise

    staff_routes = create_staff_router(
        staff, establish_context=context, workspace_guard=workspace_guard
    )
    intake_routes = create_intake_router(
        intake,
        origin=config.origin,
        staff_identity=principal,
        validate_csrf=csrf,
        admit_webhook=ingress,
    )
    app = create_application(
        service,
        document_store=document_store,
        staff_router=staff_routes,
        intake_router=intake_routes,
    )
    # build_runtime owns the sole outer operations guard. Direct composition
    # stays guarded by default; only its trusted builder selects the inner app.
    if not wrap_guard:
        return app

    def intake_ready():
        runtime, restore = status_provider()
        return gate.evaluate(
            now=service.clock(), runtime=runtime, restore=restore
        ).ready

    return GuardedApplication(
        config,
        gate,
        application=app,
        status_provider=status_provider,
        clock=service.clock,
        typeform_signature_handler=intake.receive_typeform,
        typeform_health=intake_ready,
    )
