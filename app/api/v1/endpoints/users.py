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
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse

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


@router.post("/create-admin", response_model=UserResponse)
async def create_admin(
    data: UserCreate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create an admin user (super_admin only)."""
    if data.role not in ("admin", "super_admin"):
        raise HTTPException(
            status_code=400,
            detail="This endpoint is for creating admin or super_admin users",
        )

    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(f"Admin created by {current_user.email}: {user.email} ({user.role})")
    return user


@router.patch("/{user_id}/toggle-active", response_model=UserResponse)
async def toggle_user_active(
    user_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable an admin user (super_admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()

    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.role == "super_admin":
        raise HTTPException(status_code=403, detail="Cannot disable a super admin")

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")

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
    """List all users (admin+ only)."""
    query = select(User)
    if role:
        query = query.where(User.role == role)
    query = query.order_by(User.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()
