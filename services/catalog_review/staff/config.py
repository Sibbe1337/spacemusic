import base64
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

GOOGLE_ISSUER = "https://accounts.google.com"


class StaffError(Exception):
    """Safe public error code; never include claims, credentials, or provider errors."""

    def __init__(self, code="staff_authentication_required", status=401):
        super().__init__(code)
        self.code, self.status = code, status


def utcnow():
    return datetime.now(timezone.utc)


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unb64(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise StaffError("invalid_staff_proof")
    try:
        result = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if b64(result) != value:
            raise ValueError()
        return result
    except (ValueError, TypeError):
        raise StaffError("invalid_staff_proof") from None


@dataclass(frozen=True)
class StaffSettings:
    client_id: str = ""
    origin: str = ""
    rp_id: str = ""
    generation: str = ""
    digest_key: bytes = field(default=b"", repr=False)

    def validate(self):
        allowed = {
            "review.test",
            "review.spacemusic.io",
            "review-staging.spacemusic.io",
        }
        if self.rp_id not in allowed or self.origin != "https://" + self.rp_id:
            raise ValueError("An exact isolated HTTPS origin and RP ID are required")
        if not self.client_id or len(self.client_id) > 255 or len(self.digest_key) < 32:
            raise ValueError(
                "Explicit client ID and independent random digest key required"
            )
        if str(UUID(self.generation)) != self.generation:
            raise ValueError("Explicit canonical non-restored generation UUID required")

    @property
    def redirect_uri(self):
        return self.origin + "/api/staff/oidc/callback"

    def digest(self, purpose, value):
        if not isinstance(value, str) or not 32 <= len(value) <= 256:
            raise StaffError()
        return hmac.new(
            self.digest_key, (purpose + ":" + value).encode(), hashlib.sha256
        ).hexdigest()
