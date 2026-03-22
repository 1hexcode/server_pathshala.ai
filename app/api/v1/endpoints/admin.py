"""Admin endpoints for managing colleges, programs, subjects, and students."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import logger
from app.dependencies import require_admin, require_super_admin, hash_password
from app.models.user import User
from app.models.college import College
from app.models.program import Program
from app.models.subject import Subject
from app.schemas import (
    CollegeCreate, CollegeResponse,
    ProgramCreate, ProgramResponse,
    SubjectCreate, SubjectResponse,
    StudentCreate, UserResponse,
)

router = APIRouter()


# ─── Colleges ────────────────────────────────────────────────────────────────

@router.post("/colleges", response_model=CollegeResponse)
async def create_college(
    data: CollegeCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new college. Regular admins can only create one college ever."""
    # Enforce one-college-per-admin (super_admin is exempt)
    if current_user.role == "admin" and current_user.college_id is not None:
        raise HTTPException(
            status_code=409,
            detail="You have already registered a college. An admin account can only manage one college.",
        )

    existing = await db.execute(select(College).where(College.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A college with this name already exists.")

    college = College(**data.model_dump())
    db.add(college)
    await db.flush()
    await db.refresh(college)

    # Link the admin to their newly created college
    if current_user.role == "admin":
        current_user.college_id = college.id
        await db.flush()

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
        raise HTTPException(status_code=404, detail="College not found.")
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
        raise HTTPException(status_code=404, detail="College not found.")

    # Regular admins can only toggle their own college
    if current_user.role == "admin" and current_user.college_id != college_id:
        raise HTTPException(
            status_code=403,
            detail="You can only manage your own college.",
        )

    college.is_favourite = not college.is_favourite
    await db.flush()
    await db.refresh(college)

    status = "favourited" if college.is_favourite else "unfavourited"
    logger.info(f"College {status} by {current_user.email}: {college.name}")
    return college


@router.delete("/colleges/{college_id}")
async def delete_college(
    college_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a college (super admin only)."""
    result = await db.execute(select(College).where(College.id == college_id))
    college = result.scalar_one_or_none()
    if not college:
        raise HTTPException(status_code=404, detail="College not found.")

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
    """Create a new program under a college. Admins can only add to their own college."""
    # Enforce scoping: admins can only add programs to their own college
    if current_user.role == "admin":
        if current_user.college_id is None:
            raise HTTPException(
                status_code=403,
                detail="You must create your college before adding programs.",
            )
        if data.college_id != current_user.college_id:
            raise HTTPException(
                status_code=403,
                detail="You can only add programs to your own college.",
            )

    # Verify college exists
    college = await db.execute(select(College).where(College.id == data.college_id))
    if not college.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="College not found.")

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
        raise HTTPException(status_code=404, detail="Program not found.")
    return program


@router.delete("/programs/{program_id}")
async def delete_program(
    program_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a program (super admin only)."""
    result = await db.execute(select(Program).where(Program.id == program_id))
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found.")

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
    """Create a new subject under a program. Admins can only add subjects to their own college's programs."""
    # Verify program exists
    prog_result = await db.execute(select(Program).where(Program.id == data.program_id))
    program = prog_result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found.")

    # Enforce scoping: admins can only add subjects to programs in their own college
    if current_user.role == "admin":
        if current_user.college_id is None:
            raise HTTPException(
                status_code=403,
                detail="You must create your college before adding subjects.",
            )
        if program.college_id != current_user.college_id:
            raise HTTPException(
                status_code=403,
                detail="You can only add subjects to programs in your own college.",
            )

    # Check duplicate code
    existing = await db.execute(select(Subject).where(Subject.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Subject code '{data.code}' already exists.")

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
        raise HTTPException(status_code=404, detail="Subject not found.")
    return subject


@router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a subject (super admin only)."""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

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


# ─── Students (Admin-created) ────────────────────────────────────────────────

@router.post("/create-student", response_model=UserResponse)
async def create_student(
    data: StudentCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a student account (admin only). Student is auto-linked to the admin's college."""
    if current_user.role == "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Super admins should use the /users/create-admin endpoint. Use 'Create Admin' flow.",
        )

    if current_user.college_id is None:
        raise HTTPException(
            status_code=403,
            detail="You must create your college before adding students.",
        )

    # Validate program belongs to admin's college (if provided)
    if data.program_id is not None:
        prog_result = await db.execute(select(Program).where(Program.id == data.program_id))
        program = prog_result.scalar_one_or_none()
        if not program:
            raise HTTPException(status_code=404, detail="Program not found.")
        if program.college_id != current_user.college_id:
            raise HTTPException(
                status_code=403,
                detail="The selected program does not belong to your college.",
            )

    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A user with this email is already registered.")

    student = User(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        role="student",
        college_id=current_user.college_id,
        program_id=data.program_id,
        year=data.year,
        semester=data.semester,
    )
    db.add(student)
    await db.flush()
    await db.refresh(student)

    logger.info(f"Student created by {current_user.email}: {student.email}")
    return student


@router.get("/students", response_model=List[UserResponse])
async def list_students(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List students. Admins see only their college's students; super_admin sees all."""
    query = select(User).where(User.role == "student")

    if current_user.role == "admin":
        if current_user.college_id is None:
            return []
        query = query.where(User.college_id == current_user.college_id)

    query = query.order_by(User.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/students/{user_id}/toggle-active", response_model=UserResponse)
async def toggle_student_active(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a student. Admins can only manage students in their own college."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if target.role != "student":
        raise HTTPException(
            status_code=403,
            detail="This endpoint only manages student accounts. Use the Admins tab for admin accounts.",
        )

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot disable your own account.")

    # Scope check: admins can only manage their own college's students
    if current_user.role == "admin":
        if current_user.college_id is None or target.college_id != current_user.college_id:
            raise HTTPException(
                status_code=403,
                detail="You can only manage students from your own college.",
            )

    target.is_active = not target.is_active
    await db.flush()
    await db.refresh(target)

    status = "enabled" if target.is_active else "disabled"
    logger.info(f"Student {status} by {current_user.email}: {target.email}")
    return target
