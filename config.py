"""
Configuration centralisée FitMatch.
Charge et valide les variables d'environnement au démarrage.
"""
import os
from typing import List, Optional

# Charger .env automatiquement (si présent) pour que les clés soient lues
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _split_origins(value: Optional[str]) -> List[str]:
    """Parse CORS_ORIGINS (virgules ou espaces). * retourne ['*']."""
    if not value or not value.strip():
        return ["*"]
    if value.strip() == "*":
        return ["*"]
    return [o.strip() for o in value.replace(" ", ",").split(",") if o.strip()]


class Settings:
    """Configuration lue depuis les variables d'environnement."""

    # Base de données (requis en production)
    DATABASE_URL: Optional[str] = os.environ.get("DATABASE_URL")

    # Stripe
    STRIPE_PUBLIC_KEY: Optional[str] = os.environ.get("STRIPE_PUBLIC_KEY")
    STRIPE_SECRET_KEY: Optional[str] = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.environ.get("STRIPE_WEBHOOK_SECRET")
    # Optionnel : Price ID mensuel (ex: price_xxx) - sinon price_data dynamique
    STRIPE_PRICE_ID: Optional[str] = os.environ.get("STRIPE_PRICE_ID") or os.environ.get("STRIPE_MONTHLY_PRICE_ID")
    STRIPE_ANNUAL_PRICE_ID: Optional[str] = os.environ.get("STRIPE_ANNUAL_PRICE_ID")

    # Resend
    RESEND_API_KEY: Optional[str] = os.environ.get("RESEND_API_KEY")
    SENDER_EMAIL: Optional[str] = os.environ.get("SENDER_EMAIL")

    # Supabase
    SUPABASE_URL: Optional[str] = os.environ.get("SUPABASE_URL")
    SUPABASE_ANON_KEY: Optional[str] = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")
    # Secret pour vérifier la signature des JWT Supabase (Project Settings > API > JWT Secret)
    SUPABASE_JWT_SECRET: Optional[str] = os.environ.get("SUPABASE_JWT_SECRET")
    JWT_SECRET_KEY: Optional[str] = os.environ.get("JWT_SECRET_KEY")

    # Google (optionnel)
    GOOGLE_MAPS_API_KEY: Optional[str] = os.environ.get("GOOGLE_MAPS_API_KEY")
    GOOGLE_PLACES_API_KEY: Optional[str] = os.environ.get("GOOGLE_PLACES_API_KEY")

    # Site
    SITE_URL: str = os.environ.get("SITE_URL", "http://localhost:5000")
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    # CORS : en production, définir CORS_ORIGINS (ex: https://fitmatch.fr,https://www.fitmatch.fr)
    @property
    def CORS_ORIGINS(self) -> List[str]:
        return _split_origins(os.environ.get("CORS_ORIGINS"))

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    def get_jwt_secret(self) -> Optional[str]:
        """Clé utilisée pour vérifier la signature JWT (Supabase ou JWT_SECRET_KEY)."""
        return self.SUPABASE_JWT_SECRET or self.JWT_SECRET_KEY


settings = Settings()
