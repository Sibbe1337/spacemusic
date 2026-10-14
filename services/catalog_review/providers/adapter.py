"""Read-only resource client with an injected OFFLINE transport, never requests/httpx."""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from .contracts import SCOPES, ProviderError, provider_id, short_text


@dataclass(frozen=True)
class Request:
    method: str
    url: str
    headers: dict = field(default_factory=dict, repr=False)
    query: dict = field(default_factory=dict)
    form: dict = field(default_factory=dict, repr=False)
    connect_timeout: int = 5
    total_timeout: int = 30
    max_bytes: int = 10 * 1024 * 1024


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict
    chunks: object = field(repr=False)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def retry_delay(headers, now):
    value = headers.get("retry-after", "")
    try:
        delay = (
            int(value)
            if value.isdecimal()
            else (
                parsedate_to_datetime(value).astimezone(timezone.utc) - now
            ).total_seconds()
        )
        return max(1, min(86400, int(delay)))
    except (ValueError, TypeError, OverflowError):
        return 60


class ReadOnlyAdapter:
    def __init__(self, config, transport, *, monotonic=time.monotonic):
        # Real transport implementation/activation requires a separate reviewed change.
        if getattr(transport, "offline", False) is not True:
            raise ProviderError("live_transport_not_implemented")
        self.config, self._transport, self._monotonic = config, transport, monotonic

    def authorization_url(self, state, challenge):
        self.config.require_enabled()
        return (
            self.config.oauth_base
            + "/authorize?"
            + urlencode(
                {
                    "client_id": self.config.client_id,
                    "response_type": "code",
                    "redirect_uri": self.config.callback,
                    "scope": " ".join(SCOPES),
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )

    def _send(self, request, *, before_send, observe, now):
        self.config.require_enabled()
        before_send()
        started = self._monotonic()
        try:
            response = self._transport.send(request)
            headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            data = bytearray()
            for chunk in response.chunks:
                if self._monotonic() - started > request.total_timeout:
                    raise ProviderError("provider_timeout", retry_after=5)
                if not isinstance(chunk, bytes):
                    raise ProviderError("provider_schema_invalid")
                if len(data) + len(chunk) > request.max_bytes:
                    raise ProviderError("provider_response_too_large")
                data.extend(chunk)
            if self._monotonic() - started > request.total_timeout:
                raise ProviderError("provider_timeout", retry_after=5)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("provider_unavailable", retry_after=5) from None
        observe(headers)
        if response.status == 401:
            raise ProviderError("provider_unauthorized")
        if response.status == 403:
            raise ProviderError("provider_scope_denied")
        if response.status == 404:
            raise ProviderError("provider_resource_missing")
        if 500 <= response.status < 600:
            raise ProviderError("provider_unavailable", retry_after=5)
        if headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise ProviderError("provider_schema_invalid")
        try:
            value = json.loads(
                data,
                parse_float=Decimal,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
                object_pairs_hook=_pairs,
            )
            if not isinstance(value, dict):
                raise ValueError()
        except (ValueError, UnicodeError, RecursionError):
            raise ProviderError("provider_schema_invalid") from None
        if response.status == 429:
            if value.get("error") == "quota_exceeded":
                raise ProviderError("provider_quota_exceeded")
            raise ProviderError(
                "provider_rate_limited", retry_after=retry_delay(headers, now)
            )
        if value.get("error") == "invalid_grant":
            raise ProviderError("reauth_required")
        if response.status != 200:
            raise ProviderError("provider_request_rejected")
        return value

    def tokens(self, *, code=None, verifier=None, refresh_token=None, **hooks):
        if refresh_token is None:
            form = {
                "grant_type": "authorization_code",
                "code": short_text(code, 4096),
                "code_verifier": short_text(verifier, 128),
                "redirect_uri": self.config.callback,
            }
        else:
            form = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        form.update(
            client_id=self.config.client_id, client_secret=self.config.client_secret
        )
        result = self._send(
            Request(
                "POST",
                self.config.oauth_base + "/token",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                form=form,
                max_bytes=min(self.config.max_response_bytes, 65536),
            ),
            **hooks,
        )
        if (
            not isinstance(result.get("token_type"), str)
            or result["token_type"].lower() != "bearer"
            or type(result.get("expires_in")) is not int
            or not 1 <= result["expires_in"] <= 31 * 86400
        ):
            raise ProviderError("provider_token_invalid")
        if not isinstance(result.get("scope"), str) or set(
            result["scope"].split()
        ) != set(SCOPES):
            raise ProviderError("provider_scopes_unverified")
        return {
            "access_token": short_text(result.get("access_token"), 8192),
            "refresh_token": short_text(result.get("refresh_token"), 8192),
            "expires_in": result["expires_in"],
            "scopes": list(SCOPES),
        }

    def get(self, resource, access_token, *, page=1, **hooks):
        query = {}
        if resource in ("releases", "sales/overview", "sales/releases"):
            if type(page) is not int or not 1 <= page <= self.config.max_pages:
                raise ProviderError("import_page_limit")
            query = {
                "page": page,
                "perPage" if resource == "releases" else "per_page": 100,
            }
        elif resource != "me":
            match = re.fullmatch(
                r"(?:releases/([1-9][0-9]{0,63})(?:/tracks)?|sales/releases/([1-9][0-9]{0,63})/overview)",
                resource,
            )
            if not match:
                raise ProviderError("provider_resource_forbidden")
            provider_id(next(part for part in match.groups() if part is not None))
            if page != 1:
                raise ProviderError("provider_resource_forbidden")
        return self._send(
            Request(
                "GET",
                self.config.api_base + "/" + resource,
                headers={
                    "Authorization": "Bearer " + short_text(access_token, 8192),
                    "Accept": "application/json",
                },
                query=query,
                max_bytes=self.config.max_response_bytes,
            ),
            **hooks,
        )
