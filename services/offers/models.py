from sqlmodel import Field, SQLModel, Relationship, Column
from typing import Optional, List
from datetime import datetime
import sqlalchemy as sa # Import sqlalchemy
import uuid

# Define Creator model
class CreatorBase(SQLModel):
    platform_id: str = Field(sa_column=sa.Column(sa.String, unique=True, index=True, nullable=False))
    platform_name: str = Field(nullable=False)
    username: str = Field(index=True, nullable=False)
    display_name: Optional[str] = Field(default=None)

class Creator(CreatorBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, sa_column_kwargs={"onupdate": datetime.utcnow})

    offers: List["Offer"] = Relationship(back_populates="creator")

class CreatorCreate(CreatorBase):
    pass

class CreatorRead(CreatorBase):
    id: int
    created_at: datetime
    updated_at: datetime

class CreatorReadWithOffers(CreatorRead):
    offers: List["OfferRead"] = []


# Define Offer model
class OfferBase(SQLModel):
    title: str = Field(nullable=False)
    description: Optional[str] = Field(default=None)
    amount_cents: int = Field(nullable=False)
    currency_code: str = Field(default="USD", nullable=False)
    status: str = Field(default="pending", index=True, nullable=False)
    creator_id: int = Field(foreign_key="creator.id", index=True, nullable=False)
    # New fields for valuation results
    price_low_eur: Optional[int] = Field(default=None, nullable=True)
    price_median_eur: Optional[int] = Field(default=None, nullable=True)
    price_high_eur: Optional[int] = Field(default=None, nullable=True)
    valuation_confidence: Optional[float] = Field(default=None, nullable=True)
    # New fields for PDF document generation
    pdf_url: Optional[str] = Field(default=None, nullable=True)
    pdf_hash: Optional[str] = Field(default=None, nullable=True) # SHA256 hash

class Offer(OfferBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, sa_column_kwargs={"onupdate": datetime.utcnow})

    creator: Creator = Relationship(back_populates="offers")

class OfferCreate(OfferBase):
    pass

class OfferRead(OfferBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class OfferReadWithCreator(OfferRead):
    creator: CreatorRead 