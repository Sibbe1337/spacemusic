import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Column
import sqlalchemy as sa

class LedgerEntryBase(SQLModel):
    offer_id: uuid.UUID = Field(sa_column=Column(sa.Uuid, nullable=False, index=True))
    debit_account: str = Field(nullable=False) # e.g., "cash_on_hand", "stripe_payable"
    credit_account: str = Field(nullable=False) # e.g., "payouts_clearing", "revenue"
    amount_cents: int = Field(nullable=False)
    currency_code: str = Field(default="EUR", nullable=False) # Assuming payouts primarily in EUR
    description: Optional[str] = Field(default=None)
    transaction_type: str = Field(default="payout", index=True) # e.g., "payout", "fee", "adjustment"
    reference_id: Optional[str] = Field(default=None, index=True) # e.g., Stripe Payout ID, Wise Transfer ID

class LedgerEntry(LedgerEntryBase, table=True):
    # __tablename__ = "ledger_entry" # Explicit table name if needed, SQLModel infers by default
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False)
    transaction_timestamp: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

class LedgerEntryCreate(LedgerEntryBase):
    pass

class LedgerEntryRead(LedgerEntryBase):
    id: uuid.UUID
    transaction_timestamp: datetime
    created_at: datetime 