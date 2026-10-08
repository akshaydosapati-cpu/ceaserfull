from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database.session import get_db
from app.core.rate_limiter import rate_limiter
from app.schemas.certificate import CertificateVerifyRequest, PublicCertificateResponse
from app.services.certificate_service import CertificateService


router = APIRouter(prefix="/certificates", tags=["certificate-verification"])
logger = logging.getLogger(__name__)


def _enforce_public_limit(request: Request) -> None:
    identity = request.client.host if request.client else "unknown"
    decision = rate_limiter.check("certificate-verification", identity, limit=30, window_seconds=60)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Too many verification attempts. Please try again shortly."},
            headers={"Retry-After": str(decision.retry_after)},
        )


def _verification_response(certificate_id: str, request: Request, db: Session) -> PublicCertificateResponse:
    _enforce_public_limit(request)
    service = CertificateService(db)
    try:
        certificate = service.find(certificate_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_certificate_id", "message": "Enter a valid CEASER Certificate ID."},
        ) from exc
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "certificate_not_found", "message": "Certificate Not Found"},
        )
    if certificate.status == "draft":
        raise HTTPException(status_code=404, detail={"code": "certificate_not_found", "message": "Certificate Not Found"})
    logger.info(
        "certificate_verification request_id=%s certificate_id=%s status=%s",
        getattr(request.state, "request_id", None),
        certificate.certificate_id,
        certificate.status,
    )
    return service.public_record(certificate, public_base_url=str(request.base_url))


@router.post("/verify", response_model=PublicCertificateResponse)
def verify_certificate(
    payload: CertificateVerifyRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PublicCertificateResponse:
    return _verification_response(payload.certificate_id, request, db)


@router.get("/{certificate_id}", response_model=PublicCertificateResponse)
def get_certificate(
    certificate_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PublicCertificateResponse:
    return _verification_response(certificate_id, request, db)
