"""Public stats endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.note import Note
from app.models.user import User
from app.models.subject import Subject
from app.models.ai_chat_log import AIChatLog
from app.schemas import StatsResponse

router = APIRouter()


@router.get("/", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get platform statistics (public)."""
    notes_result = await db.execute(
        select(func.count()).select_from(Note).where(Note.status == "ready")
    )
    students_result = await db.execute(
        select(func.count()).select_from(User).where(User.role == "student")
    )
    subjects_result = await db.execute(
        select(func.count()).select_from(Subject)
    )
    ai_result = await db.execute(
        select(func.count()).select_from(AIChatLog)
    )

    return StatsResponse(
        notes_count=notes_result.scalar() or 0,
        students_count=students_result.scalar() or 0,
        subjects_count=subjects_result.scalar() or 0,
        ai_responses_count=ai_result.scalar() or 0,
    )
