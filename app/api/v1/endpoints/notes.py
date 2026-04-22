"""Note management endpoints (upload, list, get, delete)."""

import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.logging import logger
from app.dependencies import get_current_user, require_admin, require_super_admin
from app.models.user import User
from app.models.note import Note
from app.models.subject import Subject
from app.models.program import Program
from app.models.college import College
from app.models.note_feedback import NoteFeedback
from app.schemas import NoteResponse, NoteRejectRequest
from app.services.storage_service import storage_service
from app.services.ocr_service import ocr_service
from app.core.config import settings

router = APIRouter()


# ─── Content-type mapping ────────────────────────────────────────────────────
MIME_TYPES = {
    ".pdf": "application/pdf",
}


def _sanitize(name: str) -> str:
    """Sanitize a name for use in a storage path (remove spaces and special chars)."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")


async def _build_storage_path(db: AsyncSession, subject: Subject) -> str:
    """
    Build a hierarchical storage path: {college_short}/{program_short}/{subject_code}/
    This maps directly to Supabase Storage object paths.
    """
    # Load program → college chain
    prog_result = await db.execute(
        select(Program).where(Program.id == subject.program_id)
    )
    program = prog_result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=500, detail="Subject's program not found")

    college_result = await db.execute(
        select(College).where(College.id == program.college_id)
    )
    college = college_result.scalar_one_or_none()
    if not college:
        raise HTTPException(status_code=500, detail="Program's college not found")

    college_dir = _sanitize(college.short_name)
    program_dir = _sanitize(program.short_name)
    subject_dir = _sanitize(subject.code)

    return f"{college_dir}/{program_dir}/{subject_dir}"


@router.post("/upload", response_model=NoteResponse)
async def upload_note(
    file: UploadFile = File(...),
    title: str = Form(...),
    subject_id: str = Form(...),
    description: str = Form(None),
    tags: str = Form(None),
    is_handwritten: str = Form("false"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a note file (any authenticated user). Note goes to 'pending' until published by super admin."""
    handwritten = is_handwritten.lower() in ("true", "1", "yes")

    # Validate file type
    allowed_types = list(MIME_TYPES.keys())
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: {', '.join(allowed_types)}",
        )

    # Validate subject exists
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Max 50MB
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

    # Build hierarchical path: {college}/{program}/{subject_code}/
    rel_dir = await _build_storage_path(db, subject)

    # Upload to Supabase Storage
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}{ext}"
    storage_path = f"{rel_dir}/{safe_filename}"

    try:
        file_url = await storage_service.upload(
            storage_path, content, MIME_TYPES.get(ext, "application/octet-stream")
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    # Parse tags
    tag_list = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Run OCR for handwritten notes
    extracted_text = None
    if handwritten:
        try:
            logger.info(f"Running OCR on handwritten note: {title}")
            extracted_text = ocr_service.ocr_pdf(content)
            if not extracted_text.strip():
                logger.warning(f"OCR produced no text for: {title}")
                extracted_text = None
        except Exception as e:
            logger.error(f"OCR failed for '{title}': {e}")
            # Continue upload even if OCR fails — text will be missing
            extracted_text = None

    # Create note record
    note = Note(
        user_id=current_user.id,
        subject_id=subject_id,
        title=title,
        description=description or None,
        file_url=file_url,
        file_size=len(content),
        status="pending",
        tags=tag_list,
        is_handwritten=handwritten,
        extracted_text=extracted_text,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)

    logger.info(
        f"Note uploaded (pending review) by {current_user.email}: {title} "
        f"({len(content)} bytes) → {file_url}"
    )
    return note


@router.get("/", response_model=List[NoteResponse])
async def list_notes(
    subject_id: Optional[str] = None,
    limit: int = Query(None, ge=1, le=100, description="Max notes to return"),
    db: AsyncSession = Depends(get_db),
):
    """List all notes, optionally filtered by subject (public)."""
    query = select(Note).options(selectinload(Note.feedback)).where(Note.status == "ready")
    if subject_id:
        query = query.where(Note.subject_id == subject_id)
    query = query.order_by(Note.created_at.desc())
    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/pending", response_model=List[NoteResponse])
async def list_pending_notes(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all notes waiting for review. Admins only see notes for their college."""
    query = select(Note).options(selectinload(Note.feedback)).where(Note.status == "pending")

    if current_user.role == "admin":
        if current_user.college_id is None:
            return []
        query = query.join(Subject, Note.subject_id == Subject.id)\
                     .join(Program, Subject.program_id == Program.id)\
                     .where(Program.college_id == current_user.college_id)
                     
    query = query.order_by(Note.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single note by ID (public). Increments view count."""
    result = await db.execute(select(Note).options(selectinload(Note.feedback)).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Increment view count and persist immediately
    note.views = (note.views or 0) + 1
    await db.commit()
    await db.refresh(note)

    return note


@router.post("/{note_id}/download", response_model=NoteResponse)
async def track_download(
    note_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Increment download counter for a note (public). Call when a user downloads the file."""
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note.downloads = (note.downloads or 0) + 1
    await db.commit()
    await db.refresh(note)

    return note


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a note. Admins can only delete notes in their college."""
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if current_user.role == "admin":
        prog_result = await db.execute(select(Program).join(Subject).where(Subject.id == note.subject_id))
        program = prog_result.scalar_one_or_none()
        if current_user.college_id is None or (program and program.college_id != current_user.college_id):
            raise HTTPException(status_code=403, detail="You can only manage notes from your own college.")

    # Delete file from storage
    if note.file_url:
        try:
            storage_path = storage_service.extract_storage_path(note.file_url)
            await storage_service.delete(storage_path)
        except Exception as e:
            logger.warning(f"Failed to delete file from storage: {e}")

    await db.delete(note)
    logger.info(f"Note deleted by {current_user.email}: {note.title}")
    return {"message": f"Note '{note.title}' deleted"}


@router.post("/{note_id}/reprocess-ocr", response_model=NoteResponse)
async def reprocess_ocr(
    note_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Re-run OCR on a handwritten note (admin+ only). Use when OCR failed during upload."""
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if not note.is_handwritten:
        raise HTTPException(status_code=400, detail="This note is not marked as handwritten")

    if not note.file_url:
        raise HTTPException(status_code=400, detail="This note has no uploaded file")

    try:
        # Download PDF from storage
        storage_path = storage_service.extract_storage_path(note.file_url)
        content = await storage_service.download(storage_path)

        logger.info(f"Re-processing OCR for: {note.title}")
        extracted_text = ocr_service.ocr_pdf(content)

        if not extracted_text.strip():
            raise HTTPException(
                status_code=500,
                detail="OCR produced no text. The service may still be unavailable.",
            )

        note.extracted_text = extracted_text
        logger.info(f"OCR reprocess complete for '{note.title}': {len(extracted_text)} chars")
        return note

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR reprocess failed for '{note.title}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OCR reprocessing failed: {e}. The DeepSeek OCR service may be temporarily unavailable.",
        )





@router.patch("/{note_id}/publish", response_model=NoteResponse)
async def publish_note(
    note_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Publish a pending note. Admins can only publish notes in their college."""
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if current_user.role == "admin":
        prog_result = await db.execute(select(Program).join(Subject).where(Subject.id == note.subject_id))
        program = prog_result.scalar_one_or_none()
        if current_user.college_id is None or (program and program.college_id != current_user.college_id):
            raise HTTPException(status_code=403, detail="You can only manage notes from your own college.")

    note.status = "ready"
    logger.info(f"Note published by {current_user.email}: {note.title}")
    return note


@router.patch("/{note_id}/reject", response_model=NoteResponse)
async def reject_note(
    note_id: str,
    payload: NoteRejectRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending note with feedback. Admins can only reject notes in their college."""
    result = await db.execute(select(Note).options(selectinload(Note.feedback)).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if current_user.role == "admin":
        prog_result = await db.execute(select(Program).join(Subject).where(Subject.id == note.subject_id))
        program = prog_result.scalar_one_or_none()
        if current_user.college_id is None or (program and program.college_id != current_user.college_id):
            raise HTTPException(status_code=403, detail="You can only manage notes from your own college.")

    note.status = "failed"
    
    # Store feedback
    feedback = NoteFeedback(
        note_id=note.id,
        admin_id=current_user.id,
        feedback_text=payload.feedback_text
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(note, attribute_names=["feedback"])
    
    logger.info(f"Note rejected by {current_user.email}: {note.title}")
    return note

