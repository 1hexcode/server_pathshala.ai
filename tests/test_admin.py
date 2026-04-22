import pytest
import uuid
from httpx import AsyncClient

# Test Cases 11-20: Admin Panel (Colleges, Programs, Subjects)


async def test_add_new_college(super_admin_client: AsyncClient):
    """TC-11: Test admin's ability to add a new college to the system"""
    uid = str(uuid.uuid4())[:8]
    payload = {"name": f"Test College {uid}", "short_name": f"TC{uid}"}
    response = await super_admin_client.post("/api/v1/admin/colleges", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == f"Test College {uid}"
    assert "id" in data


async def test_duplicate_college_rejection(super_admin_client: AsyncClient):
    """TC-12: Ensure the system rejects creation of a college with a duplicate name"""
    uid = str(uuid.uuid4())[:8]
    payload = {"name": f"Duplicate College {uid}", "short_name": f"DC{uid}"}
    # First creation
    r1 = await super_admin_client.post("/api/v1/admin/colleges", json=payload)
    assert r1.status_code == 200
    # Second creation (duplicate)
    r2 = await super_admin_client.post("/api/v1/admin/colleges", json=payload)
    assert r2.status_code in (400, 409)


async def test_college_deletion_cascade(super_admin_client: AsyncClient):
    """TC-13: Verify super admin can delete a college"""
    uid = str(uuid.uuid4())[:8]
    # Create college
    r = await super_admin_client.post("/api/v1/admin/colleges", json={"name": f"Delete College {uid}", "short_name": f"DL{uid}"})
    assert r.status_code == 200
    college_id = r.json()["id"]
    # Delete college
    d = await super_admin_client.delete(f"/api/v1/admin/colleges/{college_id}")
    assert d.status_code == 200
    # Verify it's gone
    g = await super_admin_client.get(f"/api/v1/admin/colleges/{college_id}")
    assert g.status_code == 404


async def test_college_favourite_toggle(super_admin_client: AsyncClient, test_college):
    """TC-14: Test toggling of favourite/featured status for colleges"""
    college_id = str(test_college.id)
    original_fav = test_college.is_favourite

    r = await super_admin_client.patch(f"/api/v1/admin/colleges/{college_id}/toggle-favourite")
    assert r.status_code == 200
    assert r.json()["is_favourite"] != original_fav


async def test_program_creation(super_admin_client: AsyncClient, test_college):
    """TC-15: Verify admins can create academic programs assigned to a specific college"""
    uid = str(uuid.uuid4())[:8]
    payload = {
        "college_id": str(test_college.id),
        "name": f"Test Program {uid}",
        "short_name": f"TP{uid}",
        "duration": 4,
        "total_credits": 120
    }
    response = await super_admin_client.post("/api/v1/admin/programs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["college_id"] == str(test_college.id)
    assert data["name"] == f"Test Program {uid}"


async def test_parameterized_program_listing(super_admin_client: AsyncClient, test_college, test_program):
    """TC-16: Ensure public API can list programs filtered by college ID"""
    response = await super_admin_client.get(f"/api/v1/admin/programs?college_id={test_college.id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(p["college_id"] == str(test_college.id) for p in data)


async def test_subject_creation(super_admin_client: AsyncClient, test_program):
    """TC-17: Test creation of subjects mapped to specific programs and semesters"""
    uid = str(uuid.uuid4())[:8]
    payload = {
        "program_id": str(test_program.id),
        "name": f"Subject {uid}",
        "code": f"SB{uid[:6]}",
        "semester": 1,
        "credits": 3
    }
    response = await super_admin_client.post("/api/v1/admin/subjects", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["program_id"] == str(test_program.id)
    assert data["semester"] == 1


async def test_subject_fetch_scoping(super_admin_client: AsyncClient, test_program, test_subject):
    """TC-18: Check subject filtering by program ID and semester"""
    response = await super_admin_client.get(
        f"/api/v1/admin/subjects?program_id={test_program.id}&semester={test_subject.semester}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(s["program_id"] == str(test_program.id) for s in data)
    assert all(s["semester"] == test_subject.semester for s in data)


async def test_subject_update(super_admin_client: AsyncClient, test_subject):
    """TC-19: Verify admin can update existing subject metadata"""
    subject_id = str(test_subject.id)
    resp = await super_admin_client.put(f"/api/v1/admin/subjects/{subject_id}", json={
        "name": "Updated Subject Name",
        "code": test_subject.code,
        "semester": test_subject.semester,
        "credits": 4
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Subject Name"
    assert resp.json()["credits"] == 4


async def test_missing_program_constraint(super_admin_client: AsyncClient):
    """TC-20: Test database constraint for assigning subject to a non-existent program"""
    fake_program_id = str(uuid.uuid4())
    payload = {
        "program_id": fake_program_id,
        "name": "Ghost Subject",
        "code": "GH101",
        "semester": 1,
        "credits": 3
    }
    response = await super_admin_client.post("/api/v1/admin/subjects", json=payload)
    assert response.status_code in (400, 404, 422)
