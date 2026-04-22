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
    college_id: UUID
    program_id: UUID
    year: int
    semester: int


class StudentCreate(BaseModel):
    """Schema for admin-created student accounts. Role is always 'student'."""
    email: str
    name: str
    password: str
    program_id: UUID
    year: int
    semester: int


class AdminCreate(BaseModel):
    """Schema for super_admin-created admin accounts. Includes optional college pre-assignment."""
    email: str
    name: str
    password: str
    role: str = "admin"
    college_id: Optional[UUID] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


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


class CollegeUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_favourite: Optional[bool] = None


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
    total_credits: int


class ProgramUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    duration: Optional[int] = None
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


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    semester: Optional[int] = None
    credits: Optional[int] = None
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


# ─── Note Feedback ─────────────────────────────────────────────────────────────

class NoteFeedbackResponse(BaseModel):
    id: UUID
    admin_id: UUID
    feedback_text: str
    created_at: datetime

    class Config:
        from_attributes = True

class NoteRejectRequest(BaseModel):
    feedback_text: str

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
    is_handwritten: bool = False
    downloads: int
    views: int
    tags: Optional[List[str]] = None
    created_at: datetime
    feedback: Optional[NoteFeedbackResponse] = None

    class Config:
        from_attributes = True


# ─── Stats ───────────────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    notes_count: int
    students_count: int
    subjects_count: int
    colleges_count: int
    ai_responses_count: int


# ─── LLM Models ──────────────────────────────────────────────────────────────

class LLMModelCreate(BaseModel):
    platform: str  # "groq" or "openrouter"
    model_id: str
    display_name: str
    api_key: str
    is_enabled: bool = True
    priority: int = 0

class LLMModelUpdate(BaseModel):
    display_name: Optional[str] = None
    model_id: Optional[str] = None
    api_key: Optional[str] = None
    priority: Optional[int] = None

class LLMModelResponse(BaseModel):
    id: UUID
    platform: str
    model_id: str
    display_name: str
    is_enabled: bool
    priority: int
    created_at: datetime

    class Config:
        from_attributes = True

