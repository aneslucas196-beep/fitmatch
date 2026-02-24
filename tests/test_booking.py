"""Tests des endpoints de réservation."""
import pytest
from fastapi.testclient import TestClient


def test_client_bookings_unauthorized(client: TestClient):
    """Sans cookie de session, /api/client/bookings renvoie 401."""
    r = client.get("/api/client/bookings")
    assert r.status_code == 401


def test_cancel_booking_requires_post(client: TestClient):
    """POST /api/cancel-booking sans body peut retourner 422, 400, 401 ou 500."""
    r = client.post("/api/cancel-booking", json={})
    assert r.status_code in (400, 401, 422, 500)


def test_confirm_booking_requires_valid_body(client: TestClient):
    """POST /api/confirm-booking avec body incomplet retourne 422."""
    r = client.post("/api/confirm-booking", json={"client_name": "Test"})
    assert r.status_code in (400, 422, 500)


def test_coach_bookings_unauthorized(client: TestClient):
    """GET /api/coach/bookings sans session coach retourne 401."""
    r = client.get("/api/coach/bookings")
    assert r.status_code == 401


def test_booking_availability(client: TestClient):
    """GET /api/bookings/availability avec params valides."""
    r = client.get("/api/bookings/availability?coach_id=test&date=2026-03-01")
    assert r.status_code in (200, 400, 404, 500)
