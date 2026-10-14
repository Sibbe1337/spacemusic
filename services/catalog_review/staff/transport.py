"""Opt-in Google transport. No discovery, ambient credentials or retryable POSTs."""

import copy
import json
import os
import re
import stat
import threading
import time
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from .config import StaffError, utcnow
from .oidc import JwksSnapshot

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_ENDPOINT = "https://www.googleapis.com/oauth2/v3/certs"
MAX_BODY = 65536
MAX_OPERATION_SECONDS = 12


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


class GoogleOIDCTransport:
    """Synchronous; invoke inside the router's existing thread-pool boundary.

    http_transport is a test seam for httpx.MockTransport, not a client or URL
    override. Production must omit it. Construct once per process and close at
    shutdown. No network or secret reads occur at construction or while disabled.
    """

    def __init__(
        self,
        settings,
        *,
        enabled=False,
        client_secret_path=None,
        http_transport=None,
        clock=utcnow,
    ):
        settings.validate()
        if type(enabled) is not bool:
            raise ValueError("Explicit boolean transport enable flag required")
        if enabled and (
            client_secret_path is None or not Path(client_secret_path).is_absolute()
        ):
            raise ValueError("Independent absolute mounted client-secret path required")
        self.settings, self.enabled, self.clock = settings, enabled, clock
        self._secret_path = client_secret_path
        self._cache = None
        self._cache_deadline = 0
        self._cache_lock = threading.Lock()
        self._client = httpx.Client(
            transport=http_transport,
            trust_env=False,
            follow_redirects=False,
            verify=True,
            timeout=httpx.Timeout(3, connect=3, read=3, write=3, pool=1),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )

    def close(self):
        self._client.close()

    def _available(self):
        if not self.enabled or self._client.is_closed:
            raise StaffError("staff_identity_unavailable", 503)

    def _client_secret(self):
        # Independent regular-file mount, not env/config shared with other apps.
        # O_NONBLOCK prevents a misconfigured FIFO from hanging before fstat.
        fd = os.open(self._secret_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o077
                or not 16 <= info.st_size <= 2049
            ):
                raise ValueError("private regular secret mount required")
            value = os.read(fd, 2050).decode("ascii").removesuffix("\n")
            if not 16 <= len(value) <= 2048 or not all(
                33 <= ord(character) <= 126 for character in value
            ):
                raise ValueError("invalid mounted secret")
            return value
        finally:
            os.close(fd)

    @staticmethod
    def _json(response, deadline):
        if (
            response.headers.get("content-type", "").split(";")[0].strip().lower()
            != "application/json"
            or response.headers.get("content-encoding", "identity").lower()
            != "identity"
        ):
            raise ValueError("unexpected response representation")
        length = response.headers.get("content-length")
        if length is not None and (
            not re.fullmatch(r"[0-9]{1,9}", length) or int(length) > MAX_BODY
        ):
            raise ValueError("response too large")
        body = bytearray()
        for chunk in response.iter_bytes():
            if time.monotonic() >= deadline or len(body) + len(chunk) > MAX_BODY:
                raise ValueError("response budget exceeded")
            body.extend(chunk)
        if time.monotonic() >= deadline:
            raise ValueError("response budget exceeded")
        result = json.loads(body, object_pairs_hook=_unique_object)
        if not isinstance(result, dict):
            raise ValueError("JSON object required")
        return result

    def exchange_code(self, *, code, code_verifier, redirect_uri):
        self._available()
        try:
            if (
                not isinstance(code, str)
                or not 1 <= len(code) <= 4096
                or not isinstance(code_verifier, str)
                or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", code_verifier)
                or redirect_uri != self.settings.redirect_uri
            ):
                raise ValueError("invalid exchange parameters")
            deadline = time.monotonic() + MAX_OPERATION_SECONDS
            # ONE attempt even on timeout/5xx: Google may have consumed the code.
            # Service commits state consumption first, so the caller must relogin.
            with self._client.stream(
                "POST",
                TOKEN_ENDPOINT,
                data={
                    "client_id": self.settings.client_id,
                    "client_secret": self._client_secret(),
                    "code": code,
                    "code_verifier": code_verifier,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            ) as response:
                if response.status_code != 200:
                    raise ValueError("exchange not acknowledged")
                item = self._json(response, deadline)
            token = item.get("id_token")
            if (
                "error" in item
                or not isinstance(token, str)
                or not 1 <= len(token) <= 16384
            ):
                raise ValueError("ID token required")
            # Access/refresh tokens are neither returned nor persisted.
            return token
        except Exception:
            raise StaffError("staff_identity_unavailable", 503) from None

    def _cache_ttl(self, headers, fetched_at, elapsed):
        directives = {}
        for entry in headers.get("cache-control", "").split(","):
            key, separator, value = entry.strip().lower().partition("=")
            if not key:
                continue
            if key in directives:
                raise ValueError("ambiguous cache lifetime")
            directives[key] = value.strip('"') if separator else None
        if {"no-store", "no-cache"} & directives.keys():
            raise ValueError("uncacheable signing keys")
        max_age = directives.get("max-age", "300")
        age = headers.get("age", "0")
        if (
            not isinstance(max_age, str)
            or not re.fullmatch(r"[0-9]{1,10}", max_age)
            or not re.fullmatch(r"[0-9]{1,10}", age)
        ):
            raise ValueError("invalid cache lifetime")
        apparent_age = 0
        if headers.get("date"):
            apparent_age = max(
                0, (fetched_at - parsedate_to_datetime(headers["date"])).total_seconds()
            )
        ttl = min(86400, int(max_age) - max(int(age), apparent_age) - elapsed)
        if ttl <= 0:
            raise ValueError("expired signing keys")
        return ttl

    def jwks_snapshot(self):
        self._available()
        if not self._cache_lock.acquire(timeout=1):
            raise StaffError("staff_identity_unavailable", 503)
        try:
            now = self.clock()
            if (
                self._cache
                and self._cache.fetched_at <= now < self._cache.expires_at
                and time.monotonic() < self._cache_deadline
            ):
                return copy.deepcopy(self._cache)
            self._cache = None
            deadline = time.monotonic() + MAX_OPERATION_SECONDS
            for attempt in range(2):
                try:
                    if time.monotonic() >= deadline:
                        raise ValueError("signing key request budget exceeded")
                    started = time.monotonic()
                    with self._client.stream("GET", JWKS_ENDPOINT) as response:
                        if (
                            response.status_code in (429, 500, 502, 503, 504)
                            and attempt == 0
                        ):
                            continue
                        if response.status_code != 200:
                            raise ValueError("signing keys unavailable")
                        item = self._json(response, deadline)
                        fetched_at = self.clock()
                        ttl = self._cache_ttl(
                            response.headers, fetched_at, time.monotonic() - started
                        )
                    keys = item.get("keys")
                    if (
                        not isinstance(keys, list)
                        or not 1 <= len(keys) <= 10
                        or any(not isinstance(key, dict) for key in keys)
                    ):
                        raise ValueError("invalid signing key set")
                    self._cache = JwksSnapshot(
                        tuple(keys), fetched_at, fetched_at + timedelta(seconds=ttl)
                    )
                    self._cache_deadline = time.monotonic() + ttl
                    return copy.deepcopy(self._cache)
                except httpx.TransportError:
                    if attempt != 0 or time.monotonic() >= deadline:
                        raise
            raise ValueError("signing keys unavailable")
        except Exception:
            raise StaffError("staff_identity_unavailable", 503) from None
        finally:
            self._cache_lock.release()
