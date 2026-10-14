import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Column, Field, SQLModel
import sqlalchemy as sa


class LedgerEntryBase(SQLModel):
    # Nullable during the legacy ledger backfill; new writes must populate both IDs.
    payout_intent_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(sa.Uuid, nullable=True, index=True, unique=True)
    )
    application_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(sa.Uuid, nullable=True, index=True)
    )
    offer_id: Optional[uuid.UUID] = Field(
        default=None, sa_column=Column(sa.Uuid, nullable=True, index=True)
    )
    debit_account: str = Field(nullable=False)
    credit_account: str = Field(nullable=False)
    amount_cents: int = Field(nullable=False, ge=0)
    currency_code: str = Field(default="EUR", min_length=3, max_length=3, nullable=False)
    description: Optional[str] = Field(default=None)
    transaction_type: str = Field(default="payout", index=True)
    reference_id: Optional[str] = Field(default=None, index=True)

class LedgerEntry(LedgerEntryBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)
    transaction_timestamp: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

class LedgerEntryCreate(LedgerEntryBase):
    pass

class LedgerEntryRead(LedgerEntryBase):
    id: uuid.UUID
    transaction_timestamp: datetime
    created_at: datetime
