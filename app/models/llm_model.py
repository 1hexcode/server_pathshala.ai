"""LLM Model configuration — stores available AI models for chat/summarization."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LLMModel(Base):
    """An AI model configuration that super admins can manage."""

    __tablename__ = "llm_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "groq" or "openrouter"
    model_id: Mapped[str] = mapped_column(
        String(200), nullable=False
    )  # e.g. "llama-3.1-8b-instant"
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )  # human-friendly label
    api_key: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # platform API key
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(
        Integer, default=0
    )  # lower = higher priority
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
