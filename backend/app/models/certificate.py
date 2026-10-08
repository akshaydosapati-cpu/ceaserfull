from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Certificate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "certificates"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'revoked')", name="ck_certificates_status"),
    )

    certificate_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    intern_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[str] = mapped_column(String(255), nullable=False, default="CEASER")
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="draft")
    documents: Mapped[list["CertificateDocument"]] = relationship(back_populates="certificate", cascade="all, delete-orphan")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CertificateDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "certificate_documents"
    __table_args__ = (
        CheckConstraint("document_type IN ('offer_letter', 'internship_certificate', 'supporting_document')", name="ck_certificate_documents_type"),
        CheckConstraint("status IN ('current', 'archived', 'deleted')", name="ck_certificate_documents_status"),
    )

    certificate_record_id: Mapped[str] = mapped_column(ForeignKey("certificates.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    storage_path: Mapped[str] = mapped_column(String(1000))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    file_size: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="current", index=True)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    certificate: Mapped[Certificate] = relationship(back_populates="documents")
