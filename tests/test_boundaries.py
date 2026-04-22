import pytest
import uuid
import io
from httpx import AsyncClient

# Test Cases 46-50: Frontend UI & Platform Limits


async def test_unauthenticated_redirect(async_client: AsyncClient):
    """TC-46: Verify protected API endpoints return 401 for unauthenticated access"""
    # /me is a protected API route analogous to a protected React route
    r = await async_client.get("/api/v1/users/me")
    assert r.status_code == 401

    # Dashboard data is also protected
    r2 = await async_client.get("/api/v1/users/me/dashboard")
    assert r2.status_code == 401

    # Pending notes also require authentication
    r3 = await async_client.get("/api/v1/notes/pending")
    assert r3.status_code == 401


async def test_dashboard_metrics_are_present(student_client: AsyncClient):
    """TC-47: Verify the student dashboard endpoint returns correct aggregation keys"""
    r = await student_client.get("/api/v1/users/me/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "notes_count" in data
    assert "total_downloads" in data
    assert "total_views" in data
    assert "recent_notes" in data


async def test_public_stats_endpoint(async_client: AsyncClient):
    """TC-48: Check the public statistics endpoint returns counts"""
    r = await async_client.get("/api/v1/stats/")
    assert r.status_code == 200
    data = r.json()
    # Should contain at least some stats fields
    assert isinstance(data, dict)
    # One of these keys should be present
    assert any(k in data for k in ["notes_count", "students_count", "colleges_count", "total_notes", "total_students"])


async def test_custom_404_for_unknown_note(async_client: AsyncClient):
    """TC-49: Test 404 is returned for unknown resource routes"""
    fake_id = str(uuid.uuid4())
    r = await async_client.get(f"/api/v1/notes/{fake_id}")
    assert r.status_code == 404
    data = r.json()
    assert "detail" in data


async def test_file_size_limit_enforcement(student_client: AsyncClient, test_subject):
    """TC-50: Verify the file upload endpoint blocks files exceeding the size limit"""
    # Build a fake file content just over 50MB
    oversized_content = b"A" * (51 * 1024 * 1024)
    files = {"file": ("big.pdf", io.BytesIO(oversized_content), "application/pdf")}
    data = {"title": "Oversized Upload", "subject_id": str(test_subject.id)}
    r = await student_client.post("/api/v1/notes/upload", files=files, data=data)
    assert r.status_code == 400
    assert "50MB" in r.json()["detail"] or "limit" in r.json()["detail"].lower()
