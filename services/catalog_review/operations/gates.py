"""Evidence is an operator attestation, not automatic vendor/legal verification.

Mount manifests read-only outside application backups. Status collectors must
check real integrations; a manifest cannot replace a functioning integration.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .config import ConfigurationError, canonical_uuid, require, sha256_value

EVIDENCE = frozenset(
    {
        "legal_entity",
        "operator",
        "vendor_residency",
        "price",
        "identity",
        "mail_delivery",
        "parser_isolation",
        "restore_drill",
        "security_review",
        "customer_pilot_approval",
    }
)
TECHNICAL_EVIDENCE = EVIDENCE - {"legal_entity", "price", "customer_pilot_approval"}
CHECKS = frozenset(
    {
        "database",
        "rls",
        "migrations",
        "core_origin",
        "identity",
        "webauthn_uv",
        "mail",
        "storage",
        "scanner",
        "parser",
        "retention",
        "journal",
    }
)


def utc(value):
    require(
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0),
        "utc_timestamp_required",
    )
    return value


def timestamp(value):
    try:
        require(isinstance(value, str), "timestamp_required")
        return utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (TypeError, ValueError):
        raise ConfigurationError("invalid_timestamp") from None


@dataclass(frozen=True)
class Evidence:
    sha256: str
    verified_by: str
    verified_at: datetime
    expires_at: datetime

    def valid_at(self, now):
        return (
            sha256_value(self.sha256)
            and isinstance(self.verified_by, str)
            and 1 <= len(self.verified_by.strip()) <= 200
            and utc(self.verified_at) <= now < utc(self.expires_at)
            and self.expires_at - self.verified_at <= timedelta(days=90)
        )


@dataclass(frozen=True)
class LaunchManifest:
    environment: str
    generation: str
    config_sha256: str
    release_sha256: str
    legal_name: str
    organization_number: str
    operator: str
    approved_monthly_sek: int
    invitations_approved: bool
    evidence: tuple

    @classmethod
    def from_mapping(cls, value):
        try:
            require(isinstance(value, dict), "manifest_object_required")
            data = dict(value)
            version = data.pop("schema_version")
            require(type(version) is int and version == 1, "manifest_version_required")
            raw = data.pop("evidence")
            require(
                isinstance(raw, dict) and set(raw) <= EVIDENCE, "invalid_evidence_keys"
            )
            items = []
            for name, fields in raw.items():
                record = dict(fields)
                record["verified_at"] = timestamp(record["verified_at"])
                record["expires_at"] = timestamp(record["expires_at"])
                items.append((name, Evidence(**record)))
            return cls(evidence=tuple(items), **data)
        except (TypeError, KeyError, ValueError):
            raise ConfigurationError("invalid_launch_manifest") from None


@dataclass(frozen=True)
class RuntimeState:
    generation: str
    config_sha256: str
    checked_at: datetime
    checks: tuple


@dataclass(frozen=True)
class RestoreState:
    generation: str
    session_generation: str
    journal_head: int
    replayed_through: int
    verified_at: datetime
    objects_verified: bool
    source_tombstones_reconciled: bool = False


@dataclass(frozen=True)
class Decision:
    ready: bool
    invitations_allowed: bool
    blockers: tuple


class LaunchBlocked(RuntimeError):
    """Never include evidence contents, recipient details or credentials."""


class LaunchGate:
    def __init__(self, config, manifest=None):
        self.config = config.validate()
        self.manifest = manifest

    def evaluate(self, *, now, runtime=None, restore=None):
        """Re-evaluate for every guarded action. No stale allow decision is cached."""
        try:
            return self._evaluate(utc(now), runtime, restore)
        except (ConfigurationError, TypeError, ValueError, AttributeError):
            return Decision(False, False, ("invalid_gate_state",))

    def _evaluate(self, now, runtime, restore):
        config = self.config.validate()
        blockers = []
        manifest = self.manifest
        if config.synthetic_staging:
            # This opt-in is rejected by production configuration. Runtime and
            # restore checks still apply; the factory accepts synthetic bindings
            # only, including non-sending mail, for this mode.
            pass
        elif not isinstance(manifest, LaunchManifest):
            blockers.append("launch_manifest_missing")
        else:
            if (
                manifest.environment != config.environment
                or manifest.generation != config.generation
                or manifest.config_sha256 != config.fingerprint
                or manifest.release_sha256 != config.release_sha256
            ):
                blockers.append("launch_manifest_binding")
            evidence = dict(manifest.evidence)
            if len(evidence) != len(manifest.evidence) or not set(evidence) <= EVIDENCE:
                blockers.append("invalid_evidence")
            needed = (
                EVIDENCE if config.environment == "production" else TECHNICAL_EVIDENCE
            )
            for name in sorted(needed):
                item = evidence.get(name)
                if not isinstance(item, Evidence) or not item.valid_at(now):
                    blockers.append("evidence_" + name)
            if not isinstance(manifest.operator, str) or not manifest.operator.strip():
                blockers.append("operator_missing")
            if config.environment == "production":
                if not all(
                    isinstance(v, str) and v.strip()
                    for v in (manifest.legal_name, manifest.organization_number)
                ):
                    blockers.append("legal_identity_missing")
                if (
                    type(manifest.approved_monthly_sek) is not int
                    or not config.planning_sek
                    <= manifest.approved_monthly_sek
                    <= config.ceiling_sek
                ):
                    blockers.append("price_approval_missing")
                if manifest.invitations_approved is not True:
                    blockers.append("pilot_not_approved")
        if not isinstance(runtime, RuntimeState):
            blockers.append("runtime_state_missing")
        else:
            if (
                runtime.generation != config.generation
                or runtime.config_sha256 != config.fingerprint
            ):
                blockers.append("runtime_binding")
            if (
                not timedelta(0)
                <= now - utc(runtime.checked_at)
                <= timedelta(seconds=30)
            ):
                blockers.append("runtime_state_stale")
            checks = dict(runtime.checks)
            if len(checks) != len(runtime.checks) or set(checks) != CHECKS:
                blockers.append("runtime_checks_invalid")
            for name in sorted(CHECKS):
                if checks.get(name) is not True:
                    blockers.append("integration_" + name)
        if not isinstance(restore, RestoreState):
            blockers.append("restore_state_missing")
        else:
            if (
                not canonical_uuid(restore.generation)
                or restore.generation != config.generation
                or restore.session_generation != config.generation
            ):
                blockers.append("restore_generation_mismatch")
            if (
                type(restore.journal_head) is not int
                or type(restore.replayed_through) is not int
                or restore.journal_head < 0
                or restore.replayed_through != restore.journal_head
            ):
                blockers.append("journal_replay_incomplete")
            if restore.objects_verified is not True:
                blockers.append("restore_objects_unverified")
            if restore.source_tombstones_reconciled is not True:
                blockers.append("source_tombstones_unreconciled")
            if (
                not timedelta(0)
                <= now - utc(restore.verified_at)
                <= timedelta(seconds=30)
            ):
                blockers.append("restore_state_stale")
        ready = not blockers
        return Decision(
            ready, ready and config.environment == "production", tuple(blockers)
        )

    def require_invitations(self, **status):
        if not self.evaluate(**status).invitations_allowed:
            raise LaunchBlocked("production_invitations_blocked")


def now_utc():
    return datetime.now(timezone.utc)
