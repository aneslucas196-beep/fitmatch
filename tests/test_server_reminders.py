"""Vérifie que le serveur et la boucle de rappels sont correctement configurés."""
import os
import sys

# Éviter sys.exit au démarrage (pas de DATABASE_URL en test)
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/test")

def test_process_due_reminders_importable():
    """process_due_reminders existe et est callable."""
    from main import process_due_reminders
    assert callable(process_due_reminders)


def test_reminders_loop_interval():
    """REMINDERS_LOOP_INTERVAL est un entier positif."""
    from main import REMINDERS_LOOP_INTERVAL
    assert isinstance(REMINDERS_LOOP_INTERVAL, int)
    assert REMINDERS_LOOP_INTERVAL >= 1


def test_process_due_reminders_returns_int():
    """process_due_reminders retourne un int (sans rappels dus = 0)."""
    from main import process_due_reminders
    result = process_due_reminders()
    assert isinstance(result, int)
    assert result >= 0


def test_app_has_startup():
    """L'app FastAPI existe et peut être importée."""
    from main import app
    assert app is not None
    assert hasattr(app, "router")
