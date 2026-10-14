"""Composition contract: explicitly bound objects, not all-green JSON switches.

The application builder and probes are trusted deployment code. Python cannot
prove an injected object's authenticity. Audit these bindings in launch review;
never derive probe success from configuration or manufacture fresh timestamps for
old observations. No fake implementation is included in this module or image.
"""

from dataclasses import dataclass
from datetime import timedelta
from types import MappingProxyType

from .asgi import GuardedApplication
from .gates import CHECKS, LaunchBlocked, LaunchGate, RuntimeState, now_utc, utc

# Names match LaunchGate's health checks. Checks without a domain interface are
# callable, read-only verifier hooks maintained by the composition root.
REQUIRED_ADAPTERS = {
    "database": ("transaction",),
    "rls": (),
    "migrations": (),
    "core_origin": (),
    "identity": ("begin_oidc", "complete_oidc"),
    "webauthn_uv": ("begin_uv", "complete_uv", "authorized"),
    "mail": ("dispatch", "dispatch_retention", "refresh", "refresh_retention"),
    "storage": ("put_if_absent", "get", "delete"),
    "scanner": ("inspect",),
    "parser": ("inspect",),
    "retention": ("retention_state", "expire_inactive"),
    "journal": ("contains", "suppresses", "record", "reconcile"),
}


@dataclass(frozen=True)
class ProbeResult:
    healthy: bool
    checked_at: object
    generation: str
    config_sha256: str


@dataclass(frozen=True)
class AdapterBinding:
    value: object
    mode: str
    probe: object


class GuardedMailDispatcher:
    def __init__(self, dispatcher, require_invitations):
        self._dispatcher = dispatcher
        self._require_invitations = require_invitations

    def dispatch(self, *args, **kwargs):
        self._require_invitations()
        return self._dispatcher.dispatch(*args, **kwargs)

    def refresh(self, *args, **kwargs):
        return self._dispatcher.refresh(*args, **kwargs)

    def dispatch_retention(self, *args, **kwargs):
        self._require_invitations()
        return self._dispatcher.dispatch_retention(*args, **kwargs)

    def refresh_retention(self, *args, **kwargs):
        self._require_invitations()
        return self._dispatcher.refresh_retention(*args, **kwargs)


def _binding_valid(binding, methods, synthetic):
    return (
        isinstance(binding, AdapterBinding)
        and binding.mode == ("synthetic" if synthetic else "live")
        and binding.value is not None
        and callable(binding.probe)
        and (
            all(callable(getattr(binding.value, name, None)) for name in methods)
            if methods
            else callable(binding.value)
        )
    )


def build_runtime(
    config, *, adapters, app_builder, restore_provider, manifest=None, clock=now_utc
):
    """Return an ASGI app, closed if any required adapter is absent/invalid.

    app_builder(config=..., adapters=read_only_mapping, require_invitations=callable,
                gate=..., status_provider=...)
    must construct the NON-TEST application and use the supplied adapters, including
    receive_typeform(raw_body, signature) on the exact Typeform route when supplied.

    Probes return ProbeResult from a bounded collector, not booleans. Check methods
    and probes do not run at construction. Failed/missing probes deny each action.
    Synthetic staging must supply exclusively synthetic bindings; it can exercise
    invitation workflows but LaunchGate.invitations_allowed remains production-only.
    """
    config.validate()
    gate = LaunchGate(config, manifest)
    supplied = dict(adapters)
    blockers = []
    for name, methods in REQUIRED_ADAPTERS.items():
        if not _binding_valid(supplied.get(name), methods, config.synthetic_staging):
            blockers.append("adapter_" + name)
    if set(supplied) - set(REQUIRED_ADAPTERS) - {"typeform_intake"}:
        blockers.append("unknown_adapter")
    if "typeform_intake" in supplied and not _binding_valid(
        supplied["typeform_intake"], ("receive_typeform",), config.synthetic_staging
    ):
        blockers.append("adapter_typeform_intake")
    if not callable(app_builder) or not callable(restore_provider):
        blockers.append("runtime_builder_or_restore_provider_missing")
    if blockers:
        closed = GuardedApplication(config, gate, clock=clock)
        closed.startup_blockers = tuple(blockers)
        return closed

    def healthy(binding):
        try:
            result = binding.probe()
            return (
                isinstance(result, ProbeResult)
                and result.healthy is True
                and result.generation == config.generation
                and result.config_sha256 == config.fingerprint
                and timedelta(0)
                <= utc(clock()) - utc(result.checked_at)
                <= timedelta(seconds=30)
            )
        except Exception:
            return False

    def status():
        observed = clock()
        checks = tuple((name, healthy(supplied[name])) for name in sorted(CHECKS))
        return RuntimeState(
            config.generation, config.fingerprint, observed, checks
        ), restore_provider()

    def require_invitations():
        try:
            runtime, restore = status()
            decision = gate.evaluate(now=clock(), runtime=runtime, restore=restore)
            allowed = (
                decision.ready
                if config.synthetic_staging
                else decision.invitations_allowed
            )
        except Exception:
            allowed = False
        if not allowed:
            raise LaunchBlocked("production_invitations_blocked")

    bound_values = {name: binding.value for name, binding in supplied.items()}
    bound_values["mail"] = GuardedMailDispatcher(
        bound_values["mail"], require_invitations
    )
    values = MappingProxyType(bound_values)
    application = app_builder(
        config=config,
        adapters=values,
        require_invitations=require_invitations,
        gate=gate,
        status_provider=status,
    )
    if not callable(application):
        raise ValueError("asgi_application_required")
    typeform = supplied.get("typeform_intake")
    app = GuardedApplication(
        config,
        gate,
        application=application,
        status_provider=status,
        clock=clock,
        typeform_signature_handler=typeform.value.receive_typeform
        if typeform
        else None,
        typeform_health=(lambda: healthy(typeform)) if typeform else None,
    )
    app.require_invitations = require_invitations
    app.adapters = values
    return app
