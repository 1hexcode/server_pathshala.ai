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
from app.schemas import NoteResponse
from app.services.storage_service import storage_service
from app.core.config import settings

router = APIRouter()


# ─── Content-type mapping ────────────────────────────────────────────────────
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
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
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload a note file (admin+ only)."""
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

    # Create note record
    note = Note(
        user_id=current_user.id,
        subject_id=subject_id,
        title=title,
        description=description or None,
        file_url=file_url,
        file_size=len(content),
        status="ready",
        tags=tag_list,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)

    logger.info(
        f"Note uploaded by {current_user.email}: {title} "
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
    query = select(Note).where(Note.status == "ready")
    if subject_id:
        query = query.where(Note.subject_id == subject_id)
    query = query.order_by(Note.created_at.desc())
    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single note by ID (public). Increments view count."""
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Increment view count
    note.views = (note.views or 0) + 1

    return note


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a note (super_admin only)."""
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

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
