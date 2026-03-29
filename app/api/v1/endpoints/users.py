"""User management endpoints."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import logger
from app.dependencies import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_super_admin,
    require_admin,
)
from app.models.user import User
from app.schemas import UserCreate, UserLogin, UserUpdate, UserResponse, TokenResponse, AdminCreate

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new student account (public). Returns JWT token."""
    if data.role != "student":
        raise HTTPException(
            status_code=403,
            detail="Only student accounts can self-register",
        )

    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        role="student",
        college_id=data.college_id,
        program_id=data.program_id,
        year=data.year,
        semester=data.semester,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(str(user.id), user.role)
    logger.info(f"New student registered: {user.email}")

    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login_user(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Login and receive a JWT token."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been disabled")

    user.last_login = datetime.utcnow()
    await db.flush()

    token = create_access_token(str(user.id), user.role)
    logger.info(f"User logged in: {user.email}")

    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile (requires token)."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's name and/or password."""
    if data.name is not None:
        current_user.name = data.name.strip()

    if data.new_password is not None:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="Current password is required to set a new password")
        if not verify_password(data.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if len(data.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        current_user.password_hash = hash_password(data.new_password)

    await db.commit()
    await db.refresh(current_user)
    logger.info(f"Profile updated for: {current_user.email}")
    return current_user


@router.get("/me/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard data for the current user."""
    from sqlalchemy import func
    from app.models.note import Note
    from app.schemas import NoteResponse

    # User's notes
    notes_result = await db.execute(
        select(Note)
        .where(Note.user_id == current_user.id)
        .order_by(Note.created_at.desc())
    )
    notes = notes_result.scalars().all()

    # Aggregates
    total_downloads = sum(n.downloads for n in notes)
    total_views = sum(n.views for n in notes)

    # College / program names
    college_name = None
    program_name = None
    if current_user.college_id:
        from app.models.college import College
        col = await db.execute(select(College).where(College.id == current_user.college_id))
        college = col.scalar_one_or_none()
        college_name = college.short_name if college else None
    if current_user.program_id:
        from app.models.program import Program
        prog = await db.execute(select(Program).where(Program.id == current_user.program_id))
        program = prog.scalar_one_or_none()
        program_name = program.name if program else None

    return {
        "notes_count": len(notes),
        "total_downloads": total_downloads,
        "total_views": total_views,
        "college_name": college_name,
        "program_name": program_name,
        "semester": current_user.semester,
        "recent_notes": [NoteResponse.model_validate(n) for n in notes[:5]],
    }


@router.post("/create-admin", response_model=UserResponse)
async def create_admin(
    data: AdminCreate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create an admin user with an optional pre-assigned college (super_admin only)."""
    if data.role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=400,
            detail="This endpoint is for creating admin or super_admin users.",
        )

    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    # Validate college if provided
    college_id = None
    if data.college_id:
        from app.models.college import College
        col_result = await db.execute(select(College).where(College.id == data.college_id))
        college = col_result.scalar_one_or_none()
        if not college:
            raise HTTPException(status_code=404, detail="College not found.")
        # Ensure no other admin is already assigned to this college
        existing_admin = await db.execute(
            select(User).where(User.college_id == data.college_id, User.role == "admin")
        )
        if existing_admin.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="Another admin is already assigned to this college. Each college can only have one admin.",
            )
        college_id = data.college_id

    user = User(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        role=data.role,
        college_id=college_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    college_info = f" (college: {college_id})" if college_id else ""
    logger.info(f"Admin created by {current_user.email}: {user.email} ({user.role}){college_info}")
    return user


@router.patch("/{user_id}/toggle-active", response_model=UserResponse)
async def toggle_user_active(
    user_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable an admin user (super_admin only). For students, use /admin/students/{id}/toggle-active."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if target.role == "super_admin":
        raise HTTPException(status_code=403, detail="Cannot disable a super admin account.")

    if target.role == "student":
        raise HTTPException(
            status_code=403,
            detail="Student accounts are managed via the Students tab. Use /admin/students/{id}/toggle-active.",
        )

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot disable your own account.")

    target.is_active = not target.is_active
    await db.flush()
    await db.refresh(target)

    status = "enabled" if target.is_active else "disabled"
    logger.info(f"User {status} by {current_user.email}: {target.email}")

    return target


@router.get("/", response_model=List[UserResponse])
async def list_users(
    role: str = Query(None, description="Filter by role"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """List users. Admins see only students in their college; super_admin sees all."""
    query = select(User)
    if role:
        query = query.where(User.role == role)

    # Regular admins are scoped to their own college's users
    if current_user.role == "admin":
        query = query.where(User.college_id == current_user.college_id)

    query = query.order_by(User.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()
