"""Shared test helpers - available to all test modules."""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

TEST_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/patshala_test"

test_engine = create_async_engine(TEST_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
    expire_on_commit=False,
)
