"""Tests des endpoints API principaux."""
import pytest
from fastapi.testclient import TestClient


def test_api_gyms_returns_structure(client: TestClient):
    """GET /api/gyms doit retourner gyms, total, limit, offset."""
    r = client.get("/api/gyms?limit=5&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert "gyms" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_api_coaches_returns_structure(client: TestClient):
    """GET /api/coaches doit retourner coaches avec pagination."""
    r = client.get("/api/coaches?limit=10&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert "coaches" in data
    assert "total" in data


def test_api_gyms_search_requires_params(client: TestClient):
    """GET /api/gyms/search sans params retourne message ou résultats vides."""
    r = client.get("/api/gyms/search")
    assert r.status_code == 200
    data = r.json()
    assert "success" in data or "gyms" in data


def test_robots_txt(client: TestClient):
    """GET /robots.txt doit retourner du texte."""
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "User-agent" in r.text


def test_sitemap_xml(client: TestClient):
    """GET /sitemap.xml doit retourner du XML valide."""
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "<?xml" in r.text or "<urlset" in r.text


def test_api_gyms_search_with_postal_code(client: TestClient):
    """GET /api/gyms/search avec postal_code retourne une structure valide."""
    r = client.get("/api/gyms/search?postal_code=75001")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert "gyms" in data


def test_api_gyms_search_with_query(client: TestClient):
    """GET /api/gyms/search avec q retourne des résultats ou liste vide."""
    r = client.get("/api/gyms/search?q=Paris")
    assert r.status_code == 200
    data = r.json()
    assert "gyms" in data or "success" in data


def test_api_coaches_pagination_boundaries(client: TestClient):
    """GET /api/coaches avec offset élevé retourne liste vide si pas de données."""
    r = client.get("/api/coaches?limit=10&offset=9999")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert len(data.get("coaches", [])) <= 10


def test_docs_returns_html(client: TestClient):
    """GET /docs redirige ou retourne la doc Swagger."""
    r = client.get("/docs")
    assert r.status_code == 200


def test_openapi_schema(client: TestClient):
    """GET /openapi.json retourne un schéma valide."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert data.get("info", {}).get("title")
    assert "paths" in data
