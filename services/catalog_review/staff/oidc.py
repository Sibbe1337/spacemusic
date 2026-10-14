import hmac
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from .config import GOOGLE_ISSUER, StaffError, utcnow


@dataclass(frozen=True)
class JwksSnapshot:
    keys: tuple = field(repr=False)
    fetched_at: datetime
    expires_at: datetime


class GoogleOIDCVerifier:
    """Offline verification with an explicitly injected, trusted Google JWKS cache.

    No token-selected key URL, discovery, network, or development verification path.
    The separately reviewed transport must fetch only Google's pinned JWKS endpoint.
    """

    def __init__(
        self, client_id, key_provider: Optional[Callable] = None, clock=utcnow
    ):
        if not client_id:
            raise ValueError("Explicit Google client ID required")
        self.client_id, self.key_provider, self.clock = client_id, key_provider, clock

    def verify(self, token, *, nonce, started_at):
        if self.key_provider is None:
            raise StaffError("staff_identity_unavailable", 503)
        try:
            if not isinstance(token, str) or len(token) > 16384:
                raise ValueError()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or any(
                k in header for k in ("jku", "jwk", "x5u", "crit")
            ):
                raise ValueError()
            kid = header.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 200:
                raise ValueError()
            snapshot = self.key_provider()
            # A cold cache can perform bounded network I/O. Evaluate freshness
            # after it returns, not before its fetched_at timestamp existed.
            now = self.clock()
            if (
                not isinstance(snapshot, JwksSnapshot)
                or not (
                    snapshot.fetched_at
                    <= now
                    < snapshot.expires_at
                    <= snapshot.fetched_at + timedelta(hours=24)
                )
                or not 1 <= len(snapshot.keys) <= 10
            ):
                raise ValueError()
            matches = [k for k in snapshot.keys if k.get("kid") == kid]
            if len(matches) != 1:
                raise ValueError()
            key = matches[0]
            if (
                key.get("kty") != "RSA"
                or key.get("alg", "RS256") != "RS256"
                or key.get("use", "sig") != "sig"
                or "d" in key
            ):
                raise ValueError()
            public_key = jwt.PyJWK.from_dict(key, algorithm="RS256").key
            if not isinstance(public_key, RSAPublicKey) or public_key.key_size < 2048:
                raise ValueError()
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=[GOOGLE_ISSUER, "accounts.google.com"],
                options={
                    "require": [
                        "iss",
                        "sub",
                        "aud",
                        "exp",
                        "iat",
                        "nonce",
                        "email",
                        "email_verified",
                        "hd",
                    ],
                    "strict_aud": True,
                    # Use one injected server clock, with strict NumericDate types.
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
            if not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 255:
                raise ValueError()
            if not isinstance(claims["nonce"], str) or not hmac.compare_digest(
                claims["nonce"], nonce
            ):
                raise ValueError()
            if "azp" in claims and claims["azp"] != self.client_id:
                raise ValueError()
            if claims["email_verified"] is not True or claims["hd"] != "spacemusic.io":
                raise ValueError()
            if (
                not isinstance(claims["email"], str)
                or not 3 <= len(claims["email"]) <= 254
                or claims["email"].count("@") != 1
            ):
                raise ValueError()
            if any(type(claims[k]) is not int for k in ("iat", "exp")):
                raise ValueError()
            timestamp = now.timestamp()
            if not (started_at.timestamp() - 30 <= claims["iat"] <= timestamp + 30):
                raise ValueError()
            if not (timestamp < claims["exp"] <= claims["iat"] + 3600):
                raise ValueError()
            if "nbf" in claims and (
                type(claims["nbf"]) is not int or claims["nbf"] > timestamp
            ):
                raise ValueError()
            # Google's documented legacy issuer is canonicalized only AFTER
            # signature/issuer validation. Verified workspace is an admission
            # requirement, never a principal lookup or an MFA/role grant.
            return {
                "issuer": GOOGLE_ISSUER,
                "subject": claims["sub"],
                "expires": claims["exp"],
            }
        except Exception:
            raise StaffError("invalid_google_identity") from None
