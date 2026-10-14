"""Versioned AES-256-GCM for intake envelopes; keys live outside database backups."""

import base64
import json
import re
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EnvelopeUnavailable(RuntimeError):
    pass


class EnvelopeCipher:
    def __init__(self, keys, active_key):
        if (
            not keys
            or active_key not in keys
            or any(
                not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", key)
                or type(value) is not bytes
                or len(value) != 32
                for key, value in keys.items()
            )
        ):
            raise ValueError("External versioned 256-bit keys required")
        self._keys, self.active_key = dict(keys), active_key

    @staticmethod
    def _aad(key, aad):
        if type(aad) is not bytes or not 1 <= len(aad) <= 512:
            raise ValueError("Explicit record binding required")
        return b"space-intake-envelope-v1:" + key.encode() + b":" + aad

    def seal(self, plaintext, *, aad):
        if type(plaintext) is not bytes or not 1 <= len(plaintext) <= 8192:
            raise ValueError("Bounded intake payload required")
        key, nonce = self.active_key, secrets.token_bytes(12)
        value = AESGCM(self._keys[key]).encrypt(nonce, plaintext, self._aad(key, aad))
        return json.dumps(
            {"v": 1, "key": key, "payload": base64.b64encode(nonce + value).decode()},
            separators=(",", ":"),
        ).encode()

    def open(self, envelope, *, aad):
        try:
            if type(envelope) is not bytes or not 1 <= len(envelope) <= 16384:
                raise ValueError()

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError()
                    result[key] = value
                return result

            item = json.loads(envelope, object_pairs_hook=unique)
            if (
                set(item) != {"v", "key", "payload"}
                or type(item["v"]) is not int
                or item["v"] != 1
            ):
                raise ValueError()
            raw = base64.b64decode(item["payload"], validate=True)
            if not 29 <= len(raw) <= 8220:
                raise ValueError()
            return AESGCM(self._keys[item["key"]]).decrypt(
                raw[:12], raw[12:], self._aad(item["key"], aad)
            )
        except Exception:
            raise EnvelopeUnavailable("Intake envelope unavailable") from None

    def rewrap(self, envelope, *, aad):
        return self.seal(self.open(envelope, aad=aad), aad=aad)
