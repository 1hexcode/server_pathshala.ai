"""Program model."""

import uuid

from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    college_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("colleges.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, default=4)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    total_credits: Mapped[int] = mapped_column(Integer, nullable=True)

    # Relationships
    college = relationship("College", back_populates="programs")
    subjects = relationship("Subject", back_populates="program")
    users = relationship("User", back_populates="program")
