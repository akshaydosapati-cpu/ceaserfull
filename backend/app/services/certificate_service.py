from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.certificate import Certificate, CertificateDocument
from app.schemas.certificate import CERTIFICATE_ID_PATTERN, PublicCertificateResponse


_CERTIFICATE_ID = re.compile(CERTIFICATE_ID_PATTERN)


class CertificateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def normalize_id(certificate_id: str) -> str:
        normalized = str(certificate_id or "").strip().upper()
        if not _CERTIFICATE_ID.fullmatch(normalized):
            raise ValueError("malformed_certificate_id")
        return normalized

    def find(self, certificate_id: str) -> Certificate | None:
        normalized = self.normalize_id(certificate_id)
        return self.db.query(Certificate).filter(Certificate.certificate_id == normalized).one_or_none()

    def public_record(self, certificate: Certificate, *, public_base_url: str) -> PublicCertificateResponse:
        certificate_id = certificate.certificate_id
        verification_base = "https://www.heyceaser.in"
        current_types = {
            item.document_type
            for item in certificate.documents
            if item.status == "current"
        }
        return PublicCertificateResponse(
            certificate_id=certificate_id,
            intern_name=certificate.intern_name,
            role=certificate.role,
            organization=certificate.organization,
            issue_date=certificate.issue_date,
            start_date=certificate.start_date,
            end_date=certificate.end_date,
            status=certificate.status,
            verification_url=f"{verification_base}/verify/{certificate_id}",
            has_certificate="internship_certificate" in current_types,
            has_offer_letter="offer_letter" in current_types,
        )
