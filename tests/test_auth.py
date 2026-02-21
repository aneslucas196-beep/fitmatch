"""Tests des endpoints d'authentification."""
import pytest
from fastapi.testclient import TestClient


def test_login_missing_credentials(client: TestClient):
    """POST /api/login sans body doit retourner 422 ou 401."""
    r = client.post("/api/login", data={})
    assert r.status_code in (401, 422)


def test_login_invalid_email(client: TestClient):
    """POST /api/login avec email invalide."""
    r = client.post(
        "/api/login",
        data={"email": "invalid", "password": "password123"},
    )
    assert r.status_code in (401, 422)


def test_api_client_bookings_requires_auth(client: TestClient):
    """GET /api/client/bookings sans session doit retourner 401."""
    r = client.get("/api/client/bookings")
    assert r.status_code == 401
    data = r.json()
    assert "success" in data or "detail" in data


def test_docs_accessible(client: TestClient):
    """La doc OpenAPI doit être accessible."""
    r = client.get("/docs")
    assert r.status_code == 200


def test_openapi_json(client: TestClient):
    """Le schéma OpenAPI doit contenir le titre FitMatch."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert data.get("info", {}).get("title") == "FitMatch API"
