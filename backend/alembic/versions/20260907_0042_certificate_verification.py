"""Add public certificate verification records.

Revision ID: 20260907_0042
Revises: 20260828_0041
"""

from alembic import op
import sqlalchemy as sa
from datetime import date, datetime, timezone


revision = "20260907_0042"
down_revision = "20260828_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    certificates = op.create_table(
        "certificates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("certificate_id", sa.String(length=64), nullable=False),
        sa.Column("intern_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("certificate_document", sa.String(length=1000), nullable=True),
        sa.Column("offer_letter_document", sa.String(length=1000), nullable=True),
        sa.Column("certificate_public", sa.Boolean(), nullable=False),
        sa.Column("offer_letter_public", sa.Boolean(), nullable=False),
        sa.CheckConstraint("status IN ('valid', 'revoked', 'expired')", name="ck_certificates_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("certificate_id"),
    )
    op.create_index(op.f("ix_certificates_certificate_id"), "certificates", ["certificate_id"], unique=True)
    op.create_index(op.f("ix_certificates_status"), "certificates", ["status"], unique=False)
    op.bulk_insert(
        certificates,
        [
            {
                "id": "1f50a131-91b8-47f3-bf68-b763aa0c2001",
                "created_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 9, 10, tzinfo=timezone.utc),
                "certificate_id": "CEASER-INT-2026-001",
                "intern_name": "Chirag Chouhan",
                "role": "QA Testing Intern",
                "organization": "CEASER",
                "issue_date": date(2026, 9, 10),
                "status": "valid",
                "certificate_document": "bundled://CEASER-INT-2026-001.pdf",
                "offer_letter_document": None,
                "certificate_public": True,
                "offer_letter_public": False,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_certificates_status"), table_name="certificates")
    op.drop_index(op.f("ix_certificates_certificate_id"), table_name="certificates")
    op.drop_table("certificates")
