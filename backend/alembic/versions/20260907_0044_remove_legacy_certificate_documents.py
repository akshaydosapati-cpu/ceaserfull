"""Remove legacy certificate document columns.

Revision ID: 20260907_0044
Revises: 20260907_0043
"""
from alembic import op
import sqlalchemy as sa

revision = "20260907_0044"
down_revision = "20260907_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("certificates", "offer_letter_public")
    op.drop_column("certificates", "certificate_public")
    op.drop_column("certificates", "offer_letter_document")
    op.drop_column("certificates", "certificate_document")


def downgrade() -> None:
    op.add_column("certificates", sa.Column("certificate_document", sa.String(length=1000), nullable=True))
    op.add_column("certificates", sa.Column("offer_letter_document", sa.String(length=1000), nullable=True))
    op.add_column("certificates", sa.Column("certificate_public", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("certificates", sa.Column("offer_letter_public", sa.Boolean(), nullable=False, server_default=sa.false()))
