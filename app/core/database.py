"""Async SQLAlchemy database setup for PostgreSQL."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Neon gives postgresql:// URLs, but asyncpg needs postgresql+asyncpg://
# Also strip params asyncpg doesn't understand: sslmode, channel_binding
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
db_url = db_url.replace("sslmode=require", "ssl=require")
db_url = db_url.replace("&channel_binding=require", "").replace("?channel_binding=require", "?")

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db():
    """Dependency that provides an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
