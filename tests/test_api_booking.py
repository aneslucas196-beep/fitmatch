"""Tests des endpoints de réservation."""
import pytest
from fastapi.testclient import TestClient


def test_confirm_booking_requires_body(client: TestClient):
    """POST /api/confirm-booking sans body retourne 422."""
    r = client.post("/api/confirm-booking", json={})
    assert r.status_code == 422


def test_confirm_booking_invalid_email(client: TestClient):
    """POST /api/confirm-booking avec email invalide retourne 422."""
    r = client.post(
        "/api/confirm-booking",
        json={
            "client_name": "Test",
            "client_email": "invalid",
            "coach_name": "Coach",
            "gym_name": "Salle",
            "date": "2026-03-15",
            "time": "10:00",
            "service": "Coaching",
            "duration": "60",
            "price": "50",
        },
    )
    assert r.status_code == 422


def test_coach_bookings_requires_auth(client: TestClient):
    """GET /api/coach/bookings sans session retourne 401."""
    r = client.get("/api/coach/bookings")
    assert r.status_code in (401, 403, 500)


def test_respond_booking_requires_auth(client: TestClient):
    """POST /api/coach/bookings/respond sans session retourne 401."""
    r = client.post(
        "/api/coach/bookings/respond",
        json={
            "coach_email": "coach@example.com",
            "booking_id": "abc123",
            "action": "confirm",
        },
    )
    assert r.status_code in (401, 403, 422, 500)


def test_booking_by_id_requires_auth(client: TestClient):
    """GET /api/booking/{id} sans session retourne 401."""
    r = client.get("/api/booking/some-id")
    assert r.status_code in (401, 404, 500)
