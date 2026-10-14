"""Explicit integration limits; no provider credentials are read from the environment."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import urlsplit

SCOPES = ("read:profile", "read:releases", "read:sales")
CALLBACK_PATH = "/api/integrations/toolost/callback"
MANIFEST = "toolost-read-v1-unverified-semantics"
ENVIRONMENTS = {
    "sandbox": (
        "https://review-staging.spacemusic.io",
        "https://sandbox.toolost.com/oauth",
        "https://api-sandbox.toolost.com/v1",
    ),
    "production": (
        "https://review.spacemusic.io",
        "https://toolost.com/oauth",
        "https://api.toolost.com/v1",
    ),
}


class ProviderError(Exception):
    """Only bounded application codes, never provider bodies or credentials."""

    def __init__(self, code, *, retry_after=None):
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class Config:
    environment: str = "sandbox"
    enabled: bool = False
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    developer_pool: str = "toolost"
    max_response_bytes: int = 10 * 1024 * 1024
    max_pages: int = 100
    max_calls: int = 500
    max_records: int = 10000
    max_releases: int = 100
    job_seconds: int = 1800
    lease_seconds: int = 120
    monthly_calls: int = 5000
    minute_calls: int = 30

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("invalid_provider_feature_flag")
        if self.environment not in ENVIRONMENTS:
            raise ValueError("invalid_provider_environment")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", self.developer_pool):
            raise ValueError("invalid_developer_pool")
        bounds = {
            "max_response_bytes": 10 * 1024 * 1024,
            "max_pages": 100,
            "max_calls": 500,
            "max_records": 10000,
            "max_releases": 100,
            "job_seconds": 1800,
            "lease_seconds": 120,
            "monthly_calls": 5000,
            "minute_calls": 60,
        }
        for name, upper in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError("invalid_provider_limit")

    @property
    def origin(self):
        return ENVIRONMENTS[self.environment][0]

    @property
    def callback(self):
        return self.origin + CALLBACK_PATH

    @property
    def oauth_base(self):
        return ENVIRONMENTS[self.environment][1]

    @property
    def api_base(self):
        return ENVIRONMENTS[self.environment][2]

    def require_enabled(self):
        if not self.enabled:
            raise ProviderError("provider_disabled")
        if (
            not isinstance(self.client_id, str)
            or not isinstance(self.client_secret, str)
            or not 1 <= len(self.client_id) <= 1024
            or not 1 <= len(self.client_secret) <= 4096
        ):
            raise ProviderError("provider_configuration_missing")

    def validate_callback(self, url):
        # Query parsing belongs to the isolated HTTP route, never a marketing bridge.
        if url != self.callback or urlsplit(url).query:
            raise ProviderError("callback_mismatch")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def provider_id(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,63}", value):
        raise ProviderError("provider_schema_invalid")
    return value


def short_text(value, maximum=240, *, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise ProviderError("provider_schema_invalid")
    if any(ord(char) < 32 for char in value):
        raise ProviderError("provider_schema_invalid")
    return value


def decimal_string(value):
    if type(value) is int:
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ProviderError("provider_schema_invalid")
    parts = value.as_tuple()
    if len(parts.digits) > 78 or not -30 <= parts.exponent <= 30:
        raise ProviderError("provider_number_out_of_bounds")
    return format(value, "f")


def coverage():
    return {
        "conclusions_allowed": False,
        "currency": None,
        "period_kind": "unknown",
        "gross_net_basis": None,
        "provider_completeness_verified": False,
        "reasons": [
            "currency_unverified",
            "period_semantics_unverified",
            "amount_basis_unverified",
            "catalog_sales_mapping_unverified",
        ],
    }
