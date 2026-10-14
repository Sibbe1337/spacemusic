"""Keep the legacy offer status index migration compatible.

Revision ID: d198261eb7a4
Revises: 0002_add_offer_valuation_fields
Create Date: 2025-05-22 08:33:08.617749

"""


# revision identifiers, used by Alembic.
revision = 'd198261eb7a4'
down_revision = '0002_add_offer_valuation_fields'
branch_labels = None
depends_on = None


def upgrade():
    # 0001 already creates the correctly named index on the singular table.
    pass


def downgrade():
    pass
