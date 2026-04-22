import pytest
import uuid
import io
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.note import Note
from app.models.note_feedback import NoteFeedback

# Test Cases 21-35: Note Management & Storage


def make_pdf_bytes() -> bytes:
    """Return minimal valid-ish PDF header bytes for upload testing."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type /Pages /Kids [3 0 R] /Count 1>>endobj\n"
        b"3 0 obj<</Type /Page /MediaBox [0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Size 4 /Root 1 0 R>>\nstartxref\n%%EOF"
    )


async def upload_note(client, subject_id: str, title: str = "Test Note") -> dict:
    pdf = make_pdf_bytes()
    files = {"file": ("test.pdf", io.BytesIO(pdf), "application/pdf")}
    data = {"title": title, "subject_id": subject_id, "tags": "test"}
    return await client.post("/api/v1/notes/upload", files=files, data=data)


# Helper to create and commit notes in an isolated session (no concurrent session issues)
async def create_note_committed(subject_id, user_id, title, status="ready", extracted_text=None, views=0) -> uuid.UUID:
    """Create and commit a note in its own isolated session, returning the note ID."""
    from tests.test_helpers import TestSessionLocal
    async with TestSessionLocal() as session:
        note = Note(
            user_id=user_id,
            subject_id=subject_id,
            title=title,
            file_url=f"http://s.t/{uuid.uuid4()}.pdf",
            file_size=100,
            status=status,
            extracted_text=extracted_text,
            views=views,
        )
        session.add(note)
        await session.flush()
        note_id = note.id
        await session.commit()
    return note_id


async def test_valid_pdf_upload(student_client: AsyncClient, test_subject):
    """TC-21: Verify students can upload PDF notes successfully"""
    r = await upload_note(student_client, str(test_subject.id))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["title"] == "Test Note"
    assert data["status"] == "pending"


async def test_reject_invalid_file_type(student_client: AsyncClient, test_subject):
    """TC-22: Reject files with disallowed MIME/extension"""
    files = {"file": ("malware.exe", io.BytesIO(b"MZ garbage"), "application/octet-stream")}
    data = {"title": "Bad File", "subject_id": str(test_subject.id)}
    r = await student_client.post("/api/v1/notes/upload", files=files, data=data)
    assert r.status_code == 400
    assert "Invalid file type" in r.json()["detail"]


async def test_upload_missing_subject(student_client: AsyncClient):
    """TC-23: Uploading with a non-existent subject_id returns 404"""
    files = {"file": ("test.pdf", io.BytesIO(make_pdf_bytes()), "application/pdf")}
    data = {"title": "No Subject", "subject_id": str(uuid.uuid4())}
    r = await student_client.post("/api/v1/notes/upload", files=files, data=data)
    assert r.status_code == 404


async def test_pending_status_on_upload(student_client: AsyncClient, test_subject):
    """TC-25: Newly uploaded notes default to 'pending' status"""
    r = await upload_note(student_client, str(test_subject.id), "Pending Check")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


async def test_student_cannot_see_others_pending_notes(async_client: AsyncClient, student_user, test_subject):
    """TC-26: Public listing never returns pending notes"""
    await create_note_committed(test_subject.id, student_user.id, "Private Pending", status="pending")
    r = await async_client.get("/api/v1/notes/")
    assert r.status_code == 200
    assert all(n["status"] == "ready" for n in r.json())


async def test_note_approval(super_admin_client: AsyncClient, student_client: AsyncClient, test_subject):
    """TC-29: Super admin can approve a pending note"""
    r = await upload_note(student_client, str(test_subject.id), "To Approve")
    assert r.status_code == 200
    note_id = r.json()["id"]

    pub = await super_admin_client.patch(f"/api/v1/notes/{note_id}/publish")
    assert pub.status_code == 200
    assert pub.json()["status"] == "ready"


async def test_note_rejection_with_feedback(
    super_admin_client: AsyncClient, student_client: AsyncClient, test_subject
):
    """TC-30: Super admin can reject a note with structured feedback"""
    r = await upload_note(student_client, str(test_subject.id), "To Reject")
    assert r.status_code == 200
    note_id = r.json()["id"]

    rej = await super_admin_client.patch(
        f"/api/v1/notes/{note_id}/reject",
        json={"feedback_text": "Handwriting unclear on page 3"}
    )
    assert rej.status_code == 200
    data = rej.json()
    assert data["status"] == "failed"
    assert data["feedback"]["feedback_text"] == "Handwriting unclear on page 3"


async def test_public_notes_list_only_ready(async_client: AsyncClient, student_user, test_subject):
    """TC-31: Public listing only returns 'ready' notes"""
    await create_note_committed(test_subject.id, student_user.id, "Public Ready", status="ready")
    await create_note_committed(test_subject.id, student_user.id, "Private Pending", status="pending")

    r = await async_client.get("/api/v1/notes/")
    assert r.status_code == 200
    assert all(n["status"] == "ready" for n in r.json())


async def test_listing_pagination(async_client: AsyncClient, student_user, test_subject):
    """TC-32: Pagination limit param caps number of results"""
    for i in range(8):
        await create_note_committed(test_subject.id, student_user.id, f"Pag Note {i}")
    r = await async_client.get("/api/v1/notes/?limit=5")
    assert r.status_code == 200
    assert len(r.json()) <= 5


async def test_view_count_increment(async_client: AsyncClient, student_user, test_subject):
    """TC-33: Accessing a single note detail increments view counter"""
    note_id = await create_note_committed(test_subject.id, student_user.id, "View Counter Note", views=0)

    r1 = await async_client.get(f"/api/v1/notes/{note_id}")
    assert r1.status_code == 200
    assert r1.json()["views"] == 1

    r2 = await async_client.get(f"/api/v1/notes/{note_id}")
    assert r2.status_code == 200
    assert r2.json()["views"] == 2


async def test_super_admin_delete_note(super_admin_client: AsyncClient, student_user, test_subject):
    """TC-34: Only super admins can permanently delete a note"""
    from tests.test_helpers import TestSessionLocal
    note_id = await create_note_committed(test_subject.id, student_user.id, "Note To Delete")

    r = await super_admin_client.delete(f"/api/v1/notes/{note_id}")
    assert r.status_code == 200

    async with TestSessionLocal() as session:
        result = await session.execute(select(Note).where(Note.id == note_id))
        assert result.scalar_one_or_none() is None


async def test_subject_filter_isolation(async_client: AsyncClient, student_user, test_subject):
    """TC-35: Subject-based filter isolates matching notes"""
    from app.models.subject import Subject
    from tests.test_helpers import TestSessionLocal

    # Create a second subject in its own session
    async with TestSessionLocal() as session:
        other_sub = Subject(
            program_id=test_subject.program_id,
            name=f"Other {str(uuid.uuid4())[:6]}",
            code=f"OS{str(uuid.uuid4())[:6]}",
            semester=2,
            credits=3,
        )
        session.add(other_sub)
        await session.flush()
        other_sub_id = other_sub.id
        await session.commit()

    await create_note_committed(test_subject.id, student_user.id, "In Filter")
    await create_note_committed(other_sub_id, student_user.id, "Out Filter")

    r = await async_client.get(f"/api/v1/notes/?subject_id={test_subject.id}")
    assert r.status_code == 200
    returned_subs = {n["subject_id"] for n in r.json()}
    assert str(other_sub_id) not in returned_subs
