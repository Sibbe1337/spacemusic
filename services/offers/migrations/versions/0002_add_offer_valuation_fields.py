"""Add valuation, document, and payout fields to offers."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_offer_valuation_fields"
down_revision: Union[str, None] = "0001_create_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for column in (
        sa.Column("price_low_eur", sa.Integer(), nullable=True),
        sa.Column("price_median_eur", sa.Integer(), nullable=True),
        sa.Column("price_high_eur", sa.Integer(), nullable=True),
        sa.Column("valuation_confidence", sa.Float(), nullable=True),
        sa.Column("pdf_url", sa.String(), nullable=True),
        sa.Column("pdf_hash", sa.String(), nullable=True),
        sa.Column("last_payout_method", sa.String(), nullable=True),
        sa.Column("last_payout_reference", sa.String(), nullable=True),
    ):
        op.add_column("offer", column)


def downgrade() -> None:
    for name in (
        "last_payout_reference",
        "last_payout_method",
        "pdf_hash",
        "pdf_url",
        "valuation_confidence",
        "price_high_eur",
        "price_median_eur",
        "price_low_eur",
    ):
        op.drop_column("offer", name)
