"""User model."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Enum, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("student", "admin", "super_admin", name="user_role"),
        default="student",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    college_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("colleges.id"), nullable=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("programs.id"), nullable=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=True)
    semester: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    college = relationship("College", back_populates="users")
    program = relationship("Program", back_populates="users")
    notes = relationship("Note", back_populates="user")
    summaries = relationship("Summary", back_populates="user")
