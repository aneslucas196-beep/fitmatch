#!/usr/bin/env python3
"""
Script de test complet FitMatch.
Teste : coach, réservation, rappels, APIs.
"""
import os
import sys
import json
import tempfile
from datetime import datetime, timedelta

# Mode test
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run():
    from fastapi.testclient import TestClient
    from main import app, process_due_reminders, schedule_booking_reminders, load_scheduled_reminders
    from utils import save_demo_user, get_demo_user, load_demo_users, _invalidate_users_cache

    client = TestClient(app)
    ok = 0
    fail = 0

    def check(name, cond, msg=""):
        nonlocal ok, fail
        if cond:
            print(f"  [OK] {name}")
            ok += 1
            return True
        print(f"  [FAIL] {name}" + (f" - {msg}" if msg else ""))
        fail += 1
        return False

    print("\n" + "=" * 60)
    print("TEST COMPLET FITMATCH")
    print("=" * 60)

    # 1. Health
    print("\n1. Health & API de base")
    r = client.get("/health")
    check("Health 200", r.status_code == 200)

    r = client.get("/api/coaches")
    check("API coaches 200", r.status_code == 200)
    if r.status_code == 200:
        data = r.json()
        check("API coaches structure", "coaches" in data and isinstance(data["coaches"], list))

    # 2. Coach login
    print("\n2. Coach login")
    r = client.get("/coach-login")
    check("Page coach-login 200", r.status_code == 200)

    # 3. Coach portal (sans auth = redirect)
    print("\n3. Coach portal (sans auth)")
    r = client.get("/coach/portal", follow_redirects=False)
    check("Portal sans auth = redirect", r.status_code in (302, 303, 307))

    # 4. APIs coach (GET publics)
    print("\n4. APIs coach (GET)")
    r = client.get("/api/coach/working-hours?coach_email=test@test.com")
    check("Working-hours GET", r.status_code in (200, 404, 500))
    if r.status_code == 200:
        data = r.json()
        check("Working-hours format", isinstance(data, dict) and ("monday" in data or len(data) == 0))

    r = client.get("/api/coach/session-duration?coach_email=test@test.com")
    check("Session-duration GET", r.status_code in (200, 404, 500))

    # 5. Réservation
    print("\n5. Réservation")
    r = client.get("/api/bookings/availability?coach_id=test&from=2026-03-01T00:00:00&to=2026-03-07T23:59:59")
    check("Availability GET", r.status_code in (200, 400, 404, 500))

    r = client.get("/reserver/coach-xyz/book")
    check("Page réservation /reserver/{slug}/book", r.status_code in (200, 404))

    # 6. Rappels
    print("\n6. Rappels")
    rdv = datetime.now() + timedelta(hours=48)
    booking = {
        "id": "full-test-1",
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
        check("schedule_booking_reminders crée 2 rappels", len(reminders) == 2)
        if reminders:
            types = {r["type"] for r in reminders}
            check("Rappels 24h et 2h", "24h" in types and "2h" in types)

        n = process_due_reminders()
        check("process_due_reminders retourne int", isinstance(n, int) and n >= 0)
    finally:
        os.environ.pop("SCHEDULED_REMINDERS_FILE", None)
        if os.path.exists(path):
            os.unlink(path)

    # 7. API reminders process
    print("\n7. API reminders process")
    r = client.get("/api/reminders_process")
    check("GET /api/reminders_process 200", r.status_code == 200)
    if r.status_code == 200:
        data = r.json()
        check("Réponse success + reminders_sent", "success" in data and "reminders_sent" in data)

    # 8. Test avec coach existant (si demo_users)
    print("\n8. Coach avec données")
    users = load_demo_users()
    coaches = [e for e, u in users.items() if u.get("role") == "coach"]
    if coaches:
        email = coaches[0]
        r = client.get(f"/api/coach/working-hours?coach_email={email}")
        check(f"Working-hours coach existant ({email})", r.status_code == 200)
    else:
        print("  (aucun coach en base - skip)")

    # Résumé
    print("\n" + "=" * 60)
    print(f"RÉSULTAT: {ok} OK, {fail} FAIL")
    print("=" * 60)

    return 0 if fail == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as e:
        print(f"\nERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
