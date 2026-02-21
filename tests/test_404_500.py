"""Tests des pages 404 et du catch-all."""
import pytest
from fastapi.testclient import TestClient


def test_unknown_path_returns_html_404(client: TestClient):
    """Une URL inconnue doit renvoyer du HTML 404 (pas du JSON)."""
    r = client.get("/page-inexistante-xyz")
    assert r.status_code == 404
    assert "text/html" in r.headers.get("content-type", "")
    assert "404" in r.text or "not found" in r.text.lower() or "trouvée" in r.text.lower()


def test_api_unknown_returns_json_404(client: TestClient):
    """Une URL API inconnue doit renvoyer du JSON 404."""
    r = client.get("/api/route-inexistante-xyz")
    assert r.status_code == 404
    data = r.json()
    assert "detail" in data
