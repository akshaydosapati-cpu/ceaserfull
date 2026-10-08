"""Add managed internship documents and publishing lifecycle.

Revision ID: 20260907_0043
Revises: 20260907_0042
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "20260907_0043"
down_revision = "20260907_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("certificates", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("certificates", sa.Column("end_date", sa.Date(), nullable=True))
    op.drop_constraint("ck_certificates_status", "certificates", type_="check")
    op.execute("UPDATE certificates SET status = CASE WHEN status = 'valid' THEN 'published' ELSE 'revoked' END")
    op.create_check_constraint("ck_certificates_status", "certificates", "status IN ('draft', 'published', 'revoked')")
    documents = op.create_table(
        "certificate_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("certificate_record_id", sa.String(length=36), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("uploaded_by", sa.String(length=36), nullable=True),
        sa.CheckConstraint("document_type IN ('offer_letter', 'internship_certificate', 'supporting_document')", name="ck_certificate_documents_type"),
        sa.CheckConstraint("status IN ('current', 'archived', 'deleted')", name="ck_certificate_documents_status"),
        sa.ForeignKeyConstraint(["certificate_record_id"], ["certificates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certificate_documents_certificate_record_id", "certificate_documents", ["certificate_record_id"])
    op.create_index("ix_certificate_documents_document_type", "certificate_documents", ["document_type"])
    op.create_index("ix_certificate_documents_status", "certificate_documents", ["status"])
    op.bulk_insert(documents, [{"id": "965cf850-d075-4b4e-89ab-7a6cb1ad0043", "created_at": datetime(2026, 9, 10, tzinfo=timezone.utc), "certificate_record_id": "1f50a131-91b8-47f3-bf68-b763aa0c2001", "document_type": "internship_certificate", "storage_path": "bundled://CEASER-INT-2026-001.pdf", "original_filename": "CEASER-INT-2026-001.pdf", "mime_type": "application/pdf", "file_size": 0, "version": 1, "status": "current", "uploaded_by": None}])


def downgrade() -> None:
    op.drop_table("certificate_documents")
    op.drop_constraint("ck_certificates_status", "certificates", type_="check")
    op.execute("UPDATE certificates SET status = CASE WHEN status = 'published' THEN 'valid' WHEN status = 'draft' THEN 'expired' ELSE status END")
    op.create_check_constraint("ck_certificates_status", "certificates", "status IN ('valid', 'revoked', 'expired')")
    op.drop_column("certificates", "end_date")
    op.drop_column("certificates", "start_date")
