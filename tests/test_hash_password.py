"""Tests des fonctions de hashage de mot de passe."""
import pytest
from main import hash_password, verify_password


def test_hash_password_returns_string():
    """hash_password doit retourner une chaîne."""
    result = hash_password("test123")
    assert isinstance(result, str)
    assert len(result) > 20
    assert result.startswith("$2b$") or result.startswith("$2a$")


def test_verify_password_correct():
    """verify_password doit accepter un mot de passe correct."""
    hashed = hash_password("correct_password")
    assert verify_password("correct_password", hashed) is True


def test_verify_password_incorrect():
    """verify_password doit refuser un mauvais mot de passe."""
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_no_plaintext_fallback():
    """verify_password ne doit jamais accepter password==hashed en clair."""
    assert verify_password("same", "same") is False
    assert verify_password("admin", "admin") is False
