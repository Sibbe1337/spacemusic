"""AES-256-GCM with external, versioned keys and explicit contextual binding."""

import base64
import hashlib
import json
import re
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .contracts import ProviderError, canonical


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unb64(value):
    return base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )


def pkce():
    verifier = secrets.token_urlsafe(48)
    return verifier, b64(hashlib.sha256(verifier.encode("ascii")).digest())


def state_digest(state):
    if not isinstance(state, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", state):
        raise ProviderError("oauth_state_invalid")
    return hashlib.sha256(state.encode("ascii")).hexdigest()


class TokenVault:
    def __init__(self, keys, active_key):
        if active_key not in keys or not keys:
            raise ValueError("active_encryption_key_missing")
        if any(
            not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key)
            or not isinstance(value, bytes)
            or len(value) != 32
            for key, value in keys.items()
        ):
            raise ValueError("invalid_encryption_key")
        self._keys = dict(keys)
        self.active_key = active_key

    def seal(self, value, binding):
        nonce = secrets.token_bytes(12)
        kid = self.active_key
        aad = canonical(["space-toolost", 1, kid, binding]).encode()
        ciphertext = AESGCM(self._keys[kid]).encrypt(
            nonce, canonical(value).encode(), aad
        )
        return {"v": 1, "kid": kid, "nonce": b64(nonce), "ciphertext": b64(ciphertext)}

    def open(self, envelope, binding):
        try:
            if set(envelope) != {"v", "kid", "nonce", "ciphertext"}:
                raise ValueError()
            if envelope["v"] != 1:
                raise ValueError()
            kid = envelope["kid"]
            nonce = unb64(envelope["nonce"])
            ciphertext = unb64(envelope["ciphertext"])
            aad = canonical(["space-toolost", 1, kid, binding]).encode()
            if len(nonce) != 12:
                raise ValueError()
            return json.loads(AESGCM(self._keys[kid]).decrypt(nonce, ciphertext, aad))
        except Exception:
            raise ProviderError("credential_unavailable") from None

    def rewrap(self, envelope, binding):
        return self.seal(self.open(envelope, binding), binding)
