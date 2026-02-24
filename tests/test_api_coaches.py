"""Tests de l'API coaches."""
import pytest
from fastapi.testclient import TestClient


def test_api_coaches_returns_json(client: TestClient):
    """GET /api/coaches doit retourner du JSON avec pagination."""
    r = client.get("/api/coaches")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert "coaches" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_api_coaches_pagination_params(client: TestClient):
    """GET /api/coaches accepte limit et offset."""
    r = client.get("/api/coaches?limit=5&offset=0")
    assert r.status_code == 200


def test_api_coaches_with_specialty_filter(client: TestClient):
    """GET /api/coaches avec specialty filtre les résultats."""
    r = client.get("/api/coaches?specialty=musculation")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert isinstance(data.get("coaches"), list)


def test_api_coaches_with_postal_code_filter(client: TestClient):
    """GET /api/coaches avec postal_code filtre les résultats."""
    r = client.get("/api/coaches?postal_code=75001")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True


def test_api_coaches_with_gym_id_filter(client: TestClient):
    """GET /api/coaches?gym_id=xxx filtre par salle."""
    r = client.get("/api/coaches?gym_id=bf_coigniere")
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert "coaches" in data


def test_api_gyms_search_requires_params(client: TestClient):
    """GET /api/gyms/search sans params retourne 200 ou 400."""
    r = client.get("/api/gyms/search")
    assert r.status_code in (200, 400)


def test_coach_service_get_coaches_list():
    """Le service coach retourne une liste (mock)."""
    from services.coach_service import get_coaches_list
    mock_load = lambda: {}  # Utilisateurs vides
    mock_gym = lambda gid: []
    result = get_coaches_list(mock_load, mock_gym, gym_id=None)
    assert isinstance(result, list)
    assert len(result) == 0
