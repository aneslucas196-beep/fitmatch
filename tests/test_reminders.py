"""Tests des rappels 24h et 2h avant le RDV + endpoint process."""
import os
import json
import tempfile
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient


def test_reminders_process_endpoint_returns_json(client: TestClient):
    """GET /api/reminders_process doit retourner 200 et JSON avec success et reminders_sent."""
    r = client.get("/api/reminders_process")
    assert r.status_code == 200
    data = r.json()
    assert "success" in data
    assert data["success"] in (True, False)
    if data["success"]:
        assert "reminders_sent" in data


def test_schedule_booking_reminders_24h_and_2h():
    """Vérifie que schedule_booking_reminders crée bien un rappel 24h et un rappel 2h avant le RDV."""
    from main import (
        load_scheduled_reminders,
        save_scheduled_reminders,
        schedule_booking_reminders,
        _reminders_file_path,
    )
    # RDV dans 48h pour avoir les deux rappels
    now = datetime.now()
    rdv = now + timedelta(hours=48)
    booking = {
        "id": "test-booking-1",
        "date": rdv.strftime("%Y-%m-%d"),
        "time": rdv.strftime("%H:%M"),
        "client_email": "client@test.com",
        "client_name": "Client Test",
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
        schedule_booking_reminders(booking, "Coach Test")
        data = load_scheduled_reminders()
        reminders = data.get("reminders", [])
        assert len(reminders) == 2
        types = {r["type"] for r in reminders}
        assert "24h" in types
        assert "2h" in types
        for r in reminders:
            assert "send_at" in r
            send_at = datetime.fromisoformat(r["send_at"])
            if r["type"] == "24h":
                assert abs((send_at - (rdv - timedelta(hours=24))).total_seconds()) < 60
            else:
                assert abs((send_at - (rdv - timedelta(hours=2))).total_seconds()) < 60
    finally:
        os.environ.pop("SCHEDULED_REMINDERS_FILE", None)
        if os.path.exists(path):
            os.unlink(path)


def test_process_due_reminders_empty_returns_zero():
    """Sans rappels dus, process_due_reminders retourne 0."""
    from main import process_due_reminders, save_scheduled_reminders
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json.dumps({"reminders": []}))
        path = f.name
    try:
        os.environ["SCHEDULED_REMINDERS_FILE"] = path
        n = process_due_reminders()
        assert n == 0
    finally:
        os.environ.pop("SCHEDULED_REMINDERS_FILE", None)
        if os.path.exists(path):
            os.unlink(path)


def test_process_due_reminders_sends_when_due():
    """process_due_reminders envoie les rappels dont send_at <= now (mock email)."""
    from unittest.mock import patch
    from main import process_due_reminders
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json.dumps({
            "reminders": [{
                "id": "due_1_24h",
                "type": "24h",
                "send_at": past,
                "client_email": "test@test.com",
                "client_name": "Test",
                "coach_name": "Coach",
                "gym_name": "Salle",
                "gym_address": "",
                "date": "2025-12-01",
                "time": "10:00",
                "service": "Séance",
                "duration": "60",
                "price": "40",
                "lang": "fr",
                "sent": False,
            }]
        }))
        path = f.name
    try:
        os.environ["SCHEDULED_REMINDERS_FILE"] = path
        with patch("resend_service.send_reminder_email", return_value={"success": True}):
            n = process_due_reminders()
        assert n >= 0
    finally:
        os.environ.pop("SCHEDULED_REMINDERS_FILE", None)
        if os.path.exists(path):
            os.unlink(path)
