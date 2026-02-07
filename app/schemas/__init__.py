"""Pydantic schemas for request/response validation."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    role: str = "student"
    college_id: Optional[UUID] = None
    program_id: Optional[UUID] = None
    year: Optional[int] = None
    semester: Optional[int] = None


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool = True
    college_id: Optional[UUID] = None
    program_id: Optional[UUID] = None
    year: Optional[int] = None
    semester: Optional[int] = None
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


# Resolve forward reference
TokenResponse.model_rebuild()


# ─── College ─────────────────────────────────────────────────────────────────

class CollegeCreate(BaseModel):
    name: str
    short_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_favourite: bool = False


class CollegeResponse(BaseModel):
    id: UUID
    name: str
    short_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_favourite: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Program ─────────────────────────────────────────────────────────────────

class ProgramCreate(BaseModel):
    college_id: UUID
    name: str
    short_name: str
    duration: int = 4
    description: Optional[str] = None
    total_credits: Optional[int] = None


class ProgramResponse(BaseModel):
    id: UUID
    college_id: UUID
    name: str
    short_name: str
    duration: int
    description: Optional[str] = None
    total_credits: Optional[int] = None

    class Config:
        from_attributes = True


# ─── Subject ─────────────────────────────────────────────────────────────────

class SubjectCreate(BaseModel):
    program_id: UUID
    semester: int
    name: str
    code: str
    credits: int = 3
    description: Optional[str] = None


class SubjectResponse(BaseModel):
    id: UUID
    program_id: UUID
    semester: int
    name: str
    code: str
    credits: int
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Note ────────────────────────────────────────────────────────────────────

class NoteResponse(BaseModel):
    id: UUID
    user_id: UUID
    subject_id: UUID
    title: str
    description: Optional[str] = None
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    status: str
    downloads: int
    views: int
    tags: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Stats ───────────────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    notes_count: int
    students_count: int
    subjects_count: int
    ai_responses_count: int
