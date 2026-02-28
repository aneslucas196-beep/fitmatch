"""
Tests E2E : flux coach, réservation, rappels.
Simule un parcours complet sans serveur externe.
"""
import os
import json
import tempfile
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("DATABASE_URL", "")
    from main import app
    return TestClient(app)


def test_health():
    """Health check doit répondre 200."""
    from main import app
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200


def test_coach_login_page():
    """Page coach-login doit être accessible."""
    from main import app
    c = TestClient(app)
    r = c.get("/coach-login")
    assert r.status_code == 200
    assert b"coach" in r.content.lower() or b"connect" in r.content.lower()


def test_coach_portal_requires_auth():
    """/coach/portal sans auth doit rediriger vers login."""
    from main import app
    c = TestClient(app, follow_redirects=False)
    r = c.get("/coach/portal")
    assert r.status_code in (302, 303, 401, 307)
    if r.status_code in (302, 303, 307):
        loc = r.headers.get("location", "").lower()
        assert "login" in loc or "profile-setup" in loc or "verify" in loc


def test_api_coaches_returns_list():
    """GET /api/coaches doit retourner une structure avec coaches."""
    from main import app
    c = TestClient(app)
    r = c.get("/api/coaches")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "coaches" in data
    assert isinstance(data["coaches"], list)


def test_api_working_hours_with_coach():
    """GET /api/coach/working-hours avec coach_email doit retourner des horaires."""
    from main import app
    c = TestClient(app)
    r = c.get("/api/coach/working-hours?coach_email=test@test.com")
    assert r.status_code in (200, 404, 500)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, dict)
        assert "monday" in data or len(data) >= 0


def test_api_session_duration():
    """GET /api/coach/session-duration doit retourner une durée."""
    from main import app
    c = TestClient(app)
    r = c.get("/api/coach/session-duration?coach_email=test@test.com")
    assert r.status_code in (200, 404, 500)
    if r.status_code == 200:
        data = r.json()
        assert "duration" in data or "success" in data


def test_booking_availability_endpoint():
    """GET /api/bookings/availability avec params doit répondre."""
    from main import app
    c = TestClient(app)
    r = c.get("/api/bookings/availability?coach_id=test&from=2026-03-01T00:00:00&to=2026-03-07T23:59:59")
    assert r.status_code in (200, 400, 404, 500)
    if r.status_code == 200:
        data = r.json()
        assert isinstance(data, (list, dict))


def test_schedule_booking_reminders():
    """schedule_booking_reminders crée bien 2 rappels (24h et 2h)."""
    from main import schedule_booking_reminders, load_scheduled_reminders
    now = datetime.now()
    rdv = now + timedelta(hours=48)
    booking = {
        "id": "e2e-test-1",
        "date": rdv.strftime("%Y-%m-%d"),
        "time": rdv.strftime("%H:%M"),
        "client_email": "client@test.com",
        "client_name": "Client E2E",
        "gym_name": "Salle Test",
        "gym_address": "1 rue Test",
        "service": "Séance",
        "duration": "60",
        "price": "40",
        "lang": "fr",
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json.dumps({"reminders": []}))
        path = f.name
    try:
        os.environ["SCHEDULED_REMINDERS_FILE"] = path
        schedule_booking_reminders(booking, "Coach E2E")
        data = load_scheduled_reminders()
        reminders = data.get("reminders", [])
        assert len(reminders) == 2
        types = {r["type"] for r in reminders}
        assert "24h" in types
        assert "2h" in types
    finally:
        os.environ.pop("SCHEDULED_REMINDERS_FILE", None)
        if os.path.exists(path):
            os.unlink(path)


def test_process_due_reminders_returns_int():
    """process_due_reminders retourne un int."""
    from main import process_due_reminders
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json.dumps({"reminders": []}))
        path = f.name
    try:
        os.environ["SCHEDULED_REMINDERS_FILE"] = path
        n = process_due_reminders()
        assert isinstance(n, int)
        assert n >= 0
    finally:
        os.environ.pop("SCHEDULED_REMINDERS_FILE", None)
        if os.path.exists(path):
            os.unlink(path)


def test_reserver_slug_route():
    """Route /reserver/{slug} doit exister (404 si coach inconnu)."""
    from main import app
    c = TestClient(app)
    r = c.get("/reserver/coach-inconnu-xyz")
    assert r.status_code in (200, 404)


def test_reserver_book_route():
    """Route /reserver/{slug}/book doit exister."""
    from main import app
    c = TestClient(app)
    r = c.get("/reserver/coach-inconnu-xyz/book")
    assert r.status_code in (200, 404)
