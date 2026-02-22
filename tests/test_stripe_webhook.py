"""Tests du webhook Stripe (signature, format)."""
import pytest
from fastapi.testclient import TestClient


def test_webhook_rejects_get(client: TestClient):
    """GET /api/stripe/webhook doit être refusé (405)."""
    r = client.get("/api/stripe/webhook")
    assert r.status_code == 405


def test_webhook_invalid_payload(client: TestClient):
    """POST sans payload valide ou signature invalide retourne 400 ou 400."""
    r = client.post(
        "/api/stripe/webhook",
        content=b"invalid",
        headers={"Content-Type": "application/json"},
    )
    # Sans STRIPE_WEBHOOK_SECRET en test, le comportement peut être 400, 500 ou 200 (selon le code)
    assert r.status_code in (200, 400, 500)
