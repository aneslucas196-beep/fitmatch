"""Tests des endpoints système et health."""
import pytest
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient):
    """GET /health doit retourner status ok."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "db" in data


def test_robots_txt(client: TestClient):
    """GET /robots.txt doit retourner du texte."""
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "User-agent" in r.text
    assert "Disallow" in r.text


def test_sitemap_xml(client: TestClient):
    """GET /sitemap.xml doit retourner du XML valide."""
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "<?xml" in r.text
    assert "<urlset" in r.text or "<url>" in r.text


def test_favicon(client: TestClient):
    """GET /favicon.ico doit retourner 200."""
    r = client.get("/favicon.ico")
    assert r.status_code == 200
