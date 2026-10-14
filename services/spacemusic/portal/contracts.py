from __future__ import annotations

from datetime import date
from decimal import Decimal
import hashlib
import hmac
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EmailInput(Input):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a complete email address")
        # Do not apply Gmail-specific alias rules to other providers.
        return value.lower()


class LinkInput(Input):
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class CatalogInput(Input):
    artistLink: str = Field(default="", max_length=500)
    distributor: Literal["DistroKid", "TuneCore", "Other", "Not sure"]
    tracks: int = Field(ge=1, le=1_000_000)
    rights: Literal["masters", "unsure"]
    owned: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    offered: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    cutoff: str = Field(default="", max_length=10)
    revenue: Decimal = Field(ge=0, le=1_000_000_000, max_digits=12, decimal_places=2)
    currency: Literal["USD", "EUR", "GBP", "SEK", "Other"]
    periodStart: str = Field(pattern=r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])$")
    periodEnd: str = Field(pattern=r"^[1-9][0-9]{3}-(0[1-9]|1[0-2])$")
    basis: Literal["own-share", "catalog-total", "unsure"]
    agreements: Literal["none-known", "shared", "unknown"]

    @model_validator(mode="after")
    def boundaries(self):
        if self.artistLink and (
            urlsplit(self.artistLink).scheme not in ("http", "https")
            or not urlsplit(self.artistLink).netloc
        ):
            raise ValueError("Use a full http or https music link")
        if self.cutoff and date.fromisoformat(self.cutoff).isoformat() != self.cutoff:
            raise ValueError("Invalid cutoff date")
        if self.periodStart > self.periodEnd:
            raise ValueError("Last statement month must not precede the first")
        return self


class CatalogSave(Input):
    revision: int = Field(ge=0)
    catalog: CatalogInput


class RevisionInput(Input):
    revision: int = Field(ge=0)


class ReplyInput(RevisionInput):
    message: str = Field(min_length=1, max_length=1500)


def verified_signature(secret: bytes, header: str, raw: bytes, now: int) -> bool:
    """Formspree signs timestamp + '.' + the original request bytes."""
    if not secret or len(header) > 300:
        return False
    try:
        parts = header.split(",")
        fields = dict(part.strip().split("=", 1) for part in parts)
        if len(parts) != 2 or set(fields) != {"t", "v1"}:
            return False
        if not re.fullmatch(r"[0-9]{1,12}", fields["t"]) or not re.fullmatch(
            r"[a-fA-F0-9]{64}", fields["v1"]
        ):
            return False
        if abs(now - int(fields["t"])) > 300:
            return False
        expected = hmac.new(
            secret, fields["t"].encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, fields["v1"].lower())
    except (TypeError, ValueError, KeyError):
        return False


FIXTURES = {
    "royalties": (
        "DEMO-royalties.csv",
        b"period,currency,own_share_royalties\n2026-08,USD,400\n",
    ),
    "tracks": (
        "DEMO-tracks.csv",
        b"title,isrc,owned_percent\nFictional Night,TEST00000001,100\n",
    ),
}


def file_metadata(name: str, body: bytes, kind: str):
    if (
        not name
        or len(name) > 180
        or any(c in name for c in "/\\\r\n\x00")
        or any(ord(c) < 32 for c in name)
    ):
        raise ValueError("Use a plain filename without paths or control characters")
    extension = name.rsplit(".", 1)[-1].lower()
    if extension not in {"csv", "tsv", "pdf", "xlsx"}:
        raise ValueError("Use CSV, TSV, PDF or XLSX")
    if not 0 < len(body) <= 25 * 1024 * 1024:
        raise ValueError("Files must be non-empty and no larger than 25 MB")
    # This local-only build deliberately does not claim to run antivirus.
    # Only exact bundled fixtures can leave quarantine for integration tests.
    scan = "TEST_FIXTURE" if (name, body) == FIXTURES[kind] else "QUARANTINED"
    return {
        "name": name,
        "size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "scan": scan,
    }
