"""
Routes système : health, favicon, robots.txt, sitemap.xml.
"""
import os
from fastapi import Request
from fastapi.responses import JSONResponse, Response, FileResponse


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

    @app.get("/googlec08eb3bf.html", include_in_schema=False)
    async def google_verification():
        """Fichier de vérification Google Search Console."""
        return Response(
            content="google-site-verification: googlec08eb3bf.html",
            media_type="text/html"
        )

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
            ("/signup", "weekly", "0.9"),
            ("/login", "weekly", "0.9"),
            ("/coach-signup", "weekly", "0.9"),
            ("/coach-login", "weekly", "0.9"),
            ("/coach/offre", "weekly", "0.9"),
            ("/gyms/finder", "weekly", "0.9"),
            ("/contact", "monthly", "0.7"),
            ("/faq", "monthly", "0.7"),
        ]
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for path, changefreq, priority in urls:
            xml += f'  <url><loc>{base}{path}</loc><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>\n'
        xml += '</urlset>'
        return Response(content=xml, media_type="application/xml")
