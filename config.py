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


def _split_origins(value: Optional[str], is_production: bool = False) -> List[str]:
    """Parse CORS_ORIGINS. En production, * est refuse pour la securite."""
    if not value or not value.strip():
        return []
    if value.strip() == "*":
        return [] if is_production else ["*"]
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

    # CORS : en production, CORS_ORIGINS obligatoire (ex: https://fitmatch.fr,https://www.fitmatch.fr)
    @property
    def CORS_ORIGINS(self) -> List[str]:
        origins = _split_origins(os.environ.get("CORS_ORIGINS"), self.IS_PRODUCTION)
        if not origins and self.IS_PRODUCTION:
            site = (os.environ.get("SITE_URL") or "").strip()
            if site and site.startswith("http"):
                base = site.rstrip("/")
                www = base.replace("https://", "https://www.") if "www." not in base else base
                return list(dict.fromkeys([base, www]))
        return origins if origins else ["*"]

    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    def get_jwt_secret(self) -> Optional[str]:
        """Clé utilisée pour vérifier la signature JWT (Supabase ou JWT_SECRET_KEY)."""
        return self.SUPABASE_JWT_SECRET or self.JWT_SECRET_KEY


def build_csp_header(nonce: Optional[str] = None, strict: bool = False) -> str:
    """
    Construit l'en-tête Content-Security-Policy.
    - nonce : permet d'autoriser les scripts avec attribut nonce
    - strict : en production avec nonce, utilise 'strict-dynamic' (réduit unsafe-inline)
    """
    env = os.environ.get("ENVIRONMENT", "development")
    is_prod = env.lower() in ("production", "prod")
    script_src = "'self' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net https://maps.googleapis.com"
    if nonce:
        script_src += f" 'nonce-{nonce}'"
    if strict and is_prod and nonce:
        script_src += " 'strict-dynamic'"  # Réduit unsafe-inline, scripts noncés autorisés
    else:
        script_src += " 'unsafe-inline' 'unsafe-eval'"  # Dev + Tailwind CDN
    return (
        "default-src 'self'; "
        f"script-src {script_src}; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https: blob:; "
        "connect-src 'self' https://api.stripe.com https://*.supabase.co https://equipements.sports.gouv.fr; "
        "frame-src 'self' https://js.stripe.com https://hooks.stripe.com; "
        "frame-ancestors 'none';"
    )


settings = Settings()
