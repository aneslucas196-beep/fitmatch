#!/usr/bin/env python3
"""Test rapide : le module rappels et le serveur sont prêts (sans lancer uvicorn)."""
import os
import sys
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/test")

def main():
    print("1. Import main...")
    from main import process_due_reminders, REMINDERS_LOOP_INTERVAL, app
    print("   OK")
    print("2. process_due_reminders callable:", callable(process_due_reminders))
    print("3. REMINDERS_LOOP_INTERVAL:", REMINDERS_LOOP_INTERVAL)
    print("4. App FastAPI:", app is not None)
    print("5. Appel process_due_reminders() (sans rappels = 0)...")
    n = process_due_reminders()
    print("   Retour:", n)
    assert isinstance(n, int) and n >= 0
    print("\nOK - Tout est pret. Pour lancer le serveur 24/7 : python start_server.py")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("ERREUR:", e)
        sys.exit(1)
