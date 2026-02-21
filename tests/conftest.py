"""
Configuration pytest pour FitMatch.
Définit DATABASE_URL pour éviter sys.exit au startup (les tests qui touchent la DB peuvent être mockés ou skippés).
"""
import os
import sys

# Définir DATABASE_URL avant l'import de main pour que le startup ne quitte pas
os.environ.setdefault("DATABASE_URL", "postgresql://localhost:5432/fitmatch_test")

# Ajouter la racine du projet au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

# Import après avoir défini l'env pour que startup_check_database ne fasse pas sys.exit
from main import app


@pytest.fixture
def client():
    return TestClient(app)
