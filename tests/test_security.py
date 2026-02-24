"""Tests de sécurité : verify_password, headers, CSP."""
import pytest
from fastapi.testclient import TestClient


def test_verify_password_no_plaintext_fallback(client: TestClient):
    """verify_password ne doit jamais accepter password == hashed (fallback dangereux)."""
    from main import verify_password
    # Hash bcrypt valide pour "secret"
    valid_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.G2z7qK5qK5qK5q"
    # Même si le hash est invalide/corrompu, ne doit jamais retourner True pour password en clair
    assert verify_password("secret", "secret") is False
    assert verify_password("password", "password") is False
    assert verify_password("admin", "admin") is False


def test_security_headers_present(client: TestClient):
    """Les headers de sécurité doivent être présents."""
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in [h.lower() for h in r.headers.keys()]


def test_csp_header_contains_self(client: TestClient):
    """La CSP doit contenir 'self' pour script-src."""
    r = client.get("/")
    csp = r.headers.get("content-security-policy", "")
    assert "'self'" in csp
    assert "script-src" in csp
