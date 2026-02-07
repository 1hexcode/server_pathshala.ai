"""Admin endpoints for managing colleges, programs, and subjects."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import logger
from app.dependencies import require_admin
from app.models.user import User
from app.models.college import College
from app.models.program import Program
from app.models.subject import Subject
from app.schemas import (
    CollegeCreate, CollegeResponse,
    ProgramCreate, ProgramResponse,
    SubjectCreate, SubjectResponse,
)

router = APIRouter()


# ─── Colleges ────────────────────────────────────────────────────────────────

@router.post("/colleges", response_model=CollegeResponse)
async def create_college(
    data: CollegeCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new college (admin+ only)."""
    existing = await db.execute(select(College).where(College.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="College already exists")

    college = College(**data.model_dump())
    db.add(college)
    await db.flush()
    await db.refresh(college)

    logger.info(f"College created by {current_user.email}: {college.name}")
    return college


@router.get("/colleges", response_model=List[CollegeResponse])
async def list_colleges(
    favourite: bool = Query(None, description="Filter favourite colleges only"),
    db: AsyncSession = Depends(get_db),
):
    """List all colleges (public). Use ?favourite=true for featured colleges."""
    query = select(College)
    if favourite is not None:
        query = query.where(College.is_favourite == favourite)
    query = query.order_by(College.name)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/colleges/{college_id}", response_model=CollegeResponse)
async def get_college(college_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a college by ID (public)."""
    result = await db.execute(select(College).where(College.id == college_id))
    college = result.scalar_one_or_none()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")
    return college


@router.patch("/colleges/{college_id}/toggle-favourite", response_model=CollegeResponse)
async def toggle_college_favourite(
    college_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Toggle favourite status of a college (admin+ only)."""
    result = await db.execute(select(College).where(College.id == college_id))
    college = result.scalar_one_or_none()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")

    college.is_favourite = not college.is_favourite
    await db.flush()
    await db.refresh(college)

    status = "favourited" if college.is_favourite else "unfavourited"
    logger.info(f"College {status} by {current_user.email}: {college.name}")
    return college


@router.delete("/colleges/{college_id}")
async def delete_college(
    college_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a college (admin+ only)."""
    result = await db.execute(select(College).where(College.id == college_id))
    college = result.scalar_one_or_none()
    if not college:
        raise HTTPException(status_code=404, detail="College not found")

    try:
        await db.delete(college)
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete college '{college.name}' — it has programs linked to it. Delete the programs first.",
        )

    logger.info(f"College deleted by {current_user.email}: {college.name}")
    return {"message": f"College '{college.name}' deleted"}


# ─── Programs ────────────────────────────────────────────────────────────────

@router.post("/programs", response_model=ProgramResponse)
async def create_program(
    data: ProgramCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new program under a college (admin+ only)."""
    # Verify college exists
    college = await db.execute(select(College).where(College.id == data.college_id))
    if not college.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="College not found")

    program = Program(**data.model_dump())
    db.add(program)
    await db.flush()
    await db.refresh(program)

    logger.info(f"Program created by {current_user.email}: {program.name}")
    return program


@router.get("/programs", response_model=List[ProgramResponse])
async def list_programs(
    college_id: UUID = None,
    db: AsyncSession = Depends(get_db),
):
    """List programs, optionally filtered by college (public)."""
    query = select(Program)
    if college_id:
        query = query.where(Program.college_id == college_id)
    query = query.order_by(Program.name)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/programs/{program_id}", response_model=ProgramResponse)
async def get_program(program_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a program by ID (public)."""
    result = await db.execute(select(Program).where(Program.id == program_id))
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


@router.delete("/programs/{program_id}")
async def delete_program(
    program_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a program (admin+ only)."""
    result = await db.execute(select(Program).where(Program.id == program_id))
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    try:
        await db.delete(program)
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete program '{program.name}' — it has subjects linked to it. Delete the subjects first.",
        )

    logger.info(f"Program deleted by {current_user.email}: {program.name}")
    return {"message": f"Program '{program.name}' deleted"}


# ─── Subjects ────────────────────────────────────────────────────────────────

@router.post("/subjects", response_model=SubjectResponse)
async def create_subject(
    data: SubjectCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new subject under a program (admin+ only)."""
    # Verify program exists
    program = await db.execute(select(Program).where(Program.id == data.program_id))
    if not program.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Program not found")

    # Check duplicate code
    existing = await db.execute(select(Subject).where(Subject.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Subject code '{data.code}' already exists")

    subject = Subject(**data.model_dump())
    db.add(subject)
    await db.flush()
    await db.refresh(subject)

    logger.info(f"Subject created by {current_user.email}: {subject.code} - {subject.name}")
    return subject


@router.get("/subjects", response_model=List[SubjectResponse])
async def list_subjects(
    program_id: UUID = None,
    semester: int = None,
    db: AsyncSession = Depends(get_db),
):
    """List subjects, optionally filtered by program and/or semester (public)."""
    query = select(Subject)
    if program_id:
        query = query.where(Subject.program_id == program_id)
    if semester:
        query = query.where(Subject.semester == semester)
    query = query.order_by(Subject.code)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a subject by ID (public)."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a subject (admin+ only)."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    try:
        await db.delete(subject)
        await db.flush()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete subject '{subject.code}' — it has notes linked to it. Delete the notes first.",
        )

    logger.info(f"Subject deleted by {current_user.email}: {subject.code}")
    return {"message": f"Subject '{subject.code}' deleted"}

