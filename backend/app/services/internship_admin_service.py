from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.certificate import Certificate, CertificateDocument
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.storage_service import StorageService


MAX_PDF_BYTES = 12 * 1024 * 1024
DOCUMENT_TYPES = {"offer_letter", "internship_certificate", "supporting_document"}


class InternshipAdminService:
    def __init__(self, db: Session, actor: User):
        self.db = db
        self.actor = actor

    def generate_certificate_id(self, issue_year: int) -> str:
        prefix = f"CEASER-INT-{issue_year}-"
        existing = self.db.query(Certificate.certificate_id).filter(Certificate.certificate_id.like(f"{prefix}%")).all()
        numbers = [int(value[0].removeprefix(prefix)) for value in existing if value[0].removeprefix(prefix).isdigit()]
        return f"{prefix}{max(numbers, default=0) + 1:03d}"

    def create(self, *, intern_name: str, role: str, start_date: date, end_date: date, issue_date: date, certificate_id: str | None) -> Certificate:
        if end_date < start_date:
            raise ValueError("end_date_before_start_date")
        if not certificate_id and self.db.bind and self.db.bind.dialect.name == "postgresql":
            self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 927000000 + issue_date.year})
        normalized_id = (certificate_id or self.generate_certificate_id(issue_date.year)).strip().upper()
        if not re.fullmatch(r"CEASER-INT-[0-9]{4}-[0-9]{3,6}", normalized_id) or int(normalized_id.split("-")[2]) != issue_date.year:
            raise ValueError("invalid_certificate_id")
        if self.db.query(Certificate.id).filter(Certificate.certificate_id == normalized_id).first():
            raise ValueError("duplicate_certificate_id")
        record = Certificate(certificate_id=normalized_id, intern_name=intern_name.strip(), role=role.strip(), organization="CEASER", start_date=start_date, end_date=end_date, issue_date=issue_date, status="draft")
        self.db.add(record)
        self.db.flush()
        self._audit("internship.created", record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def upload(self, record: Certificate, *, document_type: str, filename: str, content_type: str, content: bytes) -> CertificateDocument:
        if document_type not in DOCUMENT_TYPES:
            raise ValueError("unsupported_document_type")
        if content_type not in {"application/pdf", "application/x-pdf"} or not content.startswith(b"%PDF-"):
            raise ValueError("invalid_pdf")
        if not content or len(content) > MAX_PDF_BYTES:
            raise ValueError("file_too_large")
        current = self.db.query(CertificateDocument).filter(CertificateDocument.certificate_record_id == record.id, CertificateDocument.document_type == document_type, CertificateDocument.status == "current").all()
        version = max((item.version for item in self.db.query(CertificateDocument).filter(CertificateDocument.certificate_record_id == record.id, CertificateDocument.document_type == document_type)), default=0) + 1
        for item in current:
            item.status = "archived"
        secure_name = f"{uuid4().hex}.pdf"
        storage_path = StorageService().store(user_id=f"internships/{record.id}/{document_type}", filename=secure_name, content=content, content_type="application/pdf")
        original_filename = re.sub(r"[^A-Za-z0-9._ -]+", "-", Path(filename).name).strip(" .-")[:255] or "document.pdf"
        document = CertificateDocument(certificate_record_id=record.id, document_type=document_type, storage_path=storage_path, original_filename=original_filename, mime_type="application/pdf", file_size=len(content), version=version, status="current", uploaded_by=self.actor.id)
        self.db.add(document)
        self.db.flush()
        self._audit("internship.document_replaced" if current else "internship.document_uploaded", record, {"document_type": document_type, "version": version})
        self.db.commit()
        self.db.refresh(document)
        return document

    def publish(self, record: Certificate) -> None:
        has_certificate = self.db.query(CertificateDocument.id).filter(CertificateDocument.certificate_record_id == record.id, CertificateDocument.document_type == "internship_certificate", CertificateDocument.status == "current").first()
        if not has_certificate or not record.start_date or not record.end_date:
            raise ValueError("record_incomplete")
        record.status = "published"
        self._audit("internship.published", record)
        self.db.commit()

    def set_status(self, record: Certificate, status: str) -> None:
        record.status = status
        self._audit(f"internship.{status}", record)
        self.db.commit()

    def delete_document(self, record: Certificate, document: CertificateDocument) -> None:
        document.status = "deleted"
        self._audit("internship.document_deleted", record, {"document_type": document.document_type, "version": document.version})
        self.db.commit()

    def _audit(self, action: str, record: Certificate, metadata: dict | None = None) -> None:
        AuditService(self.db).record(user_id=self.actor.id, action=action, resource_type="internship", resource_id=record.id, metadata=metadata, commit=False)
