import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class OfferStatus(str, Enum):
    PENDING_VALUATION = "PENDING_VALUATION"
    DATA_REQUIRED = "DATA_REQUIRED"
    UNDER_REVIEW = "UNDER_REVIEW"
    OFFER_READY = "OFFER_READY"
    ACCEPTED = "ACCEPTED"
    PAYOUT_REQUESTED = "PAYOUT_REQUESTED"
    PAID_OUT = "PAID_OUT"
    REJECTED = "REJECTED"
    VALUATION_FAILED = "VALUATION_FAILED"


class CreatorBase(SQLModel):
    platform_id: str = Field(index=True, unique=True, nullable=False)
    platform_name: str = Field(nullable=False)
    username: str = Field(index=True, nullable=False)
    display_name: Optional[str] = Field(default=None)


class Creator(CreatorBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    offers: list["Offer"] = Relationship(back_populates="creator")


class CreatorCreate(CreatorBase):
    pass


class CreatorRead(CreatorBase):
    id: int
    created_at: datetime
    updated_at: datetime


class CreatorReadWithOffers(CreatorRead):
    offers: List["OfferRead"] = []


class OfferBase(SQLModel):
    title: str = Field(nullable=False)
    description: Optional[str] = Field(default=None)
    amount_cents: int = Field(default=0, ge=0, nullable=False)
    currency_code: str = Field(default="EUR", min_length=3, max_length=3, nullable=False)
    status: OfferStatus = Field(default=OfferStatus.PENDING_VALUATION, index=True, nullable=False)
    creator_id: int = Field(foreign_key="creator.id", index=True, nullable=False)
    price_low_eur: Optional[int] = Field(default=None, ge=0, nullable=True)
    price_median_eur: Optional[int] = Field(default=None, ge=0, nullable=True)
    price_high_eur: Optional[int] = Field(default=None, ge=0, nullable=True)
    valuation_confidence: Optional[float] = Field(default=None, ge=0, le=1, nullable=True)
    pdf_url: Optional[str] = Field(default=None, nullable=True)
    pdf_hash: Optional[str] = Field(default=None, nullable=True)
    last_payout_method: Optional[str] = Field(default=None, nullable=True)
    last_payout_reference: Optional[str] = Field(default=None, nullable=True)


class Offer(OfferBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    creator: Creator = Relationship(back_populates="offers")


class OfferCreate(OfferBase):
    pass


class OfferRead(OfferBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class OfferReadWithCreator(OfferRead):
    creator: CreatorRead
