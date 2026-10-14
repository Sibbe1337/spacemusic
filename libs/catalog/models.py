from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApplicationStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    DATA_REQUIRED = "DATA_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    OFFER_READY = "OFFER_READY"
    ACCEPTED = "ACCEPTED"
    PAID = "PAID"
    REJECTED = "REJECTED"


class DocumentType(str, Enum):
    ROYALTY_STATEMENT = "ROYALTY_STATEMENT"
    RIGHTS_AGREEMENT = "RIGHTS_AGREEMENT"
    DISTRIBUTOR_EXPORT = "DISTRIBUTOR_EXPORT"
    PUBLISHER_STATEMENT = "PUBLISHER_STATEMENT"
    IDENTITY = "IDENTITY"
    TAX = "TAX"
    OTHER = "OTHER"


class DocumentStatus(str, Enum):
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ReportStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RoyaltySource(str, Enum):
    DISTRIBUTOR = "DISTRIBUTOR"
    PUBLISHER = "PUBLISHER"
    PRO = "PRO"
    DIRECT_LICENSE = "DIRECT_LICENSE"
    OTHER = "OTHER"


class TrackRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    isrc: Optional[str] = Field(default=None, max_length=20)
    iswc: Optional[str] = Field(default=None, max_length=20)
    release_date: Optional[date] = None
    master_rights_share: float = Field(default=1.0, ge=0, le=1)
    publishing_rights_share: float = Field(default=1.0, ge=0, le=1)
    writer_share: float = Field(default=1.0, ge=0, le=1)
    neighboring_rights_share: float = Field(default=1.0, ge=0, le=1)


class RoyaltyPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    gross_cents: int = Field(ge=0)
    adjustments_cents: int = 0
    currency_code: str = Field(default="EUR", min_length=3, max_length=3)
    source: RoyaltySource
    verified: bool = False

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_period(self) -> "RoyaltyPeriod":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self

    @property
    def net_cents(self) -> int:
        return max(0, self.gross_cents + self.adjustments_cents)


class CatalogPassportDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artist_label: str = Field(min_length=1, max_length=300)
    tracks: list[TrackRecord] = Field(default_factory=list, max_length=100_000)
    territories: list[str] = Field(default_factory=list, max_length=250)
    royalty_sources: list[RoyaltySource] = Field(default_factory=list, max_length=20)
    revenue_history: list[RoyaltyPeriod] = Field(default_factory=list, max_length=36)
    previous_advances_cents: int = Field(default=0, ge=0)
    liens_or_disputes: list[str] = Field(default_factory=list, max_length=50)
    metadata_completeness: float = Field(default=0.0, ge=0, le=1)
    anti_fraud_status: Literal["PENDING", "CLEAR", "REVIEW"] = "PENDING"
    rights_ownership_share: float = Field(default=1.0, ge=0, le=1)
    top_track_revenue_share: Optional[float] = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_revenue_currency(self) -> "CatalogPassportDraft":
        currencies = {period.currency_code for period in self.revenue_history}
        if len(currencies) > 1:
            raise ValueError("revenue_history must use one currency; no implicit FX conversion is performed")
        return self


class CatalogPassport(CatalogPassportDraft):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DocumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    application_id: UUID
    document_type: DocumentType
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    storage_key: Optional[str] = None
    status: DocumentStatus = DocumentStatus.PENDING_UPLOAD
    version: int = Field(default=1, ge=1)
    uploaded_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None


class ValuationRequest(BaseModel):
    """Operator-supplied assumptions; values must come from verified benchmarks."""

    model_config = ConfigDict(extra="forbid")

    benchmark_version: str = Field(min_length=1, max_length=80)
    benchmark_multiple_low: float = Field(gt=0, le=20)
    benchmark_multiple_median: float = Field(gt=0, le=20)
    benchmark_multiple_high: float = Field(gt=0, le=20)
    currency_code: str = Field(default="EUR", min_length=3, max_length=3)
    valid_for_days: int = Field(default=14, ge=1, le=90)
    payment_terms_days: int = Field(default=5, ge=1, le=60)

    @model_validator(mode="after")
    def validate_multiples(self) -> "ValuationRequest":
        if not (
            self.benchmark_multiple_low
            <= self.benchmark_multiple_median
            <= self.benchmark_multiple_high
        ):
            raise ValueError("benchmark multiples must be ordered low <= median <= high")
        return self

    @field_validator("currency_code")
    @classmethod
    def normalize_valuation_currency(cls, value: str) -> str:
        return value.upper()


class ValuationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    benchmark_version: str
    low_cents: int = Field(ge=0)
    median_cents: int = Field(ge=0)
    high_cents: int = Field(ge=0)
    currency_code: str = "EUR"
    confidence_score: float = Field(ge=0, le=1)
    risk_adjustment: float = Field(gt=0, le=1)
    explanations: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    manual_review_required: bool
    calculated_at: datetime = Field(default_factory=utc_now)


class OfferScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    application_id: UUID
    version: str
    sale_percentage: Literal[50, 75, 100]
    cash_low_cents: int = Field(ge=0)
    cash_median_cents: int = Field(ge=0)
    cash_high_cents: int = Field(ge=0)
    currency_code: str = "EUR"
    rights_transferred: dict[str, float]
    rights_retained: dict[str, float]
    territories: list[str]
    royalty_sources: list[RoyaltySource]
    payment_date: date
    valuation_version: str
    valuation_range: dict[str, int]
    risk_adjustments: list[str]
    exceptions: list[str]
    valid_until: date
    created_at: datetime = Field(default_factory=utc_now)


class SellerApplication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    contact_email: str
    seller_name: Optional[str] = None
    status: ApplicationStatus
    catalog_passport: CatalogPassport
    valuation: Optional[ValuationResult] = None
    offers: list[OfferScenario] = Field(default_factory=list)
    accepted_offer_id: Optional[UUID] = None
    consent_version: str
    consent_marketing: bool = False
    referral_id: Optional[str] = None
    consent_at: datetime
    created_at: datetime
    updated_at: datetime


class SellerApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_email: str = Field(min_length=3, max_length=320)
    seller_name: Optional[str] = Field(default=None, max_length=160)
    artist_label: str = Field(min_length=1, max_length=300)
    consent_version: str = Field(min_length=1, max_length=80)
    consent_marketing: bool = False
    referral_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    territories: list[str] = Field(default_factory=list, max_length=250)
    royalty_sources: list[RoyaltySource] = Field(default_factory=list, max_length=20)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("contact_email must be a valid email address")
        return normalized


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=1, le=25_000_000)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class DocumentUploadResponse(BaseModel):
    document: DocumentRecord
    upload_url: str
    expires_in_seconds: int = 900


class DocumentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["VERIFIED", "REJECTED"]
    reason: Optional[str] = Field(default=None, max_length=500)


class RoyaltyReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    amount_cents: int = Field(ge=0)
    currency_code: str = Field(default="EUR", min_length=3, max_length=3)
    source: RoyaltySource
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("currency_code")
    @classmethod
    def normalize_report_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_report_period(self) -> "RoyaltyReportCreate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class RoyaltyReport(RoyaltyReportCreate):
    id: UUID = Field(default_factory=uuid4)
    application_id: UUID
    status: ReportStatus = ReportStatus.SUBMITTED
    created_at: datetime = Field(default_factory=utc_now)


class SupportRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=4000)


class ApplicationStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus
    reason: Optional[str] = Field(default=None, max_length=500)


class PayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offer_id: UUID
    recipient_token: str = Field(min_length=8, max_length=500)


class PayoutView(BaseModel):
    id: UUID
    application_id: UUID
    offer_id: UUID
    amount_cents: int
    currency_code: str
    status: str
    provider_reference: Optional[str] = None
    failure_reason: Optional[str] = None
    receipt_url: Optional[str] = None
    receipt_sha256: Optional[str] = None
    receipt_version: Optional[str] = None
    created_at: datetime
    updated_at: datetime
