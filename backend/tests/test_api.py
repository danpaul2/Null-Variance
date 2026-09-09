import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def get_auth_headers():
    res = client.post("/api/auth/login", json={"email": "mehta@lab.in", "password": "password123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_auth_login():
    response = client.post("/api/auth/login", json={"email": "mehta@lab.in", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "INSPECTOR"

def test_get_instruments():
    headers = get_auth_headers()
    response = client.get("/api/instruments", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5
    assert data[0]["id"] == "INST-0001"

def test_get_sessions():
    headers = get_auth_headers()
    response = client.get("/api/sessions", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 6
    assert data[0]["id"] == "TS-2026-0001"

def test_session_evaluate():
    headers = get_auth_headers()
    response = client.post("/api/sessions/TS-2026-0001/evaluate", headers=headers)
    assert response.status_code == 200
    comp = response.json()
    assert "overall" in comp
    assert comp["overall"] in ["PASS", "FAIL", "PENDING"]
    assert "eccentricity" in comp
    assert "repeatability" in comp

def test_docx_report_generation():
    headers = get_auth_headers()
    response = client.get("/api/reports/TS-2026-0001/docx", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(response.content) > 0

def test_activity_log():
    headers = get_auth_headers()
    response = client.get("/api/activity", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
