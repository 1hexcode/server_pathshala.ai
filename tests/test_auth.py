import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.user import User

# Test Cases 1-10: Authentication & User Management


async def test_protected_route_access(async_client: AsyncClient):
    """TC-1: Verify non-registered user cannot access protected routes"""
    response = await async_client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_valid_student_registration(async_client: AsyncClient, test_college, test_program):
    """TC-2: Ensure self-registration works with valid data"""
    import uuid
    email = f"newstudent_{str(uuid.uuid4())[:8]}@test.com"
    payload = {
        "email": email,
        "password": "SecurePassword123",
        "name": "New Student",
        "college_id": str(test_college.id),
        "program_id": str(test_program.id),
        "year": 1,
        "semester": 1
    }
    response = await async_client.post("/api/v1/users/register", json=payload)
    assert response.status_code == 200  # endpoint returns 200 with TokenResponse
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == email
    assert "password" not in data["user"]


async def test_registration_login_flow(async_client: AsyncClient, test_college, test_program):
    """TC-3: Test correct login flow after registration"""
    import uuid
    unique = str(uuid.uuid4())[:8]
    email = f"loginflow_{unique}@test.com"
    # Register
    await async_client.post("/api/v1/users/register", json={
        "email": email,
        "password": "SecurePassword123",
        "name": "Login Flow",
        "college_id": str(test_college.id),
        "program_id": str(test_program.id),
        "year": 1,
        "semester": 1
    })
    # Login
    resp = await async_client.post("/api/v1/users/login", json={"email": email, "password": "SecurePassword123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_persistent_jwt_validation(student_client: AsyncClient, student_user):
    """TC-4: Validate persistent session via JWT token"""
    response = await student_client.get("/api/v1/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == student_user.email
    assert data["role"] == "student"


async def test_admin_account_creation(super_admin_client: AsyncClient, test_college):
    """TC-5: Check that super admins can successfully create new admin accounts"""
    import uuid
    email = f"newadmin_{str(uuid.uuid4())[:8]}@test.com"
    payload = {
        "email": email,
        "password": "AdminPassword123",
        "name": "New Admin",
        "role": "admin",
        "college_id": str(test_college.id)
    }
    response = await super_admin_client.post("/api/v1/users/create-admin", json=payload)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert response.json()["college_id"] == str(test_college.id)


async def test_super_admin_creation(super_admin_client: AsyncClient):
    """TC-6: Ensure super admins can create new super admin accounts"""
    import uuid
    email = f"newsuper_{str(uuid.uuid4())[:8]}@test.com"
    payload = {
        "email": email,
        "password": "SuperPassword123",
        "name": "New Super Admin",
        "role": "super_admin"
    }
    response = await super_admin_client.post("/api/v1/users/create-admin", json=payload)
    assert response.status_code == 200
    assert response.json()["role"] == "super_admin"
    assert response.json().get("college_id") is None


async def test_disable_user_account(super_admin_client: AsyncClient, admin_user, db_session):
    """TC-7: Confirm super admins can disable an active admin user account"""
    target_id = str(admin_user.id)
    response = await super_admin_client.patch(f"/api/v1/users/{target_id}/toggle-active")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_disabled_user_login_block(async_client: AsyncClient, super_admin_client: AsyncClient, admin_user):
    """TC-8: Verify a disabled user is rejected on login"""
    # Disable the admin via the API (clean approach, no direct session commit conflicts)
    target_id = str(admin_user.id)
    disable_resp = await super_admin_client.patch(f"/api/v1/users/{target_id}/toggle-active")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["is_active"] is False

    login_payload = {"email": admin_user.email, "password": "password123"}
    resp = await async_client.post("/api/v1/users/login", json=login_payload)
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"]


async def test_personal_profile_endpoint(student_client: AsyncClient, student_user):
    """TC-9: Check student access to their personal profile via /me"""
    response = await student_client.get("/api/v1/users/me")
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "student"
    assert data["id"] == str(student_user.id)
    assert data["email"] == student_user.email


async def test_admin_user_filtering(super_admin_client: AsyncClient, admin_user, student_user):
    """TC-10: Ensure admins can view the user listing and apply role filters"""
    r_students = await super_admin_client.get("/api/v1/users/?role=student")
    assert r_students.status_code == 200
    roles = [u["role"] for u in r_students.json()]
    assert all(r == "student" for r in roles)

    r_admins = await super_admin_client.get("/api/v1/users/?role=admin")
    assert r_admins.status_code == 200
    roles = [u["role"] for u in r_admins.json()]
    assert all(r == "admin" for r in roles)
