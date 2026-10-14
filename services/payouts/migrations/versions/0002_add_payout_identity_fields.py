"""Add payout and application identity to the legacy ledger table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_payout_identity_fields"
down_revision: Union[str, None] = "6364fcaeceb9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ledgerentry", sa.Column("payout_intent_id", sa.Uuid(), nullable=True))
    op.add_column("ledgerentry", sa.Column("application_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_ledgerentry_payout_intent_id",
        "ledgerentry",
        ["payout_intent_id"],
        unique=True,
    )
    op.create_index("ix_ledgerentry_application_id", "ledgerentry", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_ledgerentry_application_id", table_name="ledgerentry")
    op.drop_index("ix_ledgerentry_payout_intent_id", table_name="ledgerentry")
    op.drop_column("ledgerentry", "application_id")
    op.drop_column("ledgerentry", "payout_intent_id")
