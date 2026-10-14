"""Bounded human-review contracts. Model output never constitutes approval."""

from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field, StrictInt, field_validator, model_validator

from .contracts import Contract

CHECKS = ("scope", "authority", "ownership", "income", "agreements", "catalog")
CheckKey = Literal["scope", "authority", "ownership", "income", "agreements", "catalog"]
Right = Literal["masters", "publishing", "both"]
Structure = Literal["full_sale", "partial_sale", "term_license"]


def clean_text(value):
    value = value.strip()
    if not value or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("Meaningful text without control characters required")
    return value


class EvidenceCheck(Contract):
    key: CheckKey
    status: Literal["missing", "seller_reported", "reviewed", "conflicting"]
    sources: list[str] = Field(default_factory=list, max_length=12)
    note: str = Field(min_length=1, max_length=600)

    _note = field_validator("note")(clean_text)

    @model_validator(mode="after")
    def evidence_required(self):
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("Duplicate evidence reference")
        if self.status != "missing" and not self.sources:
            raise ValueError("A source reference is required")
        if any(len(s) > 100 for s in self.sources):
            raise ValueError("Invalid evidence reference")
        return self


class BuyerMandate(Contract):
    buyer_id: UUID
    name: str = Field(min_length=1, max_length=120)
    mandate_reference: str = Field(min_length=1, max_length=180)
    checked_on: date
    expires_on: date
    rights: list[Right] = Field(min_length=1, max_length=3)
    structures: list[Structure] = Field(min_length=1, max_length=3)
    minimum_annual_net: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False
    )
    currency: Optional[Literal["EUR", "USD", "GBP", "SEK"]] = None

    _name = field_validator("name", "mandate_reference")(clean_text)

    @model_validator(mode="after")
    def consistent(self):
        if (self.minimum_annual_net is None) != (self.currency is None):
            raise ValueError("A revenue requirement needs its currency")
        if not 0 < (self.expires_on - self.checked_on).days <= 90:
            raise ValueError("Mandates must be reconfirmed within 90 days")
        if len(set(self.rights)) != len(self.rights) or len(
            set(self.structures)
        ) != len(self.structures):
            raise ValueError("Duplicate criteria")
        return self


class ReviewRecord(Contract):
    request_id: UUID
    revision: StrictInt = Field(ge=0)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights: Literal["masters", "publishing", "both", "unknown"] = "unknown"
    structure: Literal["full_sale", "partial_sale", "term_license", "unknown"] = (
        "unknown"
    )
    checks: list[EvidenceCheck] = Field(min_length=6, max_length=6)
    buyers: list[BuyerMandate] = Field(default_factory=list, max_length=10)
    annual_net: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False
    )
    currency: Optional[Literal["EUR", "USD", "GBP", "SEK"]] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    seller_goal: str = Field(min_length=1, max_length=800)
    exclusions: str = Field(min_length=1, max_length=800)

    _text = field_validator("seller_goal", "exclusions")(clean_text)

    @model_validator(mode="after")
    def complete(self):
        if {c.key for c in self.checks} != set(CHECKS):
            raise ValueError("All six checks are required exactly once")
        if len({b.buyer_id for b in self.buyers}) != len(self.buyers):
            raise ValueError("Duplicate buyer")
        fields = (self.annual_net, self.currency, self.period_start, self.period_end)
        if any(v is not None for v in fields):
            if any(v is None for v in fields):
                raise ValueError("Revenue needs currency and a complete period")
            if (self.period_end - self.period_start).days + 1 not in (365, 366):
                raise ValueError(
                    "Only a documented twelve-month net period is supported"
                )
        checked = {c.key: c.status for c in self.checks}
        if checked["income"] == "reviewed" and self.annual_net is None:
            raise ValueError("Review the net revenue, currency and period first")
        if checked["scope"] == "reviewed" and (
            self.rights == "unknown" or self.structure == "unknown"
        ):
            raise ValueError("Review the scope first")
        return self


class PackageRequest(Contract):
    request_id: UUID
    revision: StrictInt = Field(gt=0)
    buyer_id: UUID
    document_ids: list[UUID] = Field(default_factory=list, max_length=40)

    @field_validator("document_ids")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Duplicate document")
        return value


class ShareDecision(Contract):
    request_id: UUID
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approved", "declined", "revoked"]
