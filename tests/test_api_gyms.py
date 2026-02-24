"""Tests de l'API gyms."""
import pytest
from fastapi.testclient import TestClient


def test_api_gyms_search_with_postal_code(client: TestClient):
    """GET /api/gyms/search?postal_code=75001 retourne des salles ou liste vide."""
    r = client.get("/api/gyms/search?postal_code=75001")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert "gyms" in data or "count" in data


def test_api_gyms_search_with_query(client: TestClient):
    """GET /api/gyms/search?q=Paris retourne des résultats."""
    r = client.get("/api/gyms/search?q=Paris")
    assert r.status_code == 200
    data = r.json()
    assert "gyms" in data or "success" in data


def test_api_gyms_suggestions(client: TestClient):
    """GET /api/gyms/suggestions?q=Basic retourne des suggestions."""
    r = client.get("/api/gyms/suggestions?q=Basic")
    assert r.status_code == 200
    data = r.json()
    assert "suggestions" in data or "success" in data


def test_api_gyms_countries(client: TestClient):
    """GET /api/gyms/countries retourne la liste des pays."""
    r = client.get("/api/gyms/countries")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert "countries" in data
