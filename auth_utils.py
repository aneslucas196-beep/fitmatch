"""
Utilitaires d'authentification sécurisés pour FitMatch.
Remplace le token MD5 par HMAC-SHA256.
"""
import hmac
import hashlib
import secrets
from typing import Optional


def _session_secret() -> bytes:
    """Secret pour la dérivation des tokens de session. En production, JWT_SECRET_KEY ou SUPABASE_JWT_SECRET requis."""
    import os
    env = os.environ.get("ENVIRONMENT", "development")
    secret = (
        os.environ.get("JWT_SECRET_KEY")
        or os.environ.get("SUPABASE_JWT_SECRET")
        or (os.environ.get("SITE_URL") if env != "production" else "")
        or ""
    )
    if not secret or not secret.strip():
        if env == "production":
            raise RuntimeError(
                "JWT_SECRET_KEY ou SUPABASE_JWT_SECRET requis en production. "
                "Configurez dans Render > Environment."
            )
        secret = "fitmatch-session-secret-dev"
    return (secret or "")[:64].encode("utf-8").ljust(64, b"\0")


def generate_session_token(email: str) -> str:
    """Génère un token de session sécurisé (HMAC-SHA256)."""
    email = (email or "").strip().lower()
    if not email:
        return ""
    sig = hmac.new(_session_secret(), email.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"demo_{sig}"


def validate_session_token(token: str, email: str) -> bool:
    """Vérifie qu'un token correspond à un email."""
    if not token or not email:
        return False
    expected = generate_session_token(email)
    return secrets.compare_digest(token.strip(), expected)


def get_email_from_session_token(token: str, load_users_fn) -> Optional[str]:
    """
    Retourne l'email associé au token en parcourant les utilisateurs.
    load_users_fn: callable qui retourne dict[email, user_data]
    """
    if not token or not token.startswith("demo_") or len(token) < 20:
        return None
    users = load_users_fn()
    if not isinstance(users, dict):
        return None
    for email in users:
        if validate_session_token(token, email):
            return email
    return None
