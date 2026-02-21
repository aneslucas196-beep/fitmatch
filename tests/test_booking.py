"""Tests des endpoints de réservation."""
import pytest
from fastapi.testclient import TestClient


def test_client_bookings_unauthorized(client: TestClient):
    """Sans cookie de session, /api/client/bookings renvoie 401."""
    r = client.get("/api/client/bookings")
    assert r.status_code == 401


def test_cancel_booking_requires_post(client: TestClient):
    """POST /api/cancel-booking sans body peut retourner 422."""
    r = client.post("/api/cancel-booking", json={})
    assert r.status_code in (400, 401, 422)
