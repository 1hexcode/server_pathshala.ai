import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from urllib.parse import urlparse
import os
import uuid

from app.main import app
from app.core.database import get_db
from app.dependencies import hash_password
from app.models.user import User
from app.models.college import College
from app.models.program import Program
from app.models.subject import Subject

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/patshala"
)
parsed = urlparse(DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))
DB_USER = parsed.username or "postgres"
DB_PASS = parsed.password or "postgres"
DB_HOST = parsed.hostname or "localhost"
DB_PORT = parsed.port or 5432
TEST_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/patshala_test"

from sqlalchemy.pool import NullPool
from tests.test_helpers import TestSessionLocal, TEST_URL, test_engine

# Use standard FastAPI dependency injection returning fresh sessions
async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides a direct session hook for test arrangements — separate from app's get_db."""
    async with TestSessionLocal() as session:
        yield session
        # Session commits happen inside tests; we close cleanly

@pytest_asyncio.fixture(scope="function")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# Random UUIDs in names to avoid UniqueConstraint errors across tests
@pytest_asyncio.fixture(scope="function")
async def test_college(db_session):
    uid = str(uuid.uuid4())[:8]
    college = College(name=f"College {uid}", short_name=f"TC{uid}")
    db_session.add(college)
    await db_session.commit()
    await db_session.refresh(college)
    return college

@pytest_asyncio.fixture(scope="function")
async def test_program(db_session, test_college):
    uid = str(uuid.uuid4())[:8]
    program = Program(
        college_id=test_college.id, 
        name=f"Program {uid}", 
        short_name=f"TP{uid}", 
        duration=4, 
        total_credits=120
    )
    db_session.add(program)
    await db_session.commit()
    await db_session.refresh(program)
    return program

@pytest_asyncio.fixture(scope="function")
async def test_subject(db_session, test_program):
    uid = str(uuid.uuid4())[:8]
    subject = Subject(
        program_id=test_program.id,
        name=f"Subject {uid}",
        code=f"TS{uid}",
        semester=1,
        credits=3
    )
    db_session.add(subject)
    await db_session.commit()
    await db_session.refresh(subject)
    return subject

@pytest_asyncio.fixture(scope="function")
async def super_admin_user(db_session):
    uid = str(uuid.uuid4())[:8]
    email = f"superadmin_{uid}@test.com"
    pwd = "password123"
    user = User(
        email=email,
        password_hash=hash_password(pwd),
        name="Super Admin",
        role="super_admin",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user.test_pwd = pwd # Attach for login
    return user

@pytest_asyncio.fixture(scope="function")
async def super_admin_client(super_admin_user):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/users/login", json={"email": super_admin_user.email, "password": super_admin_user.test_pwd})
        token = resp.json()["access_token"]
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac

@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session, test_college):
    uid = str(uuid.uuid4())[:8]
    email = f"admin_{uid}@test.com"
    pwd = "password123"
    user = User(
        email=email,
        password_hash=hash_password(pwd),
        name="Admin Test",
        role="admin",
        college_id=test_college.id,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user.test_pwd = pwd
    return user

@pytest_asyncio.fixture(scope="function")
async def admin_client(admin_user):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/users/login", json={"email": admin_user.email, "password": admin_user.test_pwd})
        token = resp.json()["access_token"]
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac

@pytest_asyncio.fixture(scope="function")
async def student_user(db_session, test_program):
    uid = str(uuid.uuid4())[:8]
    email = f"student_{uid}@test.com"
    pwd = "password123"
    user = User(
        email=email,
        password_hash=hash_password(pwd),
        name="Student Test",
        role="student",
        program_id=test_program.id,
        year=1,
        semester=1,
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user.test_pwd = pwd
    return user

@pytest_asyncio.fixture(scope="function")
async def student_client(student_user):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/users/login", json={"email": student_user.email, "password": student_user.test_pwd})
        token = resp.json()["access_token"]
        ac.headers.update({"Authorization": f"Bearer {token}"})
        yield ac


@pytest_asyncio.fixture(scope="function")
async def test_note(db_session, student_user, test_subject):
    """A ready-status note owned by student_user for use in tests."""
    from app.models.note import Note
    note = Note(
        user_id=student_user.id,
        subject_id=test_subject.id,
        title="Fixture Test Note",
        file_url="http://storage.test/fixture.pdf",
        file_size=512,
        status="ready",
        extracted_text="Sample extracted text for testing.",
        views=0,
    )
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    return note
