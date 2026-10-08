from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.certificates import routes
from app.core.database.session import get_db
from app.core.rate_limiter import BoundedRateLimiter
from app.main import create_app
from app.models.certificate import Certificate, CertificateDocument


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Certificate.__table__.create(engine, checkfirst=True)
CertificateDocument.__table__.create(engine, checkfirst=True)


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app = create_app()
app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def seed(certificate_id: str, status: str, *, document: str | None = None) -> None:
    with TestingSession() as db:
        existing = db.query(Certificate).filter(Certificate.certificate_id == certificate_id).one_or_none()
        if existing:
            db.delete(existing)
            db.flush()
        record = Certificate(
                certificate_id=certificate_id,
                intern_name="Chirag Chouhan",
                role="QA Testing Intern",
                organization="CEASER",
                issue_date=date(2026, 9, 10),
                start_date=date(2026, 6, 1),
                end_date=date(2026, 8, 31),
                status=status,
            )
        db.add(record)
        db.flush()
        if document:
            db.add(CertificateDocument(certificate_record_id=record.id, document_type="internship_certificate", storage_path=document, original_filename="certificate.pdf", mime_type="application/pdf", file_size=308736, version=1, status="current"))
        db.commit()


def setup_function() -> None:
    routes.rate_limiter = BoundedRateLimiter(max_keys=100, ttl_seconds=60)
    seed("CEASER-INT-2026-001", "published", document="bundled://CEASER-INT-2026-001.pdf")
    seed("CEASER-INT-2026-002", "revoked")
    seed("CEASER-INT-2026-003", "draft")


def test_valid_certificate_returns_minimal_public_record() -> None:
    response = client.get("/certificates/CEASER-INT-2026-001")
    assert response.status_code == 200
    result = response.json()
    assert result == {
        "certificate_id": "CEASER-INT-2026-001",
        "intern_name": "Chirag Chouhan",
        "role": "QA Testing Intern",
        "organization": "CEASER",
        "issue_date": "2026-09-10",
        "start_date": "2026-06-01",
        "end_date": "2026-08-31",
        "status": "published",
        "verification_url": "https://www.heyceaser.in/verify/CEASER-INT-2026-001",
        "has_certificate": True,
        "has_offer_letter": False,
    }


def test_post_lookup_normalizes_lowercase_id() -> None:
    response = client.post("/certificates/verify", json={"certificate_id": "ceaser-int-2026-001"})
    assert response.status_code == 200
    assert response.json()["certificate_id"] == "CEASER-INT-2026-001"


def test_empty_and_malformed_ids_are_rejected() -> None:
    assert client.post("/certificates/verify", json={"certificate_id": ""}).status_code == 422
    assert client.get("/certificates/not-a-certificate").status_code == 422
    assert client.get("/certificates/%27%20OR%201%3D1--").status_code == 422


def test_unknown_revoked_and_draft_states_are_private() -> None:
    assert client.get("/certificates/CEASER-INT-2026-999").status_code == 404
    revoked = client.get("/certificates/CEASER-INT-2026-002")
    draft = client.get("/certificates/CEASER-INT-2026-003")
    assert revoked.status_code == 200 and revoked.json()["status"] == "revoked"
    assert draft.status_code == 404


def test_public_certificate_document_is_not_exposed() -> None:
    response = client.get("/certificates/CEASER-INT-2026-001/documents/certificate")
    assert response.status_code == 404


def test_all_public_document_paths_are_blocked() -> None:
    assert client.get("/certificates/CEASER-INT-2026-001/documents/offer-letter").status_code == 404
    assert client.get("/certificates/CEASER-INT-2026-001/documents/..%2F..%2F.env").status_code in {404, 422}
    assert client.get("/certificates/CEASER-INT-2026-002/documents/certificate").status_code == 404


def test_public_verification_is_rate_limited_by_ip() -> None:
    routes.rate_limiter = BoundedRateLimiter(max_keys=10, ttl_seconds=60)
    for _ in range(30):
        assert client.get("/certificates/CEASER-INT-2026-001").status_code == 200
    limited = client.get("/certificates/CEASER-INT-2026-001")
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) > 0
