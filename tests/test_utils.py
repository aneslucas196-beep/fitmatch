"""Tests des utilitaires."""
import pytest


def test_hash_password():
    """hash_password produit un hash bcrypt valide."""
    from main import hash_password, verify_password
    pwd = "testpassword123"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(pwd, hashed) is True


def test_verify_password_wrong_password():
    """verify_password rejette un mauvais mot de passe."""
    from main import hash_password, verify_password
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_serialize_for_json():
    """serialize_for_json gère datetime."""
    from utils import serialize_for_json
    from datetime import datetime
    d = datetime(2026, 2, 24, 12, 0, 0)
    assert "2026" in serialize_for_json(d)


def test_get_coaches_count_by_gym_ids_empty():
    """get_coaches_count_by_gym_ids avec liste vide retourne dict vide."""
    from main import get_coaches_count_by_gym_ids
    result = get_coaches_count_by_gym_ids([])
    assert result == {}


def test_get_gyms_by_ids_empty():
    """get_gyms_by_ids avec liste vide retourne dict vide."""
    from main import get_gyms_by_ids
    result = get_gyms_by_ids([])
    assert result == {}
