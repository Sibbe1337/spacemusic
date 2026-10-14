import hashlib
import hmac
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from uuid import UUID


class ReviewError(Exception):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class Settings:
    origin: str
    signing_key: bytes = field(repr=False)
    digest_key: bytes = field(repr=False)
    mode: str = "test"
    source_identity_key: bytes = field(default=None, repr=False)
    generation: str = "test"

    def validate(self):
        parsed = urlsplit(self.origin)
        expected = {
            "test": "https://review.test",
            "production": "https://review.spacemusic.io",
            "staging": "https://review-staging.spacemusic.io",
        }
        if (
            self.mode not in expected
            or self.origin != expected[self.mode]
            or parsed.port
        ):
            raise RuntimeError("Exact environment-specific portal origin required")
        if self.mode != "test":
            if self.source_identity_key is None:
                raise RuntimeError("Stable source identity key required")
            try:
                if str(UUID(self.generation)) != self.generation:
                    raise ValueError()
            except (TypeError, ValueError, AttributeError):
                raise RuntimeError("Non-restored generation required") from None
        if (
            type(self.signing_key) is not bytes
            or type(self.digest_key) is not bytes
            or min(len(self.signing_key), len(self.digest_key)) < 32
            or self.signing_key == self.digest_key
        ):
            raise RuntimeError(
                "Independent random signing and digest keys are required"
            )
        if self.source_identity_key is not None and (
            type(self.source_identity_key) is not bytes
            or len(self.source_identity_key) < 32
            or self.source_identity_key in (self.signing_key, self.digest_key)
        ):
            raise RuntimeError("Source identity requires a separate stable key")


def digest(key, kind, value):
    return hmac.new(key, (kind + ":" + value).encode(), hashlib.sha256).hexdigest()


def workspace_from_token(token):
    try:
        if not isinstance(token, str) or not 70 <= len(token) <= 160:
            raise ValueError()
        return str(UUID(token.split(".")[0]))
    except (ValueError, AttributeError):
        raise ReviewError("authentication_required", 401) from None
