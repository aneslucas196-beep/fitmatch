"""
Configuration optionnelle du monitoring (Sentry).
Activer en définissant SENTRY_DSN dans les variables d'environnement.
"""
import os


def init_sentry() -> bool:
    """
    Initialise Sentry si SENTRY_DSN est défini.
    Returns: True si Sentry a été initialisé, False sinon.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("ENVIRONMENT", "development"),
            traces_sample_rate=0.1,
            integrations=[FastApiIntegration()],
            send_default_pii=False,
        )
        return True
    except ImportError:
        return False
