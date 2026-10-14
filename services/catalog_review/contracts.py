from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Intake(Contract):
    source: Literal["typeform", "short_form"]
    form_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    response_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    email: str = Field(pattern=r"^[a-zA-Z0-9._+-]+@example\.com$", max_length=254)
    landing_path: Literal[
        "/",
        "/apply/",
        "/sell/",
        "/calculator/",
        "/guides/music-catalog-valuation-2026/",
    ] = "/apply/"


class LiveIntake(Intake):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        from .intake import normalize_email

        return normalize_email(value)


class Rights(Contract):
    release_reference: str = Field(
        min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"
    )
    ownership: Literal["known", "unknown"]
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    artist: Optional[str] = Field(default=None, min_length=1, max_length=240)
    rights_scope: Literal["masters", "publishing", "both", "unknown"] = "unknown"
    obligations: Literal["none_declared", "present", "unknown"] = "unknown"
    share_percent: Optional[Decimal] = Field(
        default=None, gt=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False
    )

    @model_validator(mode="after")
    def match_ownership(self):
        if (self.ownership == "known") != (self.share_percent is not None):
            raise ValueError(
                "Known ownership requires a share; unknown ownership has no share"
            )
        return self


class Draft(Contract):
    source: Literal[
        "documents"
    ]  # Provider import has a separate, unimplemented contract.
    rights: List[Rights] = Field(min_length=1, max_length=200)
    document_ids: List[UUID] = Field(default_factory=list, max_length=40)
    future_music_excluded: Literal[True]

    @field_validator("future_music_excluded", mode="before")
    @classmethod
    def explicit_future_exclusion(cls, value):
        if value is not True:
            raise ValueError("Explicit exclusion of future music is required")
        return value

    @model_validator(mode="after")
    def unique_references(self):
        if len({r.release_reference for r in self.rights}) != len(self.rights):
            raise ValueError("Duplicate release reference")
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("Duplicate document reference")
        return self


class SaveDraft(Contract):
    revision: StrictInt = Field(ge=0)
    draft: Draft


class Submit(Contract):
    request_id: UUID
    revision: StrictInt = Field(ge=0)
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Explicit confirmation is required")
        return value


class ExchangeInvitation(Contract):
    token: str = Field(min_length=70, max_length=160)


class RequestAccess(Contract):
    workspace_id: UUID
    email: str = Field(pattern=r"^[a-zA-Z0-9._+-]+@example\.com$", max_length=254)


class LiveRequestAccess(RequestAccess):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        from .intake import normalize_email

        return normalize_email(value)


class ReviewMessage(Contract):
    request_id: UUID
    body: str = Field(min_length=1, max_length=4000, strict=True)

    @field_validator("body")
    @classmethod
    def meaningful_text(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError(
                "A non-empty message without control characters is required"
            )
        return value


class Upload(Contract):
    filename: str = Field(min_length=5, max_length=180)

    @field_validator("filename")
    @classmethod
    def plain_filename(cls, value):
        if any(ord(c) < 32 or c in '/\\"' for c in value):
            raise ValueError("Use a plain filename")
        if not value.lower().endswith((".pdf", ".csv", ".xlsx")):
            raise ValueError("Unsupported file type")
        return value


class ReviewQuestion(ReviewMessage):
    request_documents: StrictBool = False


class ReviewReply(ReviewMessage):
    document_ids: List[UUID] = Field(default_factory=list, max_length=40)

    @field_validator("document_ids")
    @classmethod
    def unique_documents(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Duplicate document reference")
        return value


class ContinueInterest(Contract):
    request_id: UUID
