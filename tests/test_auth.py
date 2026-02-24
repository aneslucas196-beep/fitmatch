"""Tests des endpoints d'authentification."""
import pytest
from fastapi.testclient import TestClient


def test_login_missing_credentials(client: TestClient):
    """POST /api/login sans body doit retourner 422 ou 401."""
    r = client.post("/api/login", json={})
    assert r.status_code in (400, 401, 422)


def test_login_invalid_email(client: TestClient):
    """POST /api/login avec email invalide."""
    r = client.post(
        "/api/login",
        json={"email": "invalid", "password": "password123"},
    )
    assert r.status_code in (400, 401, 422)


def test_login_empty_password(client: TestClient):
    """POST /api/login sans mot de passe."""
    r = client.post("/api/login", json={"email": "test@example.com"})
    assert r.status_code in (400, 401, 422)


def test_logout_redirects(client: TestClient):
    """GET /logout doit rediriger vers /."""
    r = client.get("/logout", follow_redirects=False)
    assert r.status_code == 303
    assert "/" in (r.headers.get("location") or "")


def test_api_client_bookings_requires_auth(client: TestClient):
    """GET /api/client/bookings sans session doit retourner 401 ou 500 (si DB erreur)."""
    r = client.get("/api/client/bookings")
    assert r.status_code in (401, 500)
    if r.status_code == 401:
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


def test_health_endpoint(client: TestClient):
    """GET /health doit retourner status ok."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "db" in data


def test_verify_password_no_fallback():
    """verify_password ne doit jamais accepter password==hashed en clair (fallback supprimé)."""
    from main import verify_password
    # Hash bcrypt valide pour "test123"
    valid_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G4jYz5z5z5z5z5"
    assert verify_password("wrongpassword", valid_hash) is False
    # Ancien fallback dangereux : password == hashed en clair -> doit rester False
    assert verify_password("plaintext", "plaintext") is False


def test_robots_txt(client: TestClient):
    """GET /robots.txt doit retourner du texte."""
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "User-agent" in r.text or "Disallow" in r.text


def test_sitemap_xml(client: TestClient):
    """GET /sitemap.xml doit retourner du XML valide."""
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "<?xml" in r.text or "urlset" in r.text.lower()
