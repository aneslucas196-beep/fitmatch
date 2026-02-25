"""
Routes système : health, favicon, robots.txt, sitemap.xml, Google Search Console, config-check.
"""
import os
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse, Response, FileResponse

# Router pour les endpoints simples (évite les conflits au démarrage)
router = APIRouter()


@router.get("/api/system/config-check", include_in_schema=False)
async def config_check(secret: str = Query(None, alias="secret")):
    """
    Vérifie la configuration Stripe et Google Maps (sans exposer les secrets).
    Optionnel : ?secret=CRON_SECRET pour protéger en production.
    """
    from config import get_stripe_config_status, get_maps_config_status
    if os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod"):
        cron_secret = os.environ.get("CRON_SECRET")
        if cron_secret and secret != cron_secret:
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    return JSONResponse(content={
        "stripe": get_stripe_config_status(),
        "maps": get_maps_config_status(),
    })


@router.get("/googlec08eb3bf.html", include_in_schema=False)
async def google_verification():
    """Fichier de vérification Google Search Console."""
    return Response(
        content="google-site-verification: googlec08eb3bf.html",
        media_type="text/html"
    )


def register_system_routes(app, get_base_url_fn):
    """Enregistre les routes système sur l'app."""

    @app.get("/health", tags=["system"])
    async def health_check():
        """Endpoint de santé pour monitoring et déploiement."""
        try:
            db_ok = "skip"
            if os.environ.get("DATABASE_URL"):
                try:
                    from utils import load_demo_users
                    load_demo_users()
                    db_ok = "ok"
                except Exception:
                    db_ok = "error"
            return {"status": "ok", "db": db_ok}
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": str(e)}
            )

    @app.get("/favicon.ico")
    async def favicon():
        """Retourne le favicon du site."""
        return FileResponse("static/favicon.ico", media_type="image/x-icon")

    @app.get("/robots.txt")
    async def robots_txt(request: Request):
        """Fichier robots.txt pour les moteurs de recherche."""
        base = get_base_url_fn(request)
        sitemap_url = f"{base.rstrip('/')}/sitemap.xml"
        content = f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /coach/portal
Disallow: /coach/profile-setup
Disallow: /coach/subscription
Disallow: /coach/verify-email
Disallow: /coach-login
Disallow: /login
Disallow: /signup
Disallow: /mon-compte

Sitemap: {sitemap_url}
"""
        return Response(content=content, media_type="text/plain")

    @app.get("/sitemap.xml")
    async def sitemap_xml(request: Request):
        """Sitemap XML pour le référencement (sitelinks Google)."""
        base = get_base_url_fn(request)
        base = base.rstrip("/") if base else "https://fitmatch.fr"
        urls = [
            ("/", "daily", "1.0"),
            ("/about", "monthly", "0.8"),
            ("/pricing", "monthly", "0.8"),
            ("/projects", "monthly", "0.8"),
            ("/blog", "weekly", "0.8"),
            ("/blog/fitmatch-trouver-coach", "monthly", "0.7"),
            ("/gyms", "monthly", "0.8"),
            ("/gyms/finder", "weekly", "0.9"),
            ("/coaches", "monthly", "0.8"),
            ("/contact", "monthly", "0.7"),
            ("/signup", "weekly", "0.9"),
            ("/login", "weekly", "0.9"),
            ("/coach-signup", "weekly", "0.9"),
            ("/coach-login", "weekly", "0.9"),
            ("/coach/offre", "weekly", "0.9"),
            ("/faq", "monthly", "0.7"),
        ]
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for path, changefreq, priority in urls:
            loc = f"{base}{path}"
            xml += f'    <url>\n        <loc>{loc}</loc>\n        <changefreq>{changefreq}</changefreq>\n        <priority>{priority}</priority>\n    </url>\n'
        xml += '</urlset>'
        return Response(content=xml, media_type="application/xml")
