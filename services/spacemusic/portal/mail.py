"""Opt-in owner-only email test. Not a production delivery worker."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import getpass
import html
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit
from uuid import UUID

REPO = Path(__file__).resolve().parents[3]
RECIPIENT = "hello@spacemusic.io"
IDENTITY = "alex@example.com"
SUBJECT = "[TEST] Your SPACE portal sign-in link"
DEFAULT_KEY_FILE = (
    Path.home()
    / "Library/Application Support/SpaceMusic/seller-portal-local/resend-test-key"
)


class MailUnavailable(Exception):
    """Only safe, static descriptions may leave the delivery boundary."""


def validate_key(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"re_[A-Za-z0-9_-]{20,200}", value
    ):
        raise RuntimeError("Invalid Resend credential format")
    return value


def validate_key_path(path):
    if path.resolve().is_relative_to(REPO) or path.is_symlink():
        raise RuntimeError(
            "The credential must be outside the repository, without a symlink"
        )


def read_key(path):
    validate_key_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 256
        ):
            raise RuntimeError(
                "The credential must be an owner-only regular file (0600)"
            )
        try:
            return validate_key(stream.read(256).decode("ascii").strip())
        except UnicodeError:
            raise RuntimeError("Invalid Resend credential format") from None


def write_key(path, value):
    validate_key_path(path)
    value = validate_key(value)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(path.parent.stat().st_mode) & 0o077:
        raise RuntimeError("The credential directory must be owner-only (0700)")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)


def message(origin, token):
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in ("127.0.0.1", "localhost")
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    ):
        raise ValueError("Only loopback test links are allowed")
    url = origin + "/#sign-in=" + token
    safe_url = html.escape(url, quote=True)
    text = (
        "SPACE / LOCAL EMAIL TEST\n\n"
        "Continue the fictional Night Window catalog review as alex@example.com.\n\n"
        + url
        + "\n\nThis single-use link expires 15 minutes after the first send attempt. "
        "Open it on the same computer running the local portal, not on your phone. "
        "Confirm sign-in on the page; opening the link alone does not sign you in.\n\n"
        "This is an owner-requested integration test, not a customer application, "
        "valuation or offer. Do not enter customer data or forward this link.\n"
        "Replies go to hello@spacemusic.io."
    )
    markup = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SPACE local email test</title></head>
<body style="margin:0;padding:24px;background:#f6f5f1;color:#18202a;font-family:Helvetica,Arial,sans-serif">
<main style="max-width:540px;margin:auto;padding:32px;background:#ffffff;border:1px solid #d9dce1">
<p style="font-size:13px;letter-spacing:2px">SPACE / LOCAL EMAIL TEST</p>
<h1 style="font-size:30px;line-height:1.2;margin:28px 0 18px">Your catalog review.<br>Ready to continue.</h1>
<p style="font-size:16px;line-height:1.6">Sign in to the fictional Night Window review as <strong>alex@example.com</strong>.</p>
<p style="margin:28px 0"><a href="{safe_url}" style="display:inline-block;padding:16px 24px;background:#164bb8;color:#ffffff;text-decoration:none;font-weight:bold">Open local test portal</a></p>
<p style="font-size:14px;line-height:1.6">The link expires 15 minutes after the first send attempt and works once. Open it on the same computer running the local portal, not on your phone. Confirm sign-in on the page.</p>
<p style="font-size:13px;line-height:1.6;border-top:1px solid #d9dce1;padding-top:20px">Owner-requested integration test only. This is not a customer application, valuation or offer. Do not enter customer data or forward this link. Replies go to hello@spacemusic.io.</p>
</main></body></html>"""
    return {
        "from": "SPACE <hello@spacemusic.io>",
        "to": [RECIPIENT],
        "reply_to": RECIPIENT,
        "subject": SUBJECT,
        "text": text,
        "html": markup,
        "headers": {
            "X-Auto-Response-Suppress": "All",
            "Auto-Submitted": "auto-generated",
        },
        "tags": [{"name": "purpose", "value": "portal_owner_test"}],
    }


@dataclass
class ResendTestSender:
    key: str = field(repr=False)
    transport: object = field(default=None, repr=False)

    def __post_init__(self):
        validate_key(self.key)

    async def send(self, request_id, origin, token):
        try:
            import httpx
        except ImportError:
            raise MailUnavailable(
                "Owner email testing requires the optional httpx dependency"
            ) from None
        request_id = str(UUID(str(request_id)))
        body = message(origin, token)
        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=httpx.Timeout(10, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "POST",
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": "Bearer " + self.key,
                        "Idempotency-Key": "space-portal-local-v1/" + request_id,
                    },
                    json=body,
                ) as response:
                    if response.status_code not in (200, 201):
                        raise MailUnavailable(
                            f"Resend did not confirm acceptance (HTTP {response.status_code}). "
                            "Retry uses the same request; no delivery is claimed."
                        )
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 65536:
                            raise MailUnavailable(
                                "Resend returned an unexpected response"
                            )
                    import json

                    data = json.loads(content)
                    if not isinstance(data, dict) or not isinstance(
                        data.get("id"), str
                    ):
                        raise MailUnavailable("Resend returned an unexpected response")
                    return str(UUID(data["id"]))
        except MailUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise MailUnavailable(
                "Resend acceptance could not be confirmed. Retry the same request."
            ) from None


def main():
    parser = argparse.ArgumentParser(
        description="Store an owner-only local Resend test credential"
    )
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    args = parser.parse_args()
    try:
        validate_key_path(args.key_file)
        if args.key_file.exists():
            raise RuntimeError("Credential already exists; refusing to overwrite it")
        value = getpass.getpass("Resend test credential (hidden): ")
        write_key(args.key_file, value)
    except (OSError, RuntimeError, EOFError):
        parser.exit(
            1,
            "Credential was not saved. Check the private path, permissions and key format.\n",
        )
    print("Credential saved outside the repository with owner-only permissions.")


if __name__ == "__main__":
    main()
