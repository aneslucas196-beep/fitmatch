"""
Service de vérification email (OTP) pour le flux coach post-paiement Stripe.
Génère un code 6 chiffres, le hash, le stocke en DB, envoie l'email via Resend.
"""
import os
import random
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from logger import get_logger

log = get_logger()

SALT = os.environ.get("OTP_SALT", "fitmatch-otp-salt-v1").encode("utf-8")


def _hash_code(code: str) -> str:
    """Hash le code avec SHA256 + salt."""
    data = (code + SALT.decode("utf-8")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _verify_code_hash(code: str, code_hash: str) -> bool:
    """Compare le code saisi au hash stocké."""
    return secrets.compare_digest(_hash_code(code), code_hash)


def send_email_verification_code(email: str) -> Tuple[bool, Optional[str]]:
    """
    Génère un code 6 chiffres, le hash, upsert en DB, envoie l'email via Resend.
    Retourne (success, error_message).
    """
    email = (email or "").strip().lower()
    if not email:
        return False, "Email invalide"

    try:
        from utils import use_database
        if not use_database():
            log.warning("email_verifications: DATABASE_URL requis, skip")
            return False, "Base de données non configurée"
    except Exception:
        return False, "Base de données non configurée"

    code = "".join(str(random.randint(0, 9)) for _ in range(6))
    code_hash = _hash_code(code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    from db_service import upsert_email_verification
    if not upsert_email_verification(email, code_hash, expires_at):
        return False, "Erreur sauvegarde du code"

    site_url = (os.environ.get("SITE_URL") or os.environ.get("REPLIT_DEV_DOMAIN", "http://localhost:5000")).strip()
    if site_url and not site_url.startswith("http"):
        site_url = f"https://{site_url}"
    verify_url = f"{site_url.rstrip('/')}/verify-email?email={email}"

    from resend_service import send_email_verification_code_email
    result = send_email_verification_code_email(to_email=email, otp_code=code, verify_url=verify_url)

    if result.get("success"):
        log.info(f"📧 Code OTP envoyé à {email}")
        return True, None
    return False, result.get("error", "Erreur envoi email")


def verify_email_code(email: str, code: str) -> Tuple[bool, Optional[str]]:
    """
    Vérifie le code saisi. Si OK: set verified_at, retourne (True, None).
    Sinon: (False, message_erreur).
    """
    email = (email or "").strip().lower()
    code = (code or "").strip()
    if not email or not code or len(code) != 6:
        return False, "Code invalide"

    try:
        from utils import use_database
        if not use_database():
            return False, "Base de données non configurée"
    except Exception:
        return False, "Base de données non configurée"

    from db_service import get_email_verification, set_email_verified
    row = get_email_verification(email)
    if not row:
        return False, "Code invalide ou expiré"
    if row.get("verified_at"):
        return True, None  # déjà vérifié

    expires_at = row.get("expires_at")
    if expires_at:
        try:
            expiry = expires_at if isinstance(expires_at, datetime) else datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if hasattr(expiry, "tzinfo") and expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if now > expiry:
                return False, "Code invalide ou expiré"
        except (ValueError, TypeError):
            pass

    if not _verify_code_hash(code, row.get("code_hash", "")):
        return False, "Code invalide ou expiré"

    set_email_verified(email)
    return True, None


def is_email_verified(email: str) -> bool:
    """Vérifie si l'email a été vérifié (verified_at existe)."""
    try:
        from utils import use_database
        if not use_database():
            return False
    except Exception:
        return False
    from db_service import is_email_verified_in_db
    return is_email_verified_in_db(email)
