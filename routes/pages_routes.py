"""
Routes pages statiques : contact, FAQ, mentions légales, confidentialité.
"""
from fastapi import Request
from fastapi.responses import HTMLResponse


def register_pages_routes(app, templates, get_i18n_context):
    """Enregistre les routes des pages statiques."""

    @app.get("/mentions-legales", response_class=HTMLResponse)
    async def mentions_legales_page(request: Request):
        """Mentions légales / CGU."""
        i18n = get_i18n_context(request)
        return templates.TemplateResponse("mentions_legales.html", {"request": request, **i18n})

    @app.get("/confidentialite", response_class=HTMLResponse)
    async def confidentialite_page(request: Request):
        """Politique de confidentialité."""
        i18n = get_i18n_context(request)
        return templates.TemplateResponse("confidentialite.html", {"request": request, **i18n})

    @app.get("/contact", response_class=HTMLResponse)
    async def contact_page(request: Request):
        """Page contact."""
        i18n = get_i18n_context(request)
        return templates.TemplateResponse("contact.html", {"request": request, **i18n})

    @app.get("/faq", response_class=HTMLResponse)
    async def faq_page(request: Request):
        """Page FAQ dédiée (clients et coachs)."""
        i18n = get_i18n_context(request)
        return templates.TemplateResponse("faq.html", {"request": request, **i18n})
