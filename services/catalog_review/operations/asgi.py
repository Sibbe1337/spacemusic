"""Fail-closed ASGI integration hook; default image exposes only health routes."""

import json
import os

from .config import OperationsConfig, load_json
from .gates import Decision, LaunchGate, LaunchManifest, now_utc


class GuardedApplication:
    """Wrap the coordinator's ASGI app; never manufactures real health evidence.

    status_provider returns (RuntimeState, RestoreState), using cached observations
    no older than 30 seconds. The trusted collector must do bounded real probes.
    Workers must independently call LaunchGate.require_invitations before sending.
    """

    def __init__(
        self,
        config,
        gate,
        *,
        application=None,
        status_provider=None,
        clock=now_utc,
        typeform_signature_handler=None,
        typeform_health=None,
    ):
        self.config = config.validate()
        if gate.config.fingerprint != config.fingerprint:
            raise ValueError("gate_configuration_mismatch")
        self.gate = gate
        self.application = application
        self.status_provider = status_provider
        self.clock = clock
        self.typeform_signature_handler = typeform_signature_handler
        self.typeform_health = typeform_health
        self.startup_blockers = ()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            if self.application is not None:
                return await self.application(scope, receive, send)
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] != "http":
            return
        # TLS is terminated only by the trusted local reverse proxy. Configure
        # ASGI forwarded-header trust narrowly, never '*'.
        hosts = [v for k, v in scope.get("headers", []) if k.lower() == b"host"]
        expected = self.config.origin.removeprefix("https://").encode()
        if scope.get("scheme") != "https" or hosts != [expected]:
            return await self._respond(send, 400, "invalid_boundary")
        path = scope.get("path", "")
        if path == "/health/live" and scope["method"] in ("GET", "HEAD"):
            return await self._respond(
                send, 200, "live", head=scope["method"] == "HEAD"
            )
        decision = Decision(False, False, ("integration_missing",))
        if self.application is not None and self.status_provider is not None:
            try:
                runtime, restore = self.status_provider()
                decision = self.gate.evaluate(
                    now=self.clock(), runtime=runtime, restore=restore
                )
            except Exception:
                pass
        if path == "/health/ready" and scope["method"] in ("GET", "HEAD"):
            return await self._respond(
                send,
                200 if decision.ready else 503,
                "ready" if decision.ready else "blocked",
                head=scope["method"] == "HEAD",
            )
        if not decision.ready:
            return await self._respond(send, 503, "launch_blocked")
        # No cross-origin API requests, including same-site sibling origins.
        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            origins = [v for k, v in scope.get("headers", []) if k.lower() == b"origin"]
            server_webhook = (
                scope["method"] == "POST"
                and path == "/api/intake/typeform"
                and not scope.get("query_string", b"")
                and not origins
                and not any(
                    k.lower().startswith(b"sec-fetch-")
                    for k, _ in scope.get("headers", [])
                )
                and callable(self.typeform_signature_handler)
                and callable(self.typeform_health)
            )
            if server_webhook:
                try:
                    server_webhook = self.typeform_health() is True
                except Exception:
                    server_webhook = False
            if origins != [self.config.origin.encode()] and not server_webhook:
                return await self._respond(send, 403, "origin_denied")
        return await self.application(scope, receive, send)

    @staticmethod
    async def _respond(send, status, message, *, head=False):
        content = json.dumps({"status": message}, separators=(",", ":")).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-robots-tag", b"noindex, nofollow"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"" if head else content})


def create_app():
    """Safe default: cannot become ready even with a fabricated all-green file."""
    config = OperationsConfig.from_mapping(
        load_json(os.environ["REVIEW_OPERATIONS_CONFIG"])
    )
    manifest_path = os.environ.get("REVIEW_LAUNCH_MANIFEST")
    manifest = (
        LaunchManifest.from_mapping(load_json(manifest_path)) if manifest_path else None
    )
    return GuardedApplication(config, LaunchGate(config, manifest))
