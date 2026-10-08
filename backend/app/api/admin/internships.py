from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.admin.routes import require_admin_user
from app.core.database.session import get_db
from app.core.database.execution import run_serial_db
from app.models.certificate import Certificate, CertificateDocument
from app.models.user import User
from app.services.internship_admin_service import InternshipAdminService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/admin/internships", tags=["admin-internships"])


class InternshipCreate(BaseModel):
    intern_name: str = Field(min_length=2, max_length=255)
    role: str = Field(min_length=2, max_length=255)
    start_date: date
    end_date: date
    issue_date: date
    certificate_id: str | None = Field(default=None, max_length=64)


class InternshipUpdate(BaseModel):
    intern_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = Field(default=None, min_length=2, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    issue_date: date | None = None


def serialize(record: Certificate) -> dict:
    return {"id": record.id, "certificate_id": record.certificate_id, "intern_name": record.intern_name, "role": record.role, "organization": record.organization, "start_date": record.start_date, "end_date": record.end_date, "issue_date": record.issue_date, "status": record.status, "created_at": record.created_at, "documents": [{"id": d.id, "document_type": d.document_type, "original_filename": d.original_filename, "mime_type": d.mime_type, "file_size": d.file_size, "version": d.version, "status": d.status, "uploaded_at": d.created_at} for d in sorted(record.documents, key=lambda item: item.created_at, reverse=True)]}


def get_record(record_id: str, db: Session) -> Certificate:
    record = db.query(Certificate).filter(Certificate.id == record_id).one_or_none()
    if not record:
        raise HTTPException(404, detail={"code": "internship_not_found", "message": "Internship record not found."})
    return record


@router.get("")
def list_records(user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)], search: str = Query(default="", max_length=120), status: str | None = None) -> list[dict]:
    query = db.query(Certificate)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(or_(Certificate.certificate_id.ilike(term), Certificate.intern_name.ilike(term), Certificate.role.ilike(term)))
    if status in {"draft", "published", "revoked"}:
        query = query.filter(Certificate.status == status)
    return [serialize(item) for item in query.order_by(Certificate.issue_date.desc(), Certificate.created_at.desc()).limit(200).all()]


@router.post("", status_code=201)
def create_record(payload: InternshipCreate, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    try:
        return serialize(InternshipAdminService(db, user).create(**payload.model_dump()))
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail={"code": "duplicate_certificate_id", "message": "Certificate ID already exists."}) from exc
    except ValueError as exc:
        messages = {"duplicate_certificate_id": "Certificate ID already exists.", "invalid_certificate_id": "Certificate ID is invalid or does not match the issue year.", "end_date_before_start_date": "End date must be after the start date."}
        raise HTTPException(409 if str(exc) == "duplicate_certificate_id" else 422, detail={"code": str(exc), "message": messages.get(str(exc), "Invalid internship record.")}) from exc


@router.get("/{record_id}")
def read_record(record_id: str, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    return serialize(get_record(record_id, db))


@router.put("/{record_id}")
def update_record(record_id: str, payload: InternshipUpdate, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    record = get_record(record_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value.strip() if isinstance(value, str) else value)
    if record.start_date and record.end_date and record.end_date < record.start_date:
        raise HTTPException(422, detail={"code": "invalid_dates", "message": "End date must be after the start date."})
    if record.issue_date.year != int(record.certificate_id.split("-")[2]):
        raise HTTPException(422, detail={"code": "issue_year_mismatch", "message": "Issue date must remain in the Certificate ID year."})
    InternshipAdminService(db, user)._audit("internship.updated", record)
    db.commit(); db.refresh(record)
    return serialize(record)


@router.post("/{record_id}/documents", status_code=201)
async def upload_document(record_id: str, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)], document_type: Annotated[str, Form()], upload: Annotated[UploadFile, File()]) -> dict:
    try:
        content = await upload.read(12 * 1024 * 1024 + 1)
        record = await run_serial_db(get_record, record_id, db)
        document = await run_serial_db(InternshipAdminService(db, user).upload, record, document_type=document_type, filename=upload.filename or "document.pdf", content_type=upload.content_type or "", content=content)
        return {"id": document.id, "document_type": document.document_type, "original_filename": document.original_filename, "version": document.version, "status": document.status}
    except ValueError as exc:
        message = {"invalid_pdf": "Only valid PDF files are supported.", "file_too_large": "File exceeds the 12 MB limit.", "unsupported_document_type": "Unsupported document type."}.get(str(exc), "Upload failed. Please try again.")
        raise HTTPException(422, detail={"code": str(exc), "message": message}) from exc


@router.get("/{record_id}/documents/{document_id}")
def document_file(record_id: str, document_id: str, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)], download: bool = False) -> Response:
    document = db.query(CertificateDocument).filter(CertificateDocument.id == document_id, CertificateDocument.certificate_record_id == record_id, CertificateDocument.status != "deleted").one_or_none()
    if not document:
        raise HTTPException(404, detail={"code": "document_not_found", "message": "Document not found."})
    try:
        content = StorageService().read_bytes(document.storage_path)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(503, detail={"code": "storage_unavailable", "message": "Document storage is temporarily unavailable."}) from exc
    disposition = "attachment" if download else "inline"
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'{disposition}; filename="{document.original_filename.replace(chr(34), "")}"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/{record_id}/documents/{document_id}", status_code=204)
def delete_document(record_id: str, document_id: str, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)]) -> Response:
    record = get_record(record_id, db)
    document = db.query(CertificateDocument).filter(CertificateDocument.id == document_id, CertificateDocument.certificate_record_id == record.id, CertificateDocument.status != "deleted").one_or_none()
    if not document:
        raise HTTPException(404, detail={"code": "document_not_found", "message": "Document not found."})
    InternshipAdminService(db, user).delete_document(record, document)
    return Response(status_code=204)


@router.post("/{record_id}/publish")
def publish(record_id: str, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    record = get_record(record_id, db)
    try:
        InternshipAdminService(db, user).publish(record)
    except ValueError as exc:
        raise HTTPException(422, detail={"code": "record_incomplete", "message": "Complete the dates and upload a certificate PDF before publishing."}) from exc
    return serialize(record)


@router.post("/{record_id}/revoke")
def revoke(record_id: str, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    record = get_record(record_id, db); InternshipAdminService(db, user).set_status(record, "revoked"); return serialize(record)


@router.post("/{record_id}/restore")
def restore(record_id: str, user: Annotated[User, Depends(require_admin_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    record = get_record(record_id, db); InternshipAdminService(db, user).publish(record); return serialize(record)
