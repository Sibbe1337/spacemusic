"""Strict, non-secret deployment configuration; never consult ambient DB URLs.

https://developers.cloudflare.com/r2/reference/data-location/
https://www.postgresql.org/docs/current/libpq-ssl.html
"""

import hashlib
import ipaddress
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID


class ConfigurationError(ValueError):
    """A deliberately value-free configuration error, safe to log."""


def require(condition, code):
    if not condition:
        raise ConfigurationError(code)


def canonical_uuid(value):
    try:
        return (
            isinstance(value, str)
            and str(UUID(value)) == value
            and UUID(value).int != 0
        )
    except (ValueError, AttributeError):
        return False


def sha256_value(value):
    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


def secret_path(value):
    return (
        isinstance(value, str)
        and re.fullmatch(r"/run/secrets/[a-zA-Z0-9_.-]+", value) is not None
        and PurePosixPath(value).name not in (".", "..")
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_configuration_field")
        result[key] = value
    return result


def _invalid_constant(_):
    raise ConfigurationError("nonfinite_json_forbidden")


def load_json(path, *, limit=65536):
    """Read bounded local JSON, rejecting duplicate fields and non-finite values."""
    try:
        with Path(path).open("rb") as stream:
            raw = stream.read(limit + 1)
        require(len(raw) <= limit, "configuration_too_large")
        result = json.loads(
            raw, object_pairs_hook=_pairs, parse_constant=_invalid_constant
        )
        require(isinstance(result, dict), "configuration_object_required")
        return result
    except (OSError, UnicodeError, ValueError, TypeError):
        raise ConfigurationError("invalid_configuration_file") from None


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    dbname: str
    user: str
    sslrootcert: str
    passfile: str
    port: int = 5432
    max_connections: int = 4
    checkout_timeout_seconds: float = 1.0

    def validate(self):
        require(isinstance(self.host, str), "database_host_required")
        try:
            address = ipaddress.ip_address(self.host)
            private = any(
                address in ipaddress.ip_network(net)
                for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
            )
            require(private, "private_database_address_required")
        except ValueError:
            require(
                re.fullmatch(
                    r"[a-z0-9](?:[a-z0-9.-]{0,240}[a-z0-9])?\.rdb\.fr-par\.scw\.cloud",
                    self.host,
                )
                is not None
                and ".." not in self.host,
                "paris_database_host_required",
            )
        require(
            self.dbname in ("review_prod", "review_staging"),
            "isolated_database_required",
        )
        require(
            self.user in ("review_runtime", "review_migration"),
            "database_role_required",
        )
        require(
            type(self.port) is int and 1 <= self.port <= 65535, "invalid_database_port"
        )
        require(
            secret_path(self.sslrootcert) and secret_path(self.passfile),
            "mounted_database_secrets_required",
        )
        require(
            self.sslrootcert != self.passfile,
            "independent_database_secret_files_required",
        )
        require(
            type(self.max_connections) is int and 1 <= self.max_connections <= 8,
            "invalid_pool_size",
        )
        require(
            type(self.checkout_timeout_seconds) in (int, float)
            and math.isfinite(self.checkout_timeout_seconds)
            and 0 < self.checkout_timeout_seconds <= 5,
            "invalid_checkout_timeout",
        )
        return self

    def connect_kwargs(self):
        self.validate()
        return dict(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            passfile=self.passfile,
            sslrootcert=self.sslrootcert,
            sslmode="verify-full",
            connect_timeout=5,
            application_name="catalog_review_operations",
            options="-c statement_timeout=5000 -c lock_timeout=3000 -c idle_in_transaction_session_timeout=15000",
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=3,
            tcp_user_timeout=15000,
        )


@dataclass(frozen=True)
class OperationsConfig:
    environment: str
    origin: str
    generation: str
    release_sha256: str
    database: DatabaseConfig
    r2_account_id: str
    document_bucket: str
    export_bucket: str
    journal_bucket: str
    independent_backup_bucket: str
    independent_journal_bucket: str
    google_client_id: str
    workspace_domain: str
    region: str = "fr-par"
    zone: str = "fr-par-1"
    scanner_socket: str = "/run/clamav/clamd.sock"
    inactivity_days: int = 90
    backup_retention_days: int = 7
    planning_sek: int = 1700
    ceiling_sek: int = 2000
    synthetic_staging: bool = False

    @classmethod
    def from_mapping(cls, value):
        try:
            require(isinstance(value, dict), "configuration_object_required")
            data = dict(value)
            data["database"] = DatabaseConfig(**data["database"])
            return cls(**data).validate()
        except (KeyError, TypeError):
            raise ConfigurationError("invalid_configuration_fields") from None

    def validate(self):
        require(self.environment in ("production", "staging"), "invalid_environment")
        require(
            type(self.synthetic_staging) is bool
            and (not self.synthetic_staging or self.environment == "staging"),
            "synthetic_production_forbidden",
        )
        expected = (
            "https://review.spacemusic.io"
            if self.environment == "production"
            else "https://review-staging.spacemusic.io"
        )
        require(self.origin == expected, "isolated_https_origin_required")
        require(canonical_uuid(self.generation), "external_generation_required")
        require(sha256_value(self.release_sha256), "release_digest_required")
        require(
            isinstance(self.database, DatabaseConfig), "database_configuration_required"
        )
        self.database.validate()
        require(
            self.database.dbname
            == (
                "review_prod" if self.environment == "production" else "review_staging"
            ),
            "database_environment_mismatch",
        )
        require(self.database.user == "review_runtime", "runtime_role_required")
        require(
            self.region == "fr-par" and self.zone == "fr-par-1", "paris_region_required"
        )
        require(
            isinstance(self.r2_account_id, str)
            and re.fullmatch(r"[0-9a-f]{32}", self.r2_account_id) is not None
            and self.r2_account_id != "0" * 32,
            "r2_account_required",
        )
        prefix = (
            "review-prod-" if self.environment == "production" else "review-staging-"
        )
        buckets = (
            self.document_bucket,
            self.export_bucket,
            self.journal_bucket,
            self.independent_backup_bucket,
            self.independent_journal_bucket,
        )
        require(
            all(
                isinstance(b, str)
                and b.startswith(prefix)
                and re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", b)
                for b in buckets
            ),
            "isolated_bucket_names_required",
        )
        require(len(set(buckets)) == len(buckets), "distinct_buckets_required")
        require(
            self.scanner_socket == "/run/clamav/clamd.sock", "unix_scanner_required"
        )
        require(
            isinstance(self.google_client_id, str)
            and re.fullmatch(
                r"[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com", self.google_client_id
            )
            is not None,
            "google_client_required",
        )
        require(self.workspace_domain == "spacemusic.io", "workspace_domain_required")
        for name, expected_value in (
            ("inactivity_days", 90),
            ("backup_retention_days", 7),
            ("planning_sek", 1700),
            ("ceiling_sek", 2000),
        ):
            require(
                type(getattr(self, name)) is int
                and getattr(self, name) == expected_value,
                "approved_policy_required",
            )
        return self

    @property
    def r2_endpoint(self):
        self.validate()
        return "https://" + self.r2_account_id + ".eu.r2.cloudflarestorage.com"

    @property
    def tem_endpoint(self):
        return "https://api.scaleway.com/transactional-email/v1alpha1/regions/fr-par"

    @property
    def backup_endpoint(self):
        return "https://s3.fr-par.scw.cloud"

    @property
    def fingerprint(self):
        self.validate()
        return hashlib.sha256(
            json.dumps(
                asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
