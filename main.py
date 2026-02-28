from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, Cookie, Query, Response
import secrets
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List, Dict
from pydantic import BaseModel, EmailStr
import uvicorn
import jwt
import os
import sys
import time
import threading
import uuid
import json
import hashlib
from datetime import datetime, timedelta
import mimetypes
from PIL import Image
import io
from pathlib import Path
from typing import Tuple
import resend
import random
import bcrypt
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from logger import get_logger
log = get_logger()

limiter = Limiter(key_func=get_remote_address)

# CSRF : génération et vérification (cookie + champ formulaire / header)
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

def _generate_csrf_token() -> str:
    return secrets.token_hex(32)

def _verify_csrf(request: Request, token_submitted: Optional[str]) -> bool:
    """Vérifie que le token soumis (formulaire ou header) correspond au cookie."""
    if not token_submitted or not token_submitted.strip():
        return False
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token:
        return False
    return secrets.compare_digest(cookie_token.strip(), token_submitted.strip())

def _set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        max_age=86400,
        samesite="lax",
        path="/",
        httponly=True,
    )

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Vérifie le mot de passe contre le hash bcrypt. Pas de fallback en clair."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

from utils import (
    geocode_city, 
    search_coaches_mock, 
    get_coach_by_id_mock, 
    get_transformations_by_coach_mock,
    get_supabase_anon_client,
    get_supabase_client_for_user,
    # Nouvelles fonctions Supabase
    sign_in_user,
    get_user_profile,
    search_coaches_supabase,
    get_coach_by_id_supabase,
    get_transformations_by_coach_supabase,
    update_coach_profile,
    update_coach_specialties,
    add_transformation,
    upload_transformation_images,
    resend_confirmation_email,
    create_user_profile_on_confirmation,
    # Fonctions OTP
    generate_otp_code,
    store_otp_code,
    store_otp_code_for_user,
    verify_otp_code,
    cleanup_expired_otp_codes,
    create_user_account_with_otp,
    # Fonctions stockage persistant
    load_demo_users,
    save_demo_user,
    save_demo_users,
    get_demo_user,
    remove_demo_user,
    get_pending_otp_data,
    store_pending_registration,
    # Système coach ↔ salle ↔ client
    geocode_address,
    get_coach_gyms,
    add_coach_gym,
    remove_coach_gym,
    search_gyms_by_location,
    search_gyms_google_places,
    search_gyms_by_zone,
    get_coaches_by_gym,
    # Géolocalisation et pays
    get_countries_list,
    get_country_name,
    # Helpers de sérialisation JSON
    serialize_for_json,
    json_serial_default
)

from resend_service import send_otp_email_resend
from supabase_auth_service import signup_with_supabase_email_confirmation, resend_email_confirmation, sign_in_with_email_password, get_user_role
from config import settings, build_csp_header
from api.cron import router as cron_router

# Import du service d'internationalisation (i18n)
from i18n_service import (
    get_locale_from_request,
    get_translations,
    get_available_languages,
    preload_all_translations,
    SUPPORTED_LOCALES,
    DEFAULT_LOCALE,
    COOKIE_NAME as LOCALE_COOKIE_NAME
)

# Cache des langues disponibles (chargé une fois au démarrage)
_available_languages_cache = None

def get_i18n_context(request: Request) -> dict:
    """Retourne le contexte i18n pour les templates (locale, translations, available_languages)."""
    global _available_languages_cache
    if _available_languages_cache is None:
        _available_languages_cache = get_available_languages()
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    text_direction = "rtl" if locale == "ar" else "ltr"
    return {
        "locale": locale,
        "t": translations,
        "text_direction": text_direction,
        "available_languages": _available_languages_cache
    }

# Import Stripe service (gestion des abonnements coachs)
try:
    from stripe_service import (
        get_publishable_key,
        create_or_get_customer,
        create_checkout_session,
        create_portal_session,
        get_coach_subscription_info,
        update_coach_subscription,
        is_coach_subscribed,
        COACH_MONTHLY_PRICE,
        COACH_ANNUAL_PRICE,
        init_stripe
    )
    STRIPE_AVAILABLE = True
except Exception as stripe_import_error:
    log.warning(f"Stripe non disponible: {stripe_import_error}")
    STRIPE_AVAILABLE = False

# ============================================
# SYSTÈME DE RAPPELS PROGRAMMÉS
# ============================================

def _reminders_file_path() -> str:
    """Chemin du fichier des rappels (configurable en test via SCHEDULED_REMINDERS_FILE)."""
    return os.environ.get("SCHEDULED_REMINDERS_FILE", "scheduled_reminders.json")

def load_scheduled_reminders() -> dict:
    """Charge les rappels programmés depuis le fichier JSON."""
    try:
        path = _reminders_file_path()
        if not os.path.exists(path):
            return {"reminders": []}
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            return {"reminders": []}
        data = json.loads(raw)
        if not isinstance(data, dict) or "reminders" not in data:
            return {"reminders": []}
        return data
    except json.JSONDecodeError:
        # Fichier vide ou JSON invalide = pas de rappels, pas d'avertissement
        return {"reminders": []}
    except Exception as e:
        log.error(f"Erreur chargement rappels: {e}")
    return {"reminders": []}

def save_scheduled_reminders(data: dict):
    """Sauvegarde les rappels programmés dans le fichier JSON."""
    try:
        with open(_reminders_file_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Erreur sauvegarde rappels: {e}")

def schedule_booking_reminders(booking: dict, coach_name: str):
    """
    Programme les rappels pour une réservation confirmée.
    Crée 2 rappels: 24h avant et 2h avant le RDV.
    """
    try:
        booking_date = booking.get("date")
        booking_time = booking.get("time")
        
        if not booking_date or not booking_time:
            log.warning(f"Date/heure manquante pour programmer les rappels")
            return
        
        # Normaliser l'heure (accepter "14:00" ou "14:00:00")
        time_str = (booking_time or "").strip()
        if len(time_str) > 5 and ":" in time_str:
            time_str = time_str[:5]  # "14:00:00" -> "14:00"
        
        # Parser la date et l'heure du RDV
        booking_datetime = datetime.strptime(f"{booking_date} {time_str}", "%Y-%m-%d %H:%M")
        
        # Calculer les heures d'envoi des rappels
        reminder_24h = booking_datetime - timedelta(hours=24)
        reminder_2h = booking_datetime - timedelta(hours=2)
        
        now = datetime.now()
        
        # Charger les rappels existants
        reminders_data = load_scheduled_reminders()
        
        # Créer le rappel 24h (si le RDV est dans plus de 24h)
        if reminder_24h > now:
            reminders_data["reminders"].append({
                "id": f"{booking.get('id')}_24h",
                "booking_id": booking.get("id"),
                "type": "24h",
                "send_at": reminder_24h.isoformat(),
                "client_email": booking.get("client_email"),
                "client_name": booking.get("client_name"),
                "coach_name": coach_name,
                "gym_name": booking.get("gym_name"),
                "gym_address": booking.get("gym_address", ""),
                "date": booking_date,
                "time": booking_time,
                "service": booking.get("service", "Séance de coaching"),
                "duration": booking.get("duration", "60"),
                "price": booking.get("price", "40"),
                "lang": booking.get("lang", "fr"),
                "sent": False,
                "created_at": now.isoformat()
            })
            log.info(f"📅 Rappel 24h programmé pour {reminder_24h.strftime('%d/%m/%Y %H:%M')}")
        else:
            log.info(f"⏭️ RDV dans moins de 24h, pas de rappel J-1")
        
        # Créer le rappel 2h (si le RDV est dans plus de 2h)
        if reminder_2h > now:
            reminders_data["reminders"].append({
                "id": f"{booking.get('id')}_2h",
                "booking_id": booking.get("id"),
                "type": "2h",
                "send_at": reminder_2h.isoformat(),
                "client_email": booking.get("client_email"),
                "client_name": booking.get("client_name"),
                "coach_name": coach_name,
                "gym_name": booking.get("gym_name"),
                "gym_address": booking.get("gym_address", ""),
                "date": booking_date,
                "time": booking_time,
                "service": booking.get("service", "Séance de coaching"),
                "duration": booking.get("duration", "60"),
                "price": booking.get("price", "40"),
                "lang": booking.get("lang", "fr"),
                "sent": False,
                "created_at": now.isoformat()
            })
            log.info(f"⏰ Rappel 2h programmé pour {reminder_2h.strftime('%d/%m/%Y %H:%M')}")
        else:
            log.info(f"⏭️ RDV dans moins de 2h, pas de rappel 2h")
        
        # Sauvegarder
        save_scheduled_reminders(reminders_data)
        log.info(f"✅ Rappels programmés pour la réservation {booking.get('id')}")
        
    except Exception as e:
        log.error(f"Erreur programmation rappels: {e}")

def cancel_booking_reminders(booking_id: str):
    """Annule tous les rappels programmés pour une réservation."""
    try:
        reminders_data = load_scheduled_reminders()
        original_count = len(reminders_data["reminders"])
        
        # Filtrer pour retirer les rappels de cette réservation
        reminders_data["reminders"] = [
            r for r in reminders_data["reminders"] 
            if r.get("booking_id") != booking_id
        ]
        
        removed_count = original_count - len(reminders_data["reminders"])
        if removed_count > 0:
            save_scheduled_reminders(reminders_data)
            log.info(f"🗑️ {removed_count} rappel(s) annulé(s) pour la réservation {booking_id}")
        
    except Exception as e:
        log.error(f"Erreur annulation rappels: {e}")

def process_due_reminders():
    """
    Vérifie et envoie les rappels dus.
    Retourne le nombre de rappels envoyés.
    """
    from resend_service import send_reminder_email
    
    try:
        reminders_data = load_scheduled_reminders()
        now = datetime.now()
        sent_count = 0
        
        for reminder in reminders_data["reminders"]:
            if reminder.get("sent"):
                continue
            
            try:
                send_at_str = (reminder.get("send_at") or "").strip()
                if not send_at_str:
                    continue
                send_at = datetime.fromisoformat(send_at_str.replace("Z", "").replace("+00:00", ""))
            except (ValueError, TypeError):
                continue
            
            if send_at <= now:
                # C'est l'heure d'envoyer ce rappel
                log.info(f"📧 Envoi du rappel {reminder.get('type')} pour {reminder.get('client_email')}")
                
                # Formater la date en français
                try:
                    date_obj = datetime.strptime(reminder.get("date"), "%Y-%m-%d")
                    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                    date_fr = f"{jours[date_obj.weekday()].capitalize()} {date_obj.day} {mois[date_obj.month - 1]} {date_obj.year}"
                except Exception:
                    date_fr = reminder.get("date")
                
                result = send_reminder_email(
                    to_email=reminder.get("client_email"),
                    client_name=reminder.get("client_name"),
                    coach_name=reminder.get("coach_name"),
                    gym_name=reminder.get("gym_name"),
                    gym_address=reminder.get("gym_address", ""),
                    date_str=date_fr,
                    time_str=reminder.get("time"),
                    service_name=reminder.get("service", "Séance de coaching"),
                    duration=f"{reminder.get('duration', '60')} min",
                    price=f"{reminder.get('price', '40')}€",
                    reminder_type=reminder.get("type"),
                    booking_id=reminder.get("booking_id"),
                    lang=reminder.get("lang", "fr")
                )
                
                if result.get("success"):
                    reminder["sent"] = True
                    reminder["sent_at"] = now.isoformat()
                    sent_count += 1
                    log.info(f"✅ Rappel {reminder.get('type')} envoyé à {reminder.get('client_email')}")
                else:
                    log.error(f"Echec envoi rappel: {result.get('error')}")
        
        # Sauvegarder les mises à jour
        save_scheduled_reminders(reminders_data)
        
        # Nettoyer les rappels envoyés vieux de plus de 7 jours
        cleanup_old_reminders()
        
        return sent_count
        
    except Exception as e:
        log.error(f"Erreur traitement rappels: {e}")
        return 0

def cleanup_old_reminders():
    """Supprime les rappels envoyés depuis plus de 7 jours."""
    try:
        reminders_data = load_scheduled_reminders()
        now = datetime.now()
        cutoff = now - timedelta(days=7)
        
        original_count = len(reminders_data["reminders"])
        reminders_data["reminders"] = [
            r for r in reminders_data["reminders"]
            if not r.get("sent") or datetime.fromisoformat(r.get("sent_at", now.isoformat())) > cutoff
        ]
        
        removed = original_count - len(reminders_data["reminders"])
        if removed > 0:
            save_scheduled_reminders(reminders_data)
            log.info(f"🧹 {removed} ancien(s) rappel(s) nettoyé(s)")
            
    except Exception as e:
        log.warning(f"Erreur nettoyage rappels: {e}")

# ============================================

app = FastAPI(
    title="FitMatch API",
    description="API de la plateforme FitMatch : recherche de coachs, réservations, abonnements et paiements (Stripe).",
    version="1.0.0",
    openapi_tags=[
        {"name": "auth", "description": "Connexion, inscription, OTP"},
        {"name": "coach", "description": "Espace coach, profil, abonnement, Stripe Connect"},
        {"name": "booking", "description": "Réservations, disponibilités, annulations"},
        {"name": "stripe", "description": "Paiements et webhooks Stripe"},
        {"name": "client", "description": "Compte client, mes réservations"},
    ],
)

app.state.limiter = limiter

# Security headers pour la production (dont CSP)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = build_csp_header(nonce, strict=False)
    return response
app.include_router(cron_router)

# https_only=False en dev (localhost HTTP) pour que le cookie session soit stocké
_site_url = (os.getenv("SITE_URL") or "").lower()
_session_https = os.getenv("SESSION_HTTPS_ONLY", "1" if "https://" in _site_url or os.getenv("RENDER") else "0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", os.getenv("SESSION_SECRET", "change-me")),
    same_site="lax",
    https_only=(_session_https.lower() in ("1", "true", "yes"))
)


def get_session_email(request: Request) -> Optional[str]:
    """Retourne l'email stocké en session (après OTP verify)."""
    return request.session.get("user_email") or request.session.get("coach_email")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fitmatch.fr", "https://www.fitmatch.fr"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )


def _wants_html(request: Request) -> bool:
    """True si la requête attend du HTML (navigateur)."""
    if request.url.path.startswith("/api/"):
        return False
    accept = (request.headers.get("accept") or "").lower()
    return "text/html" in accept or "*/*" in accept or not accept.strip()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Renvoie une page HTML pour 404/500, redirige 401/403 vers login pour les pages web. API: JSON avec 'error'."""
    if request.url.path.startswith("/api/"):
        # API : toujours retourner JSON avec clé "error" pour le frontend
        msg = str(exc.detail) if exc.detail else "Erreur"
        return JSONResponse(status_code=exc.status_code, content={"error": msg, "detail": msg})
    if exc.status_code == 401 and _wants_html(request):
        return RedirectResponse(url="/login", status_code=302)
    if exc.status_code == 403 and _wants_html(request):
        return RedirectResponse(url="/coach-login", status_code=302)
    if exc.status_code == 500:
        i18n = get_i18n_context(request)
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "error": str(exc.detail) if exc.detail else None, **i18n},
            status_code=500,
        )
    if exc.status_code == 404:
        i18n = get_i18n_context(request)
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "message": str(exc.detail) if exc.detail else None, **i18n},
            status_code=404,
        )
    raise exc


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Erreurs non gérées : page HTML 500 pour les pages, JSON pour les API."""
    log.error(f"Erreur non gérée: {exc}")
    import traceback
    traceback.print_exc()
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    i18n = get_i18n_context(request)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": None, **i18n},
        status_code=500,
    )

# Précharger les traductions au démarrage
preload_all_translations()

def _is_stripe_configured() -> bool:
    """True si les clés Stripe sont définies et ne sont pas des placeholders (xxx)."""
    try:
        from config import get_stripe_configured
        return bool(STRIPE_AVAILABLE and get_stripe_configured())
    except Exception:
        sk = (os.environ.get("STRIPE_SECRET_KEY") or "").strip().lower()
        return bool(STRIPE_AVAILABLE and sk and "xxx" not in sk)

def _get_stripe_not_configured_response():
    """Réponse 500 JSON quand Stripe n'est pas configuré."""
    try:
        from config import get_stripe_missing
        missing = get_stripe_missing(required_only=False)
    except Exception:
        missing = ["STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY"]
    return JSONResponse(
        status_code=500,
        content={"error": "stripe_not_configured", "missing": missing}
    )


def _get_base_url(request: Request) -> str:
    """
    Retourne l'URL de base du site (ex: https://fitmatch.fr) pour redirections et Stripe.
    Priorité : SITE_URL > X-Forwarded-Proto+Host (proxy) > request.url.
    En production définir SITE_URL=https://fitmatch.fr
    """
    base = (os.environ.get("SITE_URL") or "").strip().rstrip("/")
    if base:
        if not base.startswith("http"):
            base = "https://" + base
        return base
    # Proxy (Render, Replit, Nginx)
    proto = (request.headers.get("x-forwarded-proto") or "").strip().lower() or "https"
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip()
    if host:
        return f"{proto}://{host}".rstrip("/")
    if request.url:
        u = str(request.url)
        scheme = request.headers.get("x-forwarded-proto") or (u.split("/")[0].replace(":", "") if "://" in u else "https")
        return f"{scheme}://{request.headers.get('host', 'localhost')}"
    return "https://localhost:5000"


# Routes système (health, favicon, robots, sitemap, Google Search Console)
from routes.system_routes import register_system_routes, router as system_router
app.include_router(system_router)
register_system_routes(app, _get_base_url)

# Routes auth (login API, logout)
from routes.auth_routes import register_auth_routes
register_auth_routes(app, {
    "get_demo_user": get_demo_user,
    "verify_password": verify_password,
    "log": log,
    "limiter": app.state.limiter,
})

# Routes coaches (API /api/coaches)
from routes.coach_routes import register_coach_routes
register_coach_routes(app, {
    "load_demo_users": load_demo_users,
    "get_coaches_by_gym_id": get_coaches_by_gym,
    "log": log,
})

# Token signup coach : signé pour être validable sur n'importe quelle instance (Render)
def _signup_token_secret() -> str:
    return (os.environ.get("SUPABASE_JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or os.environ.get("SITE_URL") or "fitmatch-signup")[:64]


def _create_signup_token(email: str) -> str:
    """Token signé (5 min) : encodage URL-safe pour passer dans l'URL."""
    expiry = int((datetime.now() + timedelta(minutes=5)).timestamp())
    payload = f"{email}|{expiry}"
    secret = _signup_token_secret()
    sig = hashlib.sha256((payload + secret).encode()).hexdigest()[:32]
    import base64
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().replace("=", "")
    return f"{b64}.{sig}"


def _validate_signup_token(token: str) -> Optional[str]:
    """Valide le token et retourne l'email (fonctionne sur toute instance)."""
    if not token or "." not in token:
        return None
    try:
        import base64
        b64, sig = token.split(".", 1)
        pad = (4 - len(b64) % 4) % 4
        b64 += "=" * pad
        payload = base64.urlsafe_b64decode(b64).decode("utf-8")
        email, expiry_str = payload.rsplit("|", 1)
        if int(expiry_str) < int(datetime.now().timestamp()):
            return None
        secret = _signup_token_secret()
        expected = hashlib.sha256((payload + secret).encode()).hexdigest()[:32]
        if sig != expected:
            return None
        return email.strip()
    except Exception:
        return None


def _set_session_cookie(response: Response, email: str, request: Request) -> None:
    """Met le cookie session_token (token sécurisé HMAC-SHA256)."""
    from auth_utils import generate_session_token
    unique_token = generate_session_token(email)
    base = _get_base_url(request)
    use_secure = os.environ.get("REPLIT_DEPLOYMENT") == "1" or (base or "").lower().startswith("https")
    response.set_cookie(
        key="session_token",
        value=unique_token,
        path="/",
        httponly=True,
        secure=use_secure,
        samesite="lax",
        max_age=86400 * 30,
    )

# Vérification production : PostgreSQL requis
if not os.environ.get("DATABASE_URL"):
    log.warning(f"DATABASE_URL non défini : la base de données est requise. Utilisateurs et réservations ne seront pas persistés.")

# Helper function pour charger les coaches depuis JSON
def load_coaches_from_json() -> List[Dict]:
    """Charge les coaches depuis le fichier JSON statique."""
    import json
    import os
    coaches_file = os.path.join("static", "data", "coaches.json")
    if os.path.exists(coaches_file):
        with open(coaches_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def get_gym_by_id(gym_id: str) -> Optional[Dict]:
    """Récupère les infos d'une salle par son ID (locale JSON ou Google Places)."""
    import json
    import os
    
    # 1. Chercher dans les salles locales (gyms.json)
    gyms_file = os.path.join("static", "data", "gyms.json")
    if os.path.exists(gyms_file):
        with open(gyms_file, 'r', encoding='utf-8') as f:
            local_gyms = json.load(f)
            gym = next((g for g in local_gyms if g["id"] == gym_id), None)
            if gym:
                return gym
    
    # 2. Si c'est un ID Google Places, chercher dans les selected_gyms_data des coaches
    if gym_id.startswith("google_worldwide_"):
        demo_users = load_demo_users()
        for email, user_data in demo_users.items():
            if user_data.get("role") == "coach":
                selected_gyms_data = user_data.get("selected_gyms_data", "[]")
                try:
                    if isinstance(selected_gyms_data, str):
                        selected_gyms = json.loads(selected_gyms_data)
                    else:
                        selected_gyms = selected_gyms_data if isinstance(selected_gyms_data, list) else []
                    
                    # Chercher cette salle dans les gyms de ce coach
                    for gym in selected_gyms:
                        if isinstance(gym, dict) and gym.get("id") == gym_id:
                            # Formater pour correspondre au format des salles locales
                            return {
                                "id": gym.get("id"),
                                "name": gym.get("name", "Salle de sport"),
                                "address": gym.get("address", ""),
                                "city": gym.get("city", ""),
                                "postal_code": "",  # Google Places n'a pas toujours le CP
                                "lat": gym.get("lat"),
                                "lng": gym.get("lng"),
                                "chain": gym.get("chain", "Google Places"),
                                "phone": gym.get("phone", "Non disponible"),
                                "hours": gym.get("hours", "Horaires non disponibles"),
                                "photo": "/static/gym-default.jpg"
                            }
                except Exception:
                    continue
    
    return None

def get_gyms_by_ids(gym_ids: List[str]) -> Dict[str, Dict]:
    """Récupère plusieurs salles en une seule passe (évite N+1). Retourne {gym_id: gym_data}."""
    if not gym_ids:
        return {}
    result = {}
    # 1. Salles locales (gyms.json)
    gyms_file = os.path.join("static", "data", "gyms.json")
    if os.path.exists(gyms_file):
        with open(gyms_file, 'r', encoding='utf-8') as f:
            local_gyms = json.load(f)
            by_id = {g["id"]: g for g in local_gyms if g.get("id")}
            for gid in gym_ids:
                if gid in by_id and gid not in result:
                    result[gid] = by_id[gid]
    # 2. IDs Google Places restants
    remaining = [gid for gid in gym_ids if gid not in result and gid.startswith("google_worldwide_")]
    if remaining:
        demo_users = load_demo_users()
        for email, user_data in demo_users.items():
            if user_data.get("role") != "coach":
                continue
            selected_gyms_data = user_data.get("selected_gyms_data", "[]")
            try:
                selected_gyms = json.loads(selected_gyms_data) if isinstance(selected_gyms_data, str) else (selected_gyms_data or [])
            except Exception:
                selected_gyms = []
            for gym in selected_gyms:
                if isinstance(gym, dict) and gym.get("id") in remaining:
                    gid = gym["id"]
                    if gid not in result:
                        result[gid] = {
                            "id": gym.get("id"),
                            "name": gym.get("name", "Salle de sport"),
                            "address": gym.get("address", ""),
                            "city": gym.get("city", ""),
                            "postal_code": "",
                            "lat": gym.get("lat"),
                            "lng": gym.get("lng"),
                            "chain": gym.get("chain", "Google Places"),
                            "phone": gym.get("phone", "Non disponible"),
                            "hours": gym.get("hours", "Horaires non disponibles"),
                            "photo": "/static/gym-default.jpg"
                        }
    return result

def get_coaches_count_by_gym_ids(gym_ids: List[str]) -> Dict[str, int]:
    """Compte les coachs par salle en une seule passe (évite N+1). Retourne {gym_id: count}."""
    if not gym_ids:
        return {}
    gym_ids_set = set(gym_ids)
    counts = {gid: 0 for gid in gym_ids}
    gym_name_by_id = {}
    gyms_file = os.path.join("static", "data", "gyms.json")
    if os.path.exists(gyms_file):
        with open(gyms_file, 'r', encoding='utf-8') as f:
            for g in json.load(f):
                if g.get("id") in gym_ids_set:
                    gym_name_by_id[g["id"]] = (g.get("name") or "").lower().strip()
    coaches_from_json = load_coaches_from_json()
    seen_json = set()
    for coach in coaches_from_json:
        for gid in coach.get("gyms", []):
            if gid in gym_ids_set and (coach.get("email") or coach.get("id"), gid) not in seen_json:
                seen_json.add((coach.get("email") or coach.get("id"), gid))
                counts[gid] = counts.get(gid, 0) + 1
    demo_users = load_demo_users()
    seen_demo = set()
    for email, user_data in demo_users.items():
        if user_data.get("role") != "coach" or not user_data.get("profile_completed"):
            continue
        sub = user_data.get("subscription_status", "")
        if sub in ("blocked", "cancelled", "past_due"):
            continue
        selected_gyms_data = user_data.get("selected_gyms_data", "[]")
        try:
            selected_gyms = json.loads(selected_gyms_data) if isinstance(selected_gyms_data, str) else (selected_gyms_data or [])
        except Exception:
            selected_gyms = []
        for gym in selected_gyms:
            if not isinstance(gym, dict):
                continue
            gid = gym.get("id", "")
            if gid not in gym_ids_set or (email, gid) in seen_demo:
                continue
            gym_name = (gym.get("name") or "").lower().strip()
            gym_static_name = gym_name_by_id.get(gid, "")
            if gym.get("id") == gid or (gym_static_name and gym_name == gym_static_name):
                seen_demo.add((email, gid))
                counts[gid] = counts.get(gid, 0) + 1
    return counts

def get_coaches_by_gym_id(gym_id: str) -> List[Dict]:
    """Récupère tous les coachs d'une salle spécifique depuis le JSON ET la base de données."""
    # 1. Charger les coachs de test depuis JSON
    coaches_from_json = load_coaches_from_json()
    json_coaches = [coach for coach in coaches_from_json if gym_id in coach.get("gyms", [])]
    
    # 2. Récupérer le nom de la salle pour matching
    gym_name = None
    gyms_file = os.path.join("static", "data", "gyms.json")
    if os.path.exists(gyms_file):
        with open(gyms_file, 'r', encoding='utf-8') as f:
            all_gyms = json.load(f)
            gym_info = next((g for g in all_gyms if g["id"] == gym_id), None)
            if gym_info:
                gym_name = gym_info.get("name", "").lower().strip()
    
    # 3. Charger les coachs depuis la base de données
    real_coaches = []
    demo_users = load_demo_users()
    
    for email, user_data in demo_users.items():
        # Exclure les coaches bloqués ou sans abonnement actif
        subscription_status = user_data.get("subscription_status", "")
        is_blocked = subscription_status in ["blocked", "cancelled", "past_due"]
        
        # Vérifier si c'est un coach avec profil complété et abonnement actif
        if user_data.get("role") == "coach" and user_data.get("profile_completed") and not is_blocked:
            # selected_gyms_data est stocké en STRING JSON, il faut le parser
            selected_gyms_data = user_data.get("selected_gyms_data", "[]")
            
            # Parser le JSON string
            try:
                if isinstance(selected_gyms_data, str):
                    selected_gyms = json.loads(selected_gyms_data)
                else:
                    selected_gyms = selected_gyms_data if isinstance(selected_gyms_data, list) else []
            except Exception:
                selected_gyms = []
            
            # Vérifier si ce coach entraîne dans cette salle (match par ID ou par NOM)
            gym_match = False
            gym_ids = []
            
            for gym in selected_gyms:
                if isinstance(gym, dict):
                    gym_ids.append(gym.get("id", ""))
                    
                    # Match par ID direct
                    if gym.get("id") == gym_id:
                        gym_match = True
                        break
                    
                    # Match par nom de salle (pour compatibilité Google Places vs JSON local)
                    if gym_name and gym.get("name", "").lower().strip() == gym_name:
                        gym_match = True
                        break
            
            if gym_match:
                # Construire un objet coach pour l'affichage
                coach_obj = {
                    "id": email.replace("@", "_").replace(".", "_"),  # ID unique basé sur email
                    "email": email,  # Email réel pour les réservations
                    "full_name": user_data.get("full_name", "Coach"),
                    "photo": user_data.get("profile_photo_url", user_data.get("photo", "/static/default-avatar.jpg")),
                    "verified": user_data.get("verified", False),
                    "rating": user_data.get("rating", 5.0),
                    "reviews_count": user_data.get("reviews_count", 0),
                    "specialties": user_data.get("specialties", []),
                    "price_from": user_data.get("price_from", 50),
                    "bio": user_data.get("bio", ""),
                    "city": user_data.get("city", ""),
                    "gyms": gym_ids  # Liste des IDs de salles
                }
                real_coaches.append(coach_obj)
    
    # 4. Combiner sans doublon par email (priorité DB)
    seen_emails = {c.get("email") for c in real_coaches if c.get("email")}
    for c in json_coaches:
        ej = c.get("email")
        if not ej:
            ej = (c.get("id") or "").replace("_at_", "@").replace("_", ".")
        if ej and ej not in seen_emails:
            seen_emails.add(ej)
            real_coaches.append(c)
    return real_coaches

# Configuration sécurisée - plus de stockage local, utilisation de Supabase Storage uniquement

# Configuration pour upload d'images
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
THUMBNAIL_SIZE = 600
THUMBNAIL_QUALITY = 80
UPLOAD_DIR = "transformations"

# Fonctions utilitaires pour l'upload d'images
def validate_image_file(file: UploadFile) -> Tuple[bool, str]:
    """Valide le type MIME et la taille d'un fichier image avec validation serveur robuste."""
    # Lire le contenu du fichier
    content = file.file.read()
    file.file.seek(0)  # Remettre à zéro pour réutilisation
    
    # Vérifier la taille avant traitement
    if len(content) > MAX_IMAGE_SIZE:
        return False, "Fichier trop volumineux. Maximum 5MB autorisé."
    
    # Validation robuste côté serveur avec Pillow - ignore le MIME client
    try:
        image = Image.open(io.BytesIO(content))
        image.verify()  # Vérifier l'intégrité de l'image
        
        # Vérifier que c'est un format supporté
        if image.format not in ['JPEG', 'PNG']:
            return False, "Format non supporté. Utilisez JPEG ou PNG uniquement."
            
        return True, ""
    except Exception:
        # Toute erreur Pillow signifie un fichier invalide
        return False, "Fichier image invalide ou corrompu."

def sanitize_coach_id(coach_id: str) -> str:
    """Sanitise l'ID coach pour éviter les attaques path traversal."""
    import re
    # Accepter seulement alphanumériques, tirets et underscores, max 64 caractères
    if not re.match(r'^[a-zA-Z0-9_-]{1,64}$', str(coach_id)):
        # Si invalide, utiliser un hash sécurisé
        return hashlib.sha256(str(coach_id).encode()).hexdigest()[:16]
    return str(coach_id)

def process_image_for_upload(image_content: bytes, coach_id: str) -> Tuple[bytes, bytes, str]:
    """Traite une image pour créer l'originale et le thumbnail."""
    # Sanitiser le coach_id pour éviter path traversal
    safe_coach_id = sanitize_coach_id(coach_id)
    
    # Générer un nom de fichier unique
    unique_id = str(uuid.uuid4())
    filename = f"{safe_coach_id}/{unique_id}.jpg"
    
    # Ouvrir l'image avec Pillow
    image = Image.open(io.BytesIO(image_content))
    
    # Convertir en RGB si nécessaire (pour PNG avec transparence)
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
        image = background
    
    # Créer l'image originale optimisée
    original_buffer = io.BytesIO()
    image.save(original_buffer, format='JPEG', quality=90, optimize=True)
    original_content = original_buffer.getvalue()
    
    # Créer le thumbnail
    thumbnail = image.copy()
    thumbnail.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
    
    thumbnail_buffer = io.BytesIO()
    thumbnail.save(thumbnail_buffer, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
    thumbnail_content = thumbnail_buffer.getvalue()
    
    return original_content, thumbnail_content, filename

async def upload_to_supabase_storage(supabase_client, content: bytes, filename: str) -> Optional[str]:
    """Upload un fichier vers Supabase Storage et retourne l'URL publique."""
    try:
        # Upload vers le bucket transformations
        supabase_client.storage.from_("transformations").upload(
            filename, content, 
            file_options={"content-type": "image/jpeg", "upsert": True}
        )
        
        # Récupérer l'URL publique
        url_response = supabase_client.storage.from_("transformations").get_public_url(filename)
        
        if hasattr(url_response, 'get'):
            return url_response.get("data", {}).get("publicUrl")
        else:
            return str(url_response)
    except Exception as e:
        log.info(f"Erreur upload Supabase Storage: {e}")
        return None

# Exception handler pour rediriger automatiquement les utilisateurs non connectés
@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """Redirige vers /login pour les pages web, retourne JSON pour les API."""
    if exc.status_code == 401:
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=401,
                content={"detail": exc.detail or "Authentification requise"}
            )
        return RedirectResponse(url="/login", status_code=303)
    return exc

# Configuration des templates et fichiers statiques (chemins absolus pour Render)
_BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))
templates.env.filters["tojson"] = lambda v: __import__("json").dumps(v, ensure_ascii=False) if v is not None else "null"
def _get_csp_nonce(request: Request) -> str:
    """Retourne le nonce CSP pour les scripts (évite unsafe-inline)."""
    return getattr(request.state, "csp_nonce", "")
templates.env.globals["get_csp_nonce"] = _get_csp_nonce

# Injecter csp_nonce dans tous les templates pour CSP
_original_template_response = templates.TemplateResponse
def _template_response_with_csp(name, context, **kwargs):
    ctx = dict(context)
    req = ctx.get("request")
    ctx["csp_nonce"] = getattr(req.state, "csp_nonce", "") if req else ""
    return _original_template_response(name, ctx, **kwargs)
templates.TemplateResponse = _template_response_with_csp
templates.env.globals["site_url"] = (settings.SITE_URL or "https://fitmatch.fr").rstrip("/")
try:
    from config import get_maps_api_key
    templates.env.globals["google_maps_api_key"] = get_maps_api_key() or ""
except Exception:
    templates.env.globals["google_maps_api_key"] = os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_PLACES_API_KEY") or ""
_static_dir = _BASE_DIR / "static"
_assets_dir = _BASE_DIR / "attached_assets"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
if _assets_dir.exists():
    app.mount("/attached_assets", StaticFiles(directory=str(_assets_dir)), name="attached_assets")
_uploads_dir = _BASE_DIR / "uploads"
os.makedirs(_uploads_dir, exist_ok=True)
if _uploads_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

# Client Supabase anonyme (si disponible)
supabase_anon = get_supabase_anon_client()


# Intervalle des rappels en secondes (toutes les 60 s par défaut)
REMINDERS_LOOP_INTERVAL = int(os.environ.get("REMINDERS_INTERVAL_SEC", "60"))


def _reminders_loop():
    """Boucle en arrière-plan : envoie les rappels dus toutes les REMINDERS_LOOP_INTERVAL secondes."""
    while True:
        try:
            n = process_due_reminders()
            if n > 0:
                log.info(f"[Rappels] {datetime.now().isoformat()} – {n} rappel(s) envoyé(s)")
        except Exception as e:
            log.info(f"[Rappels] Erreur: {e}")
        time.sleep(REMINDERS_LOOP_INTERVAL)


@app.on_event("startup")
def startup_check_database():
    """En production, PostgreSQL (DATABASE_URL) et JWT_SECRET sont requis. En local, démarrage sans DB autorisé."""
    try:
        log.info("🔄 Démarrage FitMatch...")
        try:
            from monitoring import init_sentry
            if init_sentry():
                log.info("✅ Sentry initialisé")
        except Exception:
            pass
        ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
        if ENVIRONMENT == "production":
            jwt_secret = os.environ.get("JWT_SECRET_KEY") or os.environ.get("SUPABASE_JWT_SECRET")
            if not jwt_secret or jwt_secret == "fitmatch-session-secret":
                log.error("JWT_SECRET_KEY ou SUPABASE_JWT_SECRET requis en production.")
                sys.exit(1)
        db_url = os.environ.get("DATABASE_URL")
        if not db_url or not db_url.strip():
            if ENVIRONMENT == "production":
                log.error("DATABASE_URL est requis en production.")
                sys.stdout.flush()
                sys.stderr.flush()
                sys.exit(1)
            else:
                log.warning("DATABASE_URL non défini : mode développement sans base de données.")
                log.info("Mode développement : démarrage sans base de données.")
                return
        # Démarrer le thread des rappels (24h/2h) pour envoi des emails en continu
        t = threading.Thread(target=_reminders_loop, daemon=True)
        t.start()
        log.info(f"✅ Rappels démarrés (toutes les {REMINDERS_LOOP_INTERVAL}s)")
        # Log config Stripe / Maps (sans exposer les secrets)
        try:
            from config import log_config_at_startup
            log_config_at_startup(log.info)
        except Exception:
            pass
    except Exception as e:
        log.error(f"Erreur au démarrage: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        sys.exit(1)


# Cache en mémoire pour les codes OTP (email -> code)
demo_otp_cache = {}
# Cache pour mapper les tokens de session aux emails (token -> email)
demo_token_map = {}

# Base de données nationale des salles de sport
GYMS_DATABASE = [
    # RÉGION PARISIENNE
    {"id": "bf_coigniere", "name": "Basic-Fit Coignières", "chain": "Basic-Fit", "lat": 48.7392, "lng": 1.9127, "address": "Centre Commercial Auchan, 78310 Coignières", "city": "Coignières"},
    {"id": "bf_plaisir", "name": "Basic-Fit Plaisir", "chain": "Basic-Fit", "lat": 48.8247, "lng": 1.9504, "address": "Avenue du Général de Gaulle, 78370 Plaisir", "city": "Plaisir"},
    {"id": "bf_versailles", "name": "Basic-Fit Versailles", "chain": "Basic-Fit", "lat": 48.8014, "lng": 2.1301, "address": "Boulevard de la Reine, 78000 Versailles", "city": "Versailles"},
    {"id": "fp_saint_quentin", "name": "Fitness Park Saint-Quentin-en-Yvelines", "chain": "Fitness Park", "lat": 48.7838, "lng": 2.0482, "address": "Place Georges Pompidou, 78180 Montigny-le-Bretonneux", "city": "Montigny-le-Bretonneux"},
    {"id": "fp_velizy", "name": "Fitness Park Vélizy", "chain": "Fitness Park", "lat": 48.7804, "lng": 2.1889, "address": "Centre Commercial Vélizy 2, 78140 Vélizy-Villacoublay", "city": "Vélizy-Villacoublay"},
    {"id": "bf_trappes", "name": "Basic-Fit Trappes", "chain": "Basic-Fit", "lat": 48.7765, "lng": 2.0079, "address": "Centre Commercial Auchan, 78190 Trappes", "city": "Trappes"},
    {"id": "keep_cool_mantes", "name": "Keep Cool Mantes-la-Jolie", "chain": "Keep Cool", "lat": 49.0014, "lng": 1.7168, "address": "Avenue du Maréchal Juin, 78200 Mantes-la-Jolie", "city": "Mantes-la-Jolie"},
    {"id": "l_orange_bleue_rambouillet", "name": "L'Orange Bleue Rambouillet", "chain": "L'Orange Bleue", "lat": 48.6436, "lng": 1.8287, "address": "Zone d'activité des Closeaux, 78120 Rambouillet", "city": "Rambouillet"},

    # PARIS CENTRE - 1er, 2ème, 3ème, 4ème arrondissements
    {"id": "neoness_chatelet", "name": "Neoness Châtelet", "chain": "Neoness", "lat": 48.8584, "lng": 2.3470, "address": "Forum des Halles, 75001 Paris", "city": "Paris"},
    {"id": "club_med_gym_rivoli", "name": "Club Med Gym Rivoli", "chain": "Club Med Gym", "lat": 48.8606, "lng": 2.3376, "address": "2 Place du Châtelet, 75001 Paris", "city": "Paris"},
    {"id": "cmg_one_marais", "name": "CMG Sports Club One Marais", "chain": "CMG Sports Club", "lat": 48.8566, "lng": 2.3522, "address": "10 rue de Turenne, 75004 Paris", "city": "Paris"},

    # PARIS OUEST - 15ème, 16ème, 17ème arrondissements  
    {"id": "fp_paris_theatre", "name": "Fitness Park Paris-Théâtre", "chain": "Fitness Park", "lat": 48.8407, "lng": 2.2936, "address": "104 bis rue du Théâtre, 75015 Paris", "city": "Paris"},
    {"id": "keepcool_paris15", "name": "Keepcool Paris 15 Convention", "chain": "Keep Cool", "lat": 48.8423, "lng": 2.2963, "address": "59 Rue Gutenberg, 75015 Paris", "city": "Paris"},
    {"id": "neoness_motte_picquet", "name": "Neoness La Motte-Picquet", "chain": "Neoness", "lat": 48.8506, "lng": 2.3026, "address": "15 rue de La Motte-Picquet, 75015 Paris", "city": "Paris"},
    {"id": "cmg_grenelle", "name": "CMG Sports Club One Grenelle", "chain": "CMG Sports Club", "lat": 48.8450, "lng": 2.2985, "address": "8 rue Frémicourt, 75015 Paris", "city": "Paris"},
    {"id": "cercles_porte_versailles", "name": "Cercles de la Forme Porte de Versailles", "chain": "Cercles de la Forme", "lat": 48.8353, "lng": 2.2886, "address": "31, rue du Hameau, 75015 Paris", "city": "Paris"},
    {"id": "front_de_seine", "name": "Front de Seine", "chain": "Indépendant", "lat": 48.8487, "lng": 2.2835, "address": "44 rue Émeriau, 75015 Paris", "city": "Paris"},
    {"id": "cmg_trocadero", "name": "CMG Sports Club One Trocadéro", "chain": "CMG Sports Club", "lat": 48.8620, "lng": 2.2870, "address": "35 avenue Kléber, 75016 Paris", "city": "Paris"},
    {"id": "fitness_park_ternes", "name": "Fitness Park Ternes", "chain": "Fitness Park", "lat": 48.8783, "lng": 2.2967, "address": "208 rue de Courcelles, 75017 Paris", "city": "Paris"},

    # PARIS EST - 19ème, 20ème arrondissements
    {"id": "keep_cool_belleville", "name": "Keep Cool Belleville", "chain": "Keep Cool", "lat": 48.8728, "lng": 2.3831, "address": "52 rue de Belleville, 75019 Paris", "city": "Paris"},
    {"id": "neoness_pere_lachaise", "name": "Neoness Père Lachaise", "chain": "Neoness", "lat": 48.8566, "lng": 2.3915, "address": "147 avenue Parmentier, 75020 Paris", "city": "Paris"},
    {"id": "forest_hill_menilmontant", "name": "Forest Hill Ménilmontant", "chain": "Forest Hill", "lat": 48.8642, "lng": 2.3855, "address": "17 rue Boyer, 75020 Paris", "city": "Paris"},

    # HAUTS-DE-SEINE (92)
    {"id": "bf_issy", "name": "Basic-Fit Issy-les-Moulineaux", "chain": "Basic-Fit", "lat": 48.8247, "lng": 2.2725, "address": "2 rue Rouget de Lisle, 92130 Issy-les-Moulineaux", "city": "Issy-les-Moulineaux"},

    # SEINE-SAINT-DENIS (93)
    {"id": "basic_fit_bobigny", "name": "Basic-Fit Bobigny", "chain": "Basic-Fit", "lat": 48.9127, "lng": 2.4494, "address": "Centre Commercial Bobigny 2, 93000 Bobigny", "city": "Bobigny"},
    {"id": "fitness_park_saint_denis", "name": "Fitness Park Saint-Denis", "chain": "Fitness Park", "lat": 48.9362, "lng": 2.3574, "address": "8 rue du Landy, 93200 Saint-Denis", "city": "Saint-Denis"},
    {"id": "keep_cool_montreuil", "name": "Keep Cool Montreuil", "chain": "Keep Cool", "lat": 48.8644, "lng": 2.4530, "address": "128 avenue de la Résistance, 93100 Montreuil", "city": "Montreuil"},

    # VAL-DE-MARNE (94)
    {"id": "basic_fit_creteil", "name": "Basic-Fit Créteil", "chain": "Basic-Fit", "lat": 48.7900, "lng": 2.4656, "address": "Centre Commercial Créteil Soleil, 94000 Créteil", "city": "Créteil"},
    {"id": "fitness_park_vincennes", "name": "Fitness Park Vincennes", "chain": "Fitness Park", "lat": 48.8467, "lng": 2.4378, "address": "43 rue de Fontenay, 94300 Vincennes", "city": "Vincennes"},

    # NORD (59) - Lille et région
    {"id": "basic_fit_lille_centre", "name": "Basic-Fit Lille Centre", "chain": "Basic-Fit", "lat": 50.6292, "lng": 3.0573, "address": "15 rue Nationale, 59000 Lille", "city": "Lille"},
    {"id": "keep_cool_lille", "name": "Keep Cool Lille", "chain": "Keep Cool", "lat": 50.6365, "lng": 3.0635, "address": "89 rue du Molinel, 59000 Lille", "city": "Lille"},
    {"id": "fitness_park_villeneuve", "name": "Fitness Park Villeneuve d'Ascq", "chain": "Fitness Park", "lat": 50.6184, "lng": 3.1474, "address": "Centre Commercial V2, 59650 Villeneuve-d'Ascq", "city": "Villeneuve-d'Ascq"},
    {"id": "neoness_lille_flandres", "name": "Neoness Lille Flandres", "chain": "Neoness", "lat": 50.6372, "lng": 3.0700, "address": "Gare Lille Flandres, 59000 Lille", "city": "Lille"},
    {"id": "orange_bleue_tourcoing", "name": "L'Orange Bleue Tourcoing", "chain": "L'Orange Bleue", "lat": 50.7262, "lng": 3.1615, "address": "132 rue de Tournai, 59200 Tourcoing", "city": "Tourcoing"},

    # RHÔNE (69) - Lyon et région
    {"id": "basic_fit_lyon_part_dieu", "name": "Basic-Fit Lyon Part-Dieu", "chain": "Basic-Fit", "lat": 45.7608, "lng": 4.8567, "address": "Centre Commercial Part-Dieu, 69003 Lyon", "city": "Lyon"},
    {"id": "keep_cool_lyon", "name": "Keep Cool Lyon", "chain": "Keep Cool", "lat": 45.7640, "lng": 4.8357, "address": "45 cours Gambetta, 69003 Lyon", "city": "Lyon"},
    {"id": "fitness_park_lyon", "name": "Fitness Park Lyon", "chain": "Fitness Park", "lat": 45.7489, "lng": 4.8467, "address": "112 rue de la République, 69002 Lyon", "city": "Lyon"},
    {"id": "cmg_lyon_bellecour", "name": "CMG Sports Club Lyon Bellecour", "chain": "CMG Sports Club", "lat": 45.7578, "lng": 4.8320, "address": "2 place Bellecour, 69002 Lyon", "city": "Lyon"},
    {"id": "neoness_lyon_perrache", "name": "Neoness Lyon Perrache", "chain": "Neoness", "lat": 45.7494, "lng": 4.8265, "address": "Gare de Perrache, 69002 Lyon", "city": "Lyon"},

    # BOUCHES-DU-RHÔNE (13) - Marseille et région
    {"id": "basic_fit_marseille_centre", "name": "Basic-Fit Marseille Centre", "chain": "Basic-Fit", "lat": 43.2965, "lng": 5.3698, "address": "47 La Canebière, 13001 Marseille", "city": "Marseille"},
    {"id": "keep_cool_marseille", "name": "Keep Cool Marseille", "chain": "Keep Cool", "lat": 43.3047, "lng": 5.3806, "address": "232 avenue du Prado, 13008 Marseille", "city": "Marseille"},
    {"id": "fitness_park_marseille", "name": "Fitness Park Marseille", "chain": "Fitness Park", "lat": 43.2922, "lng": 5.3656, "address": "Centre Bourse, 13001 Marseille", "city": "Marseille"},
    {"id": "orange_bleue_aix", "name": "L'Orange Bleue Aix-en-Provence", "chain": "L'Orange Bleue", "lat": 43.5263, "lng": 5.4454, "address": "765 avenue de la Grande Bégude, 13100 Aix-en-Provence", "city": "Aix-en-Provence"},

    # HAUTE-GARONNE (31) - Toulouse et région
    {"id": "basic_fit_toulouse_centre", "name": "Basic-Fit Toulouse Centre", "chain": "Basic-Fit", "lat": 43.6047, "lng": 1.4442, "address": "39 rue d'Alsace-Lorraine, 31000 Toulouse", "city": "Toulouse"},
    {"id": "keep_cool_toulouse", "name": "Keep Cool Toulouse", "chain": "Keep Cool", "lat": 43.6108, "lng": 1.4544, "address": "123 avenue de Muret, 31300 Toulouse", "city": "Toulouse"},
    {"id": "fitness_park_toulouse", "name": "Fitness Park Toulouse", "chain": "Fitness Park", "lat": 43.6029, "lng": 1.4486, "address": "Centre Commercial Saint-Georges, 31000 Toulouse", "city": "Toulouse"},

    # LOIRE-ATLANTIQUE (44) - Nantes et région
    {"id": "basic_fit_nantes_centre", "name": "Basic-Fit Nantes Centre", "chain": "Basic-Fit", "lat": 47.2184, "lng": -1.5536, "address": "15 rue de Strasbourg, 44000 Nantes", "city": "Nantes"},
    {"id": "keep_cool_nantes", "name": "Keep Cool Nantes", "chain": "Keep Cool", "lat": 47.2073, "lng": -1.5334, "address": "8 boulevard de Berlin, 44000 Nantes", "city": "Nantes"},
    {"id": "fitness_park_nantes", "name": "Fitness Park Nantes", "chain": "Fitness Park", "lat": 47.2159, "lng": -1.5541, "address": "Centre Commercial Beaulieu, 44000 Nantes", "city": "Nantes"}
]

# IDs de salles valides pour validation
VALID_GYM_IDS = {gym["id"] for gym in GYMS_DATABASE}

def validate_selected_gyms(selected_gyms_str: str) -> List[str]:
    """Valide et nettoie la liste des salles sélectionnées."""
    if not selected_gyms_str:
        return []
    
    try:
        import json
        selected_gyms = json.loads(selected_gyms_str)
        if not isinstance(selected_gyms, list):
            return []
        
        # Filtrer seulement les IDs valides
        valid_gyms = [gym_id for gym_id in selected_gyms if isinstance(gym_id, str) and gym_id in VALID_GYM_IDS]
        return valid_gyms[:10]  # Limiter à 10 salles max
        
    except json.JSONDecodeError:
        return []
    except Exception:
        return []

# Fonction de validation du mot de passe
def is_valid_password(password: str) -> bool:
    """Valide qu'un mot de passe respecte les critères de sécurité.
    
    Critères: Au moins 8 caractères, une lettre et un chiffre.
    """
    import re
    # Au moins 8 caractères, une lettre et un chiffre (autorisant caractères spéciaux)
    return bool(re.match(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$', password))

# Helper functions pour l'authentification
def get_current_user(session_token: Optional[str] = Cookie(None)):
    """Récupère l'utilisateur connecté via le token de session."""
    if not session_token or not isinstance(session_token, str):
        return None
    session_token = session_token.strip()
    if len(session_token) < 10:
        return None

    # Toujours reconnaître le token demo_ (inscription coach, signup-reservation, etc.)
    # même si Supabase est configuré, pour que /coach/subscription soit accessible après signup.
    if session_token.startswith("demo_"):
        from utils import load_demo_users, get_demo_user
        from auth_utils import get_email_from_session_token
        if session_token in demo_token_map:
            email = demo_token_map[session_token]
            fresh_user_data = get_demo_user(email)
            if fresh_user_data:
                fresh_user_data["_access_token"] = session_token
                fresh_user_data["email"] = email
                return fresh_user_data
        email = get_email_from_session_token(session_token, load_demo_users)
        if email:
            fresh_user_data = get_demo_user(email)
            if fresh_user_data:
                fresh_user_data["_access_token"] = session_token
                fresh_user_data["email"] = email
                return fresh_user_data
        return None

    # Supabase/JWT : uniquement si pas de token demo_
    if not supabase_anon:
        return None
    try:
        jwt_secret = settings.get_jwt_secret()
        if jwt_secret:
            decoded_token = jwt.decode(
                session_token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_exp": True},
            )
        else:
            if settings.IS_PRODUCTION:
                log.warning(f"SUPABASE_JWT_SECRET ou JWT_SECRET_KEY non défini : vérification JWT désactivée (risque sécurité).")
            decoded_token = jwt.decode(session_token, options={"verify_signature": False})
        user_id = decoded_token.get("sub")
        
        if not user_id:
            log.error(f" Token JWT invalide (pas d'ID utilisateur)")
            return None
            
        # Créer un client authentifié pour respecter les politiques RLS
        user_supabase = get_supabase_client_for_user(session_token)
        if not user_supabase:
            log.error(f" Impossible de créer le client authentifié")
            return None
            
        # Charger le profil directement depuis la table profiles
        profile = get_user_profile(user_supabase, user_id)
        if profile:
            profile["_access_token"] = session_token  # Garder le token pour les futures requêtes
            log.info(f"✅ Utilisateur authentifié: {profile.get('email', 'N/A')}")
            return profile
        else:
            # Profil non trouvé - créer automatiquement lors de la première connexion
            log.warning(f" Profil manquant pour utilisateur {user_id}, création automatique")
            
            # Récupérer l'email depuis le token JWT
            user_email = decoded_token.get("email")
            if not user_email:
                log.error(f" Email non trouvé dans le token")
                return None
                
            # Créer un objet utilisateur mock pour la création de profil
            mock_user = type('User', (), {
                'id': user_id,
                'email': user_email,
                'user_metadata': {}
            })()
            
            return create_profile_on_first_login(user_supabase, mock_user, session_token)
            
    except jwt.DecodeError:
        log.error(f" Token JWT mal formé")
        return None
    except Exception as e:
        log.error(f"Erreur authentification: {e}")
        return None

def create_profile_on_first_login(user_supabase, user, access_token: str):
    """Crée automatiquement un profil lors de la première connexion (cas confirmation email)."""
    try:
        # Récupérer les métadonnées utilisateur depuis Supabase auth
        user_metadata = getattr(user, 'user_metadata', {})
        
        profile_data = {
            "id": user.id,
            "role": "client",  # Toujours client par défaut pour sécurité
            "full_name": user_metadata.get("full_name", "Utilisateur"),
            "email": getattr(user, 'email', None)
        }
        
        # Créer le profil avec le client authentifié (respecte RLS)
        response = user_supabase.table("profiles").insert(profile_data).execute()
        
        if response.data:
            profile = response.data[0]
            profile["_access_token"] = access_token
            log.info(f"✅ Profil créé automatiquement lors de la première connexion pour {user.email}")
            return profile
        
        return None
    except Exception as e:
        log.error(f"Erreur création profil automatique: {e}")
        return None

def require_auth(user = Depends(get_current_user)):
    """Middleware pour routes nécessitant une authentification."""
    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Authentification requise",
            headers={"Location": "/login"}
        )
    return user

def require_coach_role(user = Depends(require_auth)):
    """Middleware pour routes réservées aux coaches."""
    if user.get("role") != "coach":
        raise HTTPException(
            status_code=403, 
            detail="Accès réservé aux coaches",
            headers={"Location": "/login"}
        )
    return user

def require_coach_or_pending(user = Depends(require_auth)):
    """Middleware pour /coach/subscription - accepte coaches avec ou sans abonnement."""
    if user.get("role") != "coach":
        raise HTTPException(
            status_code=403, 
            detail="Accès réservé aux coaches",
            headers={"Location": "/coach-login"}
        )
    return user


def get_coach_from_session_or_cookie(request: Request) -> Optional[Dict]:
    """Retourne le coach si session Starlette (cookie session) OU session_token valide."""
    # 1) Priorité : session Starlette (OTP vérifié) - cookie "session" avec user_email + is_coach
    session_email = get_session_email(request)
    is_coach = request.session.get("is_coach") is True
    if session_email and is_coach:
        user_data = get_demo_user(session_email)
        # Priorité session (profile_completed, subscription_status après finalisation) > DB/fichier
        profile_completed = request.session.get("profile_completed")
        if profile_completed is None:
            profile_completed = (user_data or {}).get("profile_completed", False)
        sub_status = request.session.get("subscription_status") or (user_data or {}).get("subscription_status", "active")
        if user_data and user_data.get("role") == "coach":
            user_data["email"] = session_email
            user_data["_access_token"] = f"session_{session_email}"
            user_data["profile_completed"] = profile_completed
            user_data["subscription_status"] = sub_status
            return user_data
        # Session valide mais user absent du cache DB : accepter quand même (créé après OTP)
        base = dict(user_data) if user_data else {}
        base.update({
            "email": session_email,
            "role": "coach",
            "profile_completed": profile_completed,
            "subscription_status": sub_status,
            "_access_token": f"session_{session_email}",
        })
        return base
    # 2) Fallback : cookie session_token (login classique)
    user = get_current_user(request.cookies.get("session_token"))
    if user and user.get("role") == "coach":
        return user
    return None


def require_coach_session_or_cookie(request: Request) -> Dict:
    """Dépendance : coach connecté via session OTP ou cookie."""
    user = get_coach_from_session_or_cookie(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentification requise")
    return user


def require_active_subscription(user = Depends(require_coach_session_or_cookie)):
    """Middleware pour routes nécessitant un abonnement actif."""
    subscription_status = user.get("subscription_status", "")
    
    # Autoriser si abonnement actif
    if subscription_status == "active":
        return user
    
    # Sinon rediriger vers la page d'abonnement
    raise HTTPException(
        status_code=303,
        detail="Abonnement requis",
        headers={"Location": "/coach/subscription"}
    )


# Routes publiques
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, response: Response):
    """Page d'accueil avec formulaire de recherche et détection de langue."""
    # Détecter la langue du visiteur
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    available_languages = get_available_languages()
    
    # Sauvegarder la langue dans un cookie
    resp = templates.TemplateResponse("index.html", {
        "request": request,
        "t": translations,
        "locale": locale,
        "available_languages": available_languages,
        "text_direction": translations.get("dir", "ltr")
    })
    resp.set_cookie(key=LOCALE_COOKIE_NAME, value=locale, max_age=31536000)  # 1 an
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

@app.get("/set-language/{locale}")
async def set_language(request: Request, locale: str):
    """Change la langue de l'utilisateur."""
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE

    referer = (request.headers.get("referer") or request.headers.get("Referer") or "").strip()
    base = str(request.base_url).rstrip("/")
    site = (os.environ.get("SITE_URL") or base).rstrip("/")
    if referer and (referer.startswith(site) or referer.startswith(base) or referer.startswith("/")):
        redirect_url = referer if referer.startswith("http") else (base + referer) if referer.startswith("/") else "/"
    else:
        redirect_url = "/"
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key=LOCALE_COOKIE_NAME, value=locale, max_age=31536000, path="/", samesite="lax")
    return response

@app.get("/search", response_class=HTMLResponse)
async def search_coaches(
    request: Request,
    specialty: Optional[str] = None,
    city: str = "",
    gym: Optional[str] = None,
    radius_km: int = 25
):
    """Recherche de coachs avec géolocalisation ou par salle."""
    
    # Si on cherche par salle spécifique - charger les VRAIS coaches
    if gym:
        coaches = get_coaches_by_gym_id(gym)
        i18n = get_i18n_context(request)
        return templates.TemplateResponse("results.html", {
            "request": request,
            "coaches": coaches,
            "specialty": None,
            "city": "",
            "gym": gym,
            "radius_km": radius_km,
            **i18n
        })
    
    # Géocoder la ville
    coords = geocode_city(city) if city else None
    user_lat, user_lng = coords if coords else (None, None)
    
    # Rechercher les coachs - VRAIS coaches depuis la base de données
    from utils import load_demo_users
    demo_users = load_demo_users()
    coaches = []
    
    for email, user_data in demo_users.items():
        # Exclure les coaches bloqués ou sans abonnement actif
        subscription_status = user_data.get("subscription_status", "")
        is_blocked = subscription_status in ["blocked", "cancelled", "past_due"]
        
        if user_data.get("role") == "coach" and user_data.get("profile_completed") and not is_blocked:
            coaches.append({
                "id": email.replace("@", "_").replace(".", "_"),
                "email": email,
                "full_name": user_data.get("full_name", "Coach"),
                "bio": user_data.get("bio", ""),
                "city": user_data.get("city", ""),
                "specialties": user_data.get("specialties", []),
                "price_from": user_data.get("price_from", 50),
                "rating": 4.5,
                "reviews_count": 10,
                "verified": True,
                "photo": user_data.get("photo", "/static/default-avatar.jpg"),
                "distance": 0.0
            })
    
    # Filtrer par spécialité si demandé
    if specialty:
        coaches = [c for c in coaches if specialty.lower() in [s.lower() for s in c.get("specialties", [])]]
    
    i18n = get_i18n_context(request)
    return templates.TemplateResponse("results.html", {
        "request": request,
        "coaches": coaches,
        "specialty": specialty,
        "city": city,
        "gym": None,
        "radius_km": radius_km,
        **i18n
    })

# Cette route sera déplacée après les routes spécifiques coach/portal, coach/specialties, etc.

# Routes d'authentification
@app.get("/client/home", response_class=HTMLResponse)
async def client_home(request: Request, user = Depends(get_current_user)):
    """Page d'accueil pour les clients avec formulaire de recherche."""
    # Si pas d'utilisateur connecté, rediriger vers la page de connexion
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    lang = get_locale_from_request(request)
    t = get_translations(lang)
    
    response = templates.TemplateResponse("client_home.html", {
        "request": request, 
        "user": user,
        "lang": lang,
        "t": t
    })
    # Désactiver le cache pour éviter les problèmes de session
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/mon-compte", response_class=HTMLResponse)
async def mon_compte(request: Request, user=Depends(get_current_user)):
    """Page compte client (réservations depuis la base)."""
    i18n = get_i18n_context(request)
    lang = i18n.get("locale", "fr")
    t = i18n.get("t", get_translations(lang))
    response = templates.TemplateResponse("client_home.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t,
        "locale": lang,
        **i18n
    })
    # Désactiver le cache pour éviter les problèmes de session
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/gyms/search", response_class=HTMLResponse)
async def gym_search_page(request: Request):
    """Page de recherche de salles de sport avec géolocalisation."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("gym_search.html", {"request": request, "t": translations, "locale": locale})

@app.get("/gyms-map", response_class=HTMLResponse)
async def gyms_map_page(request: Request, address: str = "", radius_km: int = 25):
    """Page de recherche de salles avec Google Maps. Affiche 'Maps non configuré' si clé absente."""
    try:
        from config import get_maps_api_key
        google_maps_api_key = get_maps_api_key() or ""
    except Exception:
        google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_PLACES_API_KEY") or ""
    i18n = get_i18n_context(request)
    return templates.TemplateResponse("gyms_map.html", {
        "request": request,
        "address": address,
        "radius_km": radius_km,
        "google_maps_api_key": google_maps_api_key,
        **i18n
    })

@app.get("/gym/{gym_id}", response_class=HTMLResponse)
async def gym_detail_page(request: Request, gym_id: str, name: Optional[str] = None, address: Optional[str] = None):
    """
    Page publique affichant une salle et tous ses coachs.
    🆕 Supporte les salles locales (JSON), Google Places (worldwide), et recherche par nom
    Paramètres:
    - gym_id: ID de la salle (place_id Google ou ID local)
    - name: Nom de la salle (optionnel, pour l'affichage)
    - address: Adresse de la salle (optionnel, pour l'affichage)
    """
    gym_name = name or "Salle de sport"
    gym_address = address or ""
    
    # Essayer de charger les infos de la salle (locale ou Google Places)
    gym_info = get_gym_by_id(gym_id)
    
    if gym_info:
        gym_name = gym_info.get("name", gym_name)
        gym_address = gym_info.get("address", gym_address)
    
    # Charger les coachs de cette salle (par ID ou par nom)
    coaches_found = []
    demo_users = load_demo_users()
    search_name = gym_name.lower().strip() if gym_name else None
    
    for email, user_data in demo_users.items():
        subscription_status = user_data.get("subscription_status", "")
        is_blocked = subscription_status in ["blocked", "cancelled", "past_due"]
        if user_data.get("role") == "coach" and user_data.get("profile_completed") and not is_blocked:
            selected_gyms_data = user_data.get("selected_gyms_data", "[]")
            
            try:
                if isinstance(selected_gyms_data, str):
                    selected_gyms = json.loads(selected_gyms_data)
                else:
                    selected_gyms = selected_gyms_data if isinstance(selected_gyms_data, list) else []
            except Exception:
                selected_gyms = []
            
            gym_match = False
            
            for gym in selected_gyms:
                if isinstance(gym, dict):
                    if gym.get("place_id") == gym_id or gym.get("id") == gym_id:
                        gym_match = True
                        break
                    
                    if search_name:
                        gym_name_lower = gym.get("name", "").lower().strip()
                        if search_name in gym_name_lower or gym_name_lower in search_name:
                            gym_match = True
                            break
            
            if gym_match:
                coach_obj = {
                    "id": email.replace("@", "_").replace(".", "_"),
                    "email": email,
                    "name": user_data.get("full_name", "Coach"),
                    "photo_url": user_data.get("profile_photo_url", "/static/default-avatar.jpg"),
                    "verified": user_data.get("verified", False),
                    "rating": user_data.get("rating", 5.0),
                    "review_count": user_data.get("reviews_count", 0),
                    "specialties": user_data.get("specialties", []),
                    "price": user_data.get("price_from", 40),
                    "bio": user_data.get("bio", ""),
                    "city": user_data.get("city", "")
                }
                coaches_found.append(coach_obj)
    
    # Trier par : vérifiés → note
    coaches_sorted = sorted(
        coaches_found,
        key=lambda c: (-int(c.get("verified", False)), -c.get("rating", 0))
    )
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("gym_detail.html", {
        "request": request,
        "gym_name": gym_name,
        "gym_address": gym_address,
        "gym_id": gym_id,
        "coaches": coaches_sorted,
        "t": translations,
        "locale": locale
    })

@app.get("/test-coaches", response_class=HTMLResponse)
async def test_coaches_page(request: Request):
    """Page de test pour vérifier que les VRAIS coaches sont chargés."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("test_coaches.html", {"request": request, "t": translations, "locale": locale})

@app.get("/partner", response_class=HTMLResponse)
async def partner_page(request: Request):
    """Page Devenir partenaire FitMatch Pro."""
    i18n = get_i18n_context(request)
    return templates.TemplateResponse("partner.html", {"request": request, **i18n})

# Pages marketing SEO (sitelinks Google)
@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """Page À propos."""
    i18n = get_i18n_context(request)
    base = _get_base_url(request)
    return templates.TemplateResponse("about.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/about",
        **i18n
    })

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Page Tarifs."""
    i18n = get_i18n_context(request)
    base = _get_base_url(request)
    return templates.TemplateResponse("pricing.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/pricing",
        **i18n
    })

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    """Page Projets / Case studies."""
    i18n = get_i18n_context(request)
    base = _get_base_url(request)
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/projects",
        **i18n
    })

@app.get("/blog", response_class=HTMLResponse)
async def blog_page(request: Request):
    """Page listing blog."""
    i18n = get_i18n_context(request)
    base = _get_base_url(request)
    return templates.TemplateResponse("blog.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/blog",
        **i18n
    })

@app.get("/blog/fitmatch-trouver-coach", response_class=HTMLResponse)
async def blog_article_page(request: Request):
    """Article blog : Comment FitMatch vous aide à trouver le coach idéal."""
    i18n = get_i18n_context(request)
    base = _get_base_url(request)
    return templates.TemplateResponse("blog_article.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/blog/fitmatch-trouver-coach",
        **i18n
    })

@app.get("/gyms", response_class=HTMLResponse)
async def gyms_marketing_page(request: Request):
    """Page marketing salles → redirige vers /gyms/finder."""
    i18n = get_i18n_context(request)
    base = _get_base_url(request)
    return templates.TemplateResponse("gyms_marketing.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/gyms",
        **i18n
    })

@app.get("/coaches", response_class=HTMLResponse)
async def coaches_marketing_page(request: Request):
    """Page marketing coachs → coach-signup / coach-login."""
    i18n = get_i18n_context(request)
    base = _get_base_url(request)
    return templates.TemplateResponse("coaches_marketing.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/coaches",
        **i18n
    })

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
    base = _get_base_url(request)
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "canonical_url": f"{base.rstrip('/')}/contact",
        **i18n
    })

@app.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    """Page FAQ dédiée (clients et coachs)."""
    i18n = get_i18n_context(request)
    return templates.TemplateResponse("faq.html", {"request": request, **i18n})

@app.get("/coach-signup", response_class=HTMLResponse)
async def coach_signup_page(request: Request):
    """Page d'inscription coach avec hero section."""
    i18n = get_i18n_context(request)
    return templates.TemplateResponse("coach_signup.html", {"request": request, **i18n})

@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request, role: str | None = None):
    """Formulaire d'inscription. Les coachs sont redirigés vers la page dédiée."""
    if (role or "").strip().lower() == "coach":
        return RedirectResponse(url="/coach-login?tab=signup", status_code=302)
    csrf_token = _generate_csrf_token()
    countries = get_countries_list()
    i18n = get_i18n_context(request)
    resp = templates.TemplateResponse("signup.html", {
        "request": request,
        "role": role,
        "countries": countries,
        "csrf_token": csrf_token,
        **i18n
    })
    _set_csrf_cookie(resp, csrf_token)
    return resp

@app.get("/api/test-gym-data")
async def test_gym_data_validation():
    """ENDPOINT DE TEST : Validation de la complétude des données salles nationales."""
    try:
        from utils import test_national_gym_data_completeness
        validation_results = test_national_gym_data_completeness()
        return {"success": True, "validation": validation_results}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/gyms")
async def get_gyms(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """API pour récupérer la liste des salles (pagination: limit, offset)."""
    try:
        # Récupérer un échantillon de vraies salles françaises via Data ES
        sample_gyms = []
        
        # Essayer d'abord avec search_gyms_by_zone pour avoir des vraies salles
        try:
            from utils import search_gyms_by_zone
            # Récupérer des salles populaires de différentes villes
            cities_sample = ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"]
            
            for city in cities_sample:
                city_gyms = search_gyms_by_zone(city)
                if city_gyms:
                    sample_gyms.extend(city_gyms[:10])  # Max 10 salles par ville
                    if len(sample_gyms) >= 50:  # Limiter à 50 salles au total
                        break
        except Exception as api_error:
            log.warning(f"Erreur récupération échantillon Data ES: {api_error}")
        
        # Si pas assez de salles via API, compléter avec notre base locale
        if len(sample_gyms) < 20:
            sample_gyms.extend(GYMS_DATABASE[:30])  # Ajouter jusqu'à 30 salles locales
        
        total = len(sample_gyms)
        gyms_page = sample_gyms[offset:offset + limit]
        log.info(f"API /gyms: {len(gyms_page)} salles (total {total}, offset {offset})")
        return {"gyms": gyms_page, "total": total, "limit": limit, "offset": offset}
        
    except Exception as e:
        log.error(f"Erreur /api/gyms: {e}")
        # Fallback vers base locale en cas d'erreur
        return {"gyms": GYMS_DATABASE}

@app.get("/api/user/gyms")
async def get_user_gyms(user = Depends(get_current_user)):
    """Récupère les salles préférées de l'utilisateur connecté."""
    try:
        # Vérifier l'authentification
        if not user:
            return {"success": False, "message": "Utilisateur non connecté", "selected_gyms": []}
        
        user_id = user.get("id")
        email = user.get("email")
        
        if not supabase_anon:
            # Chercher dans le stockage persistant
            user_data = get_demo_user(email)
            if user_data:
                selected_gyms_str = user_data.get("selected_gyms", "[]")
                try:
                    selected_gyms = json.loads(selected_gyms_str) if selected_gyms_str else []
                    return {"success": True, "selected_gyms": selected_gyms}
                except Exception:
                    return {"success": True, "selected_gyms": []}
            else:
                return {"success": True, "selected_gyms": []}
        else:
            # Mode Supabase - récupérer depuis la base de données
            response = supabase_anon.table("profiles").select("selected_gyms").eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                selected_gyms_str = response.data[0].get("selected_gyms")
                if selected_gyms_str:
                    try:
                        selected_gyms = json.loads(selected_gyms_str)
                        return {"success": True, "selected_gyms": selected_gyms}
                    except Exception:
                        return {"success": True, "selected_gyms": []}
                else:
                    return {"success": True, "selected_gyms": []}
            else:
                return {"success": True, "selected_gyms": []}
                
    except Exception as e:
        log.error(f"Erreur lors de la récupération des salles utilisateur: {e}")
        return {"success": False, "message": "Erreur serveur", "selected_gyms": []}

@app.post("/api/user/gyms")
async def save_user_gyms(request: Request, user = Depends(get_current_user)):
    """Sauvegarde les salles préférées de l'utilisateur connecté."""
    try:
        # Vérifier l'authentification
        if not user:
            return {"success": False, "message": "Utilisateur non connecté"}
        
        user_id = user.get("id")
        email = user.get("email")
        
        # Récupérer les données JSON de la requête
        body = await request.json()
        selected_gyms = body.get("selected_gyms", [])
        
        # Valider les salles sélectionnées
        validated_gyms = validate_selected_gyms(json.dumps(selected_gyms))
        
        if not supabase_anon:
            # Sauvegarder dans le stockage persistant
            user_data = get_demo_user(email)
            if user_data:
                user_data["selected_gyms"] = json.dumps(validated_gyms)
                save_demo_user(email, user_data)
                log.info(f"✅ Salles sauvegardées pour {email}: {validated_gyms}")
                return {"success": True, "message": "Salles sauvegardées avec succès"}
            else:
                return {"success": False, "message": "Utilisateur non trouvé"}
        else:
            # Mode Supabase - sauvegarder dans la base de données
            response = supabase_anon.table("profiles").update({
                "selected_gyms": json.dumps(validated_gyms)
            }).eq("id", user_id).execute()
            
            if response.data:
                log.info(f"✅ Salles sauvegardées en Supabase pour l'utilisateur {user_id}: {validated_gyms}")
                return {"success": True, "message": "Salles sauvegardées avec succès"}
            else:
                return {"success": False, "message": "Erreur lors de la sauvegarde"}
                
    except Exception as e:
        log.error(f"Erreur lors de la sauvegarde des salles: {e}")
        return {"success": False, "message": "Erreur serveur"}

@app.post("/signup")
@limiter.limit("8/minute")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    gender: str = Form(...),
    role: str = Form(...),
    country: str = Form(...),
    coach_gender_preference: str = Form("aucune"),
    selected_gyms: str = Form(""),
    csrf_token: Optional[str] = Form(None),
):
    """Inscription utilisateur avec système OTP par email."""
    if not _verify_csrf(request, csrf_token or request.headers.get(CSRF_HEADER_NAME)):
        return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})
    email = email.lower().strip()
    countries = get_countries_list()
    i18n = get_i18n_context(request)
    t = i18n["t"]
    pr_signup = t.get("signup", {})
    
    # Validation du mot de passe
    if not is_valid_password(password):
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": pr_signup.get("error_password_weak", "Password too weak"),
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference,
            **i18n
        }, status_code=400)
    
    if gender not in ["homme", "femme"]:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": pr_signup.get("error_gender_required", "Please select your gender"),
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference,
            **i18n
        }, status_code=400)
    
    valid_countries = [c["code"] for c in countries]
    if not country or country not in valid_countries:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": pr_signup.get("error_country_required", "Please select your country"),
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference,
            **i18n
        }, status_code=400)
    
    # Validation du rôle
    if role not in ["client", "coach"]:
        role = "client"
    
    # Générer le code OTP (6 chiffres par défaut)
    otp_code = generate_otp_code(6)
    
    if not supabase_anon:
        # Stocker le code et les infos utilisateur dans le cache
        demo_otp_cache[email] = otp_code
        # Traiter et valider les salles sélectionnées pour les clients
        selected_gyms_list = []
        if role == "client":
            selected_gyms_list = validate_selected_gyms(selected_gyms)
            if selected_gyms and not selected_gyms_list:
                log.warning(f" Salles invalides reçues pour {email}: {selected_gyms}")
                return templates.TemplateResponse("signup.html", {
                    "request": request,
                    "error": pr_signup.get("error_gyms_invalid", "Invalid gyms selected."),
                    "full_name": full_name,
                    "email": email,
                    "gender": gender,
                    "role": role,
                    "coach_gender_preference": coach_gender_preference,
                    "country_code": country,
                    "countries": countries,
                    **i18n
                }, status_code=400)
        
        user_data = {
            "full_name": full_name,
            "gender": gender,
            "role": role,
            "country_code": country,
            "password": hash_password(password.strip()),
            "coach_gender_preference": coach_gender_preference if role == "client" else None,
            "selected_gyms": selected_gyms_list if role == "client" else None,
            "lang": i18n["locale"]
        }
        save_demo_user(email, user_data)
        
        log.info(f"🔐 Code OTP généré pour {email}: {otp_code}")
        
        # Envoyer l'email avec Resend
        # Get language for email
        i18n = get_i18n_context(request)
        lang = i18n['locale']
        email_result = send_otp_email_resend(email, otp_code, full_name, lang=lang)
        
        pr_otp = t.get("verify_otp", {})
        success_message = pr_otp.get("success_otp_sent", "Verification code sent to your email")
        if email_result.get("success") and email_result.get("mode") == "resend":
            success_message += f" (Email ID: {email_result.get('email_id', 'N/A')})"
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "success": success_message,
            **i18n
        })
    
    try:
        # NOUVEAU: Utiliser le service email natif Supabase au lieu de l'OTP manuel
        
        # Valider et traiter les salles sélectionnées avant inscription
        validated_gyms = None
        if role == "client":
            validated_gyms_list = validate_selected_gyms(selected_gyms)
            if selected_gyms and not validated_gyms_list:
                log.warning(f" Salles invalides reçues pour {email}: {selected_gyms}")
                return templates.TemplateResponse("signup.html", {
                    "request": request,
                    "error": pr_signup.get("error_gyms_invalid", "Invalid gyms selected."),
                    "full_name": full_name,
                    "email": email,
                    "gender": gender,
                    "role": role,
                    "coach_gender_preference": coach_gender_preference,
                    "country_code": country,
                    "countries": countries,
                    **i18n
                }, status_code=400)
            # Convertir en JSON pour stockage
            validated_gyms = json.dumps(validated_gyms_list) if validated_gyms_list else None
        
        # Sauvegarder les données supplémentaires en attente
        pending_stored = store_pending_registration(
            supabase_anon, 
            email, 
            full_name, 
            password, 
            role, 
            gender,
            coach_gender_preference if role == "client" else None,
            validated_gyms
        )
        
        # Inscription avec email de confirmation natif Supabase
        signup_result = signup_with_supabase_email_confirmation(
            email=email,
            password=password, 
            full_name=full_name,
            role=role
        )
        
        if signup_result.get("success"):
            pr_sent = t.get("email_confirmation_sent", {})
            return templates.TemplateResponse("email_confirmation_sent.html", {
                "request": request,
                "email": email,
                "success": signup_result.get("message", pr_sent.get("message", "Confirmation email sent")),
                **i18n
            })
        else:
            error_message = signup_result.get("error", pr_signup.get("error_signup_failed", "Registration error"))
            if "already registered" in error_message.lower() or "already exists" in error_message.lower():
                error_message = pr_signup.get("error_email_exists", "This email is already in use.")
            log.info(f"💥 Détails erreur inscription Supabase: {error_message}")
            return templates.TemplateResponse("signup.html", {
                "request": request,
                "error": error_message,
                "full_name": full_name,
                "email": email,
                "gender": gender,
                "role": role,
                "country_code": country,
                "countries": countries,
                "coach_gender_preference": coach_gender_preference,
                **i18n
            }, status_code=400)
    except Exception as e:
        log.error(f"Erreur inscription OTP: {e}")
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": pr_signup.get("error_signup_failed", "Registration error. Please try again."),
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference,
            **i18n
        }, status_code=500)

@app.post("/resend-confirmation")
async def resend_confirmation_email(request: Request):
    """Renvoie l'email de confirmation Supabase."""
    try:
        body = await request.json()
        email = body.get("email", "").lower().strip()
        
        if not email:
            return {"success": False, "error": "Email requis"}
        
        result = resend_email_confirmation(email)
        return result
        
    except Exception as e:
        log.error(f"Erreur renvoi confirmation: {e}")
        return {"success": False, "error": str(e)}

@app.get("/auth/email-confirmed")
async def email_confirmed_callback(request: Request):
    """Page affichée après confirmation d'email via Supabase."""
    i18n = get_i18n_context(request)
    t = i18n["t"]
    pr = t.get("email_confirmed", {})
    return templates.TemplateResponse("email_confirmed.html", {
        "request": request,
        "success": pr.get("success_message", "Email confirmed! You can now log in."),
        **i18n
    })

@app.post("/verify-otp")
async def verify_otp_submit(
    request: Request,
    email: str = Form(...),
    otp_code: str = Form(...)
):
    """Vérification du code OTP et activation du compte."""
    email = email.lower().strip()
    otp_code = otp_code.strip()
    i18n = get_i18n_context(request)
    t = i18n["t"]
    pr_otp = t.get("verify_otp", {})
    
    if not otp_code.isdigit() or len(otp_code) < 4 or len(otp_code) > 6:
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": pr_otp.get("code_invalid", "Invalid code."),
            **i18n
        }, status_code=400)
    
    if not supabase_anon:
        # Vérifier que le code correspond exactement à celui généré
        stored_code = demo_otp_cache.get(email)
        if stored_code and otp_code == stored_code:
            # Code correct - supprimer du cache et connecter
            # Récupérer les informations utilisateur depuis le stockage persistant
            user_info = get_demo_user(email) or {}
            role = user_info.get('role', 'client')
            del demo_otp_cache[email]
            
            # Rediriger selon le rôle
            if role == 'coach':
                redirect_url = "/coach/portal"
            else:
                redirect_url = "/client/home"
                
            response = RedirectResponse(url=redirect_url, status_code=303)
            # Créer un token unique pour cet utilisateur
            from auth_utils import generate_session_token
            unique_token = generate_session_token(email)
            response.set_cookie(
                key="session_token",
                value=unique_token,
                httponly=True,
                secure=os.environ.get("REPLIT_DEPLOYMENT") == "1",
                samesite="lax"
            )
            return response
        else:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": pr_otp.get("code_incorrect", "Incorrect code."),
                **i18n
            }, status_code=400)
    
    try:
        otp_valid = verify_otp_code(supabase_anon, email, otp_code)
        if not otp_valid:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": pr_otp.get("code_expired", "Incorrect or expired code."),
                **i18n
            }, status_code=400)
        
        pending_data = get_pending_otp_data(supabase_anon, email)
        if not pending_data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": pr_otp.get("data_not_found", "Registration data not found."),
                **i18n
            }, status_code=400)
        
        response = supabase_anon.table("otp_codes").select("user_id").eq("email", email).eq("consumed", True).order("created_at", desc=True).limit(1).execute()
        if not response.data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": pr_otp.get("user_not_found", "User not found."),
                **i18n
            }, status_code=400)
        
        user_id = response.data[0]['user_id']
        
        # Extraire les données d'inscription
        full_name = pending_data.get('full_name', '')
        role = pending_data.get('role', 'client')
        gender = pending_data.get('gender')
        coach_gender_preference = pending_data.get('coach_gender_preference')
        selected_gyms = pending_data.get('selected_gyms')
        
        # Créer le profil utilisateur avec toutes les données
        profile_created = create_user_profile_on_confirmation(
            supabase_anon, 
            user_id, 
            email, 
            full_name, 
            role,
            gender,
            coach_gender_preference,
            selected_gyms
        )
        
        # Connecter l'utilisateur
        # Note: En production, il faudrait une vraie session Supabase
        # Rediriger l'utilisateur
        
        # Rediriger selon le rôle
        if role == 'coach':
            redirect_url = "/coach/portal"
        else:
            redirect_url = "/client/home"
        
        response = RedirectResponse(url=redirect_url, status_code=303)
        
        response.set_cookie(
            key="session_token",
            value=f"verified_{user_id}",
            httponly=True,
            secure=os.environ.get("REPLIT_DEPLOYMENT") == "1",
            samesite="lax",
            max_age=3600 * 24 * 7  # 7 jours
        )
        
        return response
        
    except Exception as e:
        log.error(f"Erreur vérification OTP: {e}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": pr_otp.get("error_verify", "Verification error."),
            **i18n
        }, status_code=500)

@app.post("/resend-otp")
async def resend_otp_submit(
    request: Request,
    email: str = Form(...)
):
    """Renvoie un nouveau code OTP."""
    email = email.lower().strip()
    i18n = get_i18n_context(request)
    t = i18n["t"]
    pr_otp = t.get("verify_otp", {})
    
    if not supabase_anon:
        new_otp_code = generate_otp_code(6)
        demo_otp_cache[email] = new_otp_code
        log.info(f"🔐 Nouveau code OTP pour {email}: {new_otp_code}")
        user_data = get_demo_user(email)
        full_name = user_data.get("full_name") if user_data else None
        locale = i18n["locale"]
        email_result = send_otp_email_resend(email, new_otp_code, full_name, lang=locale)
        if email_result.get("success"):
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "success": pr_otp.get("resend_success", "New code sent to your email"),
                **i18n
            })
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": pr_otp.get("resend_error", "Error sending code."),
            **i18n
        })
    
    try:
        pending_data = get_pending_otp_data(supabase_anon, email)
        if not pending_data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": pr_otp.get("no_request_found", "No registration request found."),
                **i18n
            }, status_code=400)
        full_name = pending_data['full_name']
        role = pending_data['role']
        new_otp_code = generate_otp_code(6)
        otp_stored = store_otp_code(supabase_anon, email, full_name, role, new_otp_code)
        if not otp_stored:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": pr_otp.get("resend_code_error", "Error generating new code."),
                **i18n
            }, status_code=500)
        locale = i18n["locale"]
        email_result = send_otp_email_resend(email, new_otp_code, full_name, lang=locale)
        if email_result.get("success"):
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "success": pr_otp.get("resend_success", "New code sent by email"),
                **i18n
            })
        error_details = email_result.get("error", "")
        error_message = pr_otp.get("resend_error", "Error sending code. Please try again.")
        log.info(f"💥 Détails erreur renvoi email: {error_details}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": error_message,
            **i18n
        }, status_code=500)
    except Exception as e:
        log.error(f"Erreur renvoi OTP: {e}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": pr_otp.get("resend_error", "Error resending code."),
            **i18n
        }, status_code=500)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, message: Optional[str] = None, password_changed: Optional[str] = None):
    """Formulaire de connexion."""
    csrf_token = _generate_csrf_token()
    i18n = get_i18n_context(request)
    resp = templates.TemplateResponse("login.html", {
        "request": request,
        "message": message,
        "password_changed": password_changed,
        "csrf_token": csrf_token,
        **i18n
    })
    _set_csrf_cookie(resp, csrf_token)
    return resp

@app.post("/login")
@limiter.limit("10/minute")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: Optional[str] = Form(None),
):
    """Traitement de la connexion."""
    def _login_error(msg: str = "Erreur de connexion. Veuillez réessayer."):
        try:
            i18n = get_i18n_context(request)
        except Exception:
            i18n = {"locale": "fr", "t": {}, "text_direction": "ltr", "available_languages": []}
        return templates.TemplateResponse("login.html", {"request": request, "error": msg, "email": email, **i18n}, status_code=200)
    
    try:
        if not _verify_csrf(request, csrf_token or request.headers.get(CSRF_HEADER_NAME)):
            return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})
        email = email.lower().strip()
    except Exception as e:
        log.error(f"Login erreur initiale: {e}")
        import traceback
        traceback.print_exc()
        return _login_error()
    
    if not supabase_anon:
        user_found = None
        
        # Vérifier les utilisateurs inscrits dans le stockage persistant
        cached_user = get_demo_user(email)
        if cached_user:
            # Normaliser les mots de passe pour la comparaison
            stored_password = cached_user.get("password", "").strip()
            submitted_password = password.strip()
            if stored_password and verify_password(submitted_password, stored_password):
                user_found = cached_user
                log.info(f"✅ Connexion avec compte inscrit")
        
        if user_found:
            # Redirection selon le rôle
            role = user_found["role"]
            if role == "coach":
                redirect_url = "/coach/portal"
            elif role == "client":
                redirect_url = "/client/home"
            else:
                redirect_url = "/coach/portal"
            
            log.info(f"✅ Connexion réussie - Redirection vers {redirect_url} (rôle: {role})")
            
            response = RedirectResponse(url=redirect_url, status_code=303)
            # Créer un token unique pour cet utilisateur
            from auth_utils import generate_session_token
            unique_token = generate_session_token(email)
            response.set_cookie(
                key="session_token",
                value=unique_token,
                httponly=True,
                secure=os.environ.get("REPLIT_DEPLOYMENT") == "1",
                samesite="lax"
            )
            return response
        else:
            # Identifiants incorrects
            i18n = get_i18n_context(request)
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email ou mot de passe incorrect.",
                "email": email,
                **i18n
            }, status_code=401)
    
    # Mode Supabase - utiliser le nouveau service avec vérification d'email confirmé
    try:
        i18n = get_i18n_context(request)
    except Exception as e:
        log.error(f"Login get_i18n_context: {e}")
        i18n = {"locale": "fr", "t": {}, "text_direction": "ltr", "available_languages": []}
    
    try:
        result = sign_in_with_email_password(email, password)
    except Exception as e:
        log.error(f"Erreur sign_in Supabase: {e}")
        import traceback
        traceback.print_exc()
        cached_user = get_demo_user(email)
        if cached_user:
            stored_password = cached_user.get("password", "").strip()
            if stored_password and verify_password(password.strip(), stored_password):
                role = cached_user.get("role", "client")
                redirect_url = "/coach/portal" if role == "coach" else "/client/home"
                from auth_utils import generate_session_token
                response = RedirectResponse(url=redirect_url, status_code=303)
                response.set_cookie(key="session_token", value=generate_session_token(email), httponly=True, secure=os.environ.get("REPLIT_DEPLOYMENT") == "1", samesite="lax")
                return response
        return _login_error()
    
    try:
        # Fallback table users : coachs inscrits via formulaire coach sont dans users, pas dans Supabase Auth
        if not result.get("success"):
            cached_user = get_demo_user(email)
            if cached_user:
                stored_password = cached_user.get("password", "").strip()
                if stored_password and verify_password(password.strip(), stored_password):
                    role = cached_user.get("role", "client")
                    redirect_url = "/coach/portal" if role == "coach" else "/client/home"
                    from auth_utils import generate_session_token
                    response = RedirectResponse(url=redirect_url, status_code=303)
                    response.set_cookie(key="session_token", value=generate_session_token(email), httponly=True, secure=os.environ.get("REPLIT_DEPLOYMENT") == "1", samesite="lax")
                    return response
        
        if result.get("success"):
            try:
                user_id = result.get("user") and getattr(result["user"], "id", None)
                session = result.get("session")
                access_token = session.access_token if session else None
                if not user_id or not access_token:
                    raise ValueError("Session ou user manquant")
                user_supabase = get_supabase_client_for_user(access_token)
                profile = get_user_profile(user_supabase, user_id) if user_supabase else None
                user_role = (profile or {}).get("role")
                
                if user_role == "coach":
                    redirect_url = "/coach/portal"
                elif user_role == "client":
                    redirect_url = "/client/home"
                else:
                    redirect_url = "/coach/portal"
                
                log.info(f"✅ Redirection vers {redirect_url} pour utilisateur rôle: {user_role or 'inconnu'}")
                
                response = RedirectResponse(url=redirect_url, status_code=303)
                response.set_cookie(
                    key="session_token",
                    value=access_token,
                    httponly=True,
                    secure=os.environ.get("REPLIT_DEPLOYMENT") == "1",
                    samesite="lax",
                    max_age=3600 * 24 * 7
                )
                return response
            except Exception as e:
                log.error(f"Login post-auth erreur: {e}")
                import traceback
                traceback.print_exc()
                return templates.TemplateResponse("login.html", {
                    "request": request,
                    "error": "Erreur de connexion. Veuillez réessayer.",
                    "email": email,
                    **i18n
                }, status_code=200)
        else:
            # Gérer les différents types d'erreurs
            error_message = result.get("error", "Erreur de connexion")
            
            i18n = get_i18n_context(request)
            if result.get("mode") == "email_not_confirmed":
                return templates.TemplateResponse("login.html", {
                    "request": request,
                    "error": "Email non confirmé. Vérifiez votre boîte mail ou renvoyez l'email de confirmation.",
                    "email": email,
                    "show_resend": True,
                    **i18n
                }, status_code=401)
            elif result.get("mode") == "invalid_credentials":
                return templates.TemplateResponse("login.html", {
                    "request": request,
                    "error": "Email ou mot de passe incorrect.",
                    "email": email,
                    **i18n
                }, status_code=401)
            else:
                log.info(f"💥 Erreur connexion: {error_message}")
                return templates.TemplateResponse("login.html", {
                    "request": request,
                    "error": "Erreur de connexion. Veuillez réessayer.",
                    "email": email,
                    **i18n
                }, status_code=401)
    except Exception as e:
        log.error(f"Login erreur non gérée: {e}")
        import traceback
        traceback.print_exc()
        return _login_error()

@app.post("/auth/resend-confirmation")
async def resend_confirmation(
    request: Request,
    email: str = Form(...),
    csrf_token: Optional[str] = Form(None),
):
    """Renvoie l'email de confirmation."""
    if not _verify_csrf(request, csrf_token or request.headers.get(CSRF_HEADER_NAME)):
        return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})
    # Normaliser l'email en lowercase
    email = email.lower().strip()
    
    i18n = get_i18n_context(request)
    t = i18n["t"]
    pr_ve = t.get("verify_email", {})
    if not supabase_anon:
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "error": pr_ve.get("resend_unavailable", "Email resend not available"),
            **i18n
        })
    success = resend_confirmation_email(supabase_anon, email)
    if success:
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "success": pr_ve.get("resend_success", "Confirmation email resent!"),
            **i18n
        })
    return templates.TemplateResponse("verify_email.html", {
        "request": request,
        "email": email,
        "error": pr_ve.get("resend_error", "Error resending email."),
        **i18n
    })

# === PASSWORD RESET ===
import secrets
from datetime import datetime, timedelta

password_reset_tokens = {}

@app.post("/api/forgot-password")
@limiter.limit("5/minute")
async def api_forgot_password(request: Request):
    """Envoie un email de réinitialisation de mot de passe."""
    try:
        data = await request.json()
        email = data.get("email", "").lower().strip()
        
        if not email:
            return {"success": True}
        
        user = get_demo_user(email)
        if not user:
            return {"success": True}
        
        locale = get_locale_from_request(request)
        translations = get_translations(locale)
        pr = translations.get("password_reset", {})
        
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(hours=1)
        password_reset_tokens[token] = {
            "email": email,
            "expiry": expiry,
            "locale": locale
        }
        
        host = request.headers.get("host", "localhost:5000")
        protocol = "https" if "replit" in host else "http"
        reset_link = f"{protocol}://{host}/reset-password?token={token}"
        
        sender_email = os.environ.get("SENDER_EMAIL", "")
        resend_api_key = os.environ.get("RESEND_API_KEY")
        
        if resend_api_key and sender_email:
            import resend
            resend.api_key = resend_api_key
            
            if "<" in sender_email:
                from_field = sender_email
            else:
                from_field = f"FitMatch <{sender_email}>"
            
            email_greeting = pr.get("email_greeting", "Bonjour,")
            email_body = pr.get("email_body", "Cliquez sur ce lien pour réinitialiser votre mot de passe FitMatch pour le compte")
            email_button = pr.get("email_button", "Réinitialiser mon mot de passe")
            email_copy_link = pr.get("email_copy_link", "Ou copiez ce lien dans votre navigateur :")
            email_ignore = pr.get("email_ignore", "Si vous n'avez pas demandé à réinitialiser votre mot de passe, vous pouvez ignorer cet e-mail.")
            email_thanks = pr.get("email_thanks", "Merci,")
            email_team = pr.get("email_team", "Votre équipe FitMatch")
            email_footer = pr.get("email_footer", "Tous droits réservés.")
            email_subject = pr.get("email_subject", "Réinitialisez votre mot de passe pour FitMatch")
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f5f5f5;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="100%" style="max-width:500px;background:#ffffff;border-radius:12px;overflow:hidden;">
          <tr>
            <td style="padding:32px 32px 24px;text-align:center;border-bottom:1px solid #eee;">
              <span style="font-size:28px;font-weight:700;color:#0b0f14;">Fit<span style="color:#008f57;">Match</span></span>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 16px;font-size:16px;color:#333;">{email_greeting}</p>
              <p style="margin:0 0 24px;font-size:16px;color:#333;line-height:1.5;">
                {email_body} <a href="mailto:{email}" style="color:#008f57;text-decoration:none;">{email}</a>.
              </p>
              <p style="margin:0 0 24px;">
                <a href="{reset_link}" style="display:inline-block;background:#008f57;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">{email_button}</a>
              </p>
              <p style="margin:0 0 8px;font-size:14px;color:#666;">{email_copy_link}</p>
              <p style="margin:0 0 24px;font-size:13px;color:#008f57;word-break:break-all;">
                <a href="{reset_link}" style="color:#008f57;">{reset_link}</a>
              </p>
              <p style="margin:0 0 16px;font-size:14px;color:#999;line-height:1.5;">
                {email_ignore}
              </p>
              <p style="margin:24px 0 0;font-size:14px;color:#333;">{email_thanks}</p>
              <p style="margin:4px 0 0;font-size:14px;color:#333;font-weight:600;">{email_team}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px;background:#f9f9f9;text-align:center;">
              <p style="margin:0;font-size:12px;color:#999;">© 2024 FitMatch. {email_footer}</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
            
            try:
                resend.Emails.send({
                    "from": from_field,
                    "to": [email],
                    "subject": email_subject,
                    "html": html_content
                })
                log.info(f"✅ Email de réinitialisation envoyé à {email} (langue: {locale})")
            except Exception as e:
                log.error(f"Erreur envoi email: {e}")
        else:
            log.warning(f" Resend non configuré ou SENDER_EMAIL manquant")
        
        return {"success": True}
        
    except Exception as e:
        log.error(f"Erreur forgot-password: {e}")
        return {"success": True}


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request, from_page: Optional[str] = Query(None, alias="from")):
    """Page pour demander un lien de réinitialisation de mot de passe."""
    i18n = get_i18n_context(request)
    back_url = "/coach-login" if from_page == "coach" else "/login"
    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "back_url": back_url,
        **i18n
    })


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    """Page de réinitialisation du mot de passe."""
    error = None
    locale = "fr"
    
    if not token:
        locale = get_locale_from_request(request)
        i18n = get_i18n_context(request)
        pr = i18n.get("t", {}).get("password_reset", {})
        error = pr.get("error_invalid", "Lien invalide ou expiré.")
    elif token not in password_reset_tokens:
        locale = get_locale_from_request(request)
        i18n = get_i18n_context(request)
        pr = i18n.get("t", {}).get("password_reset", {})
        error = pr.get("error_invalid", "Lien invalide ou expiré.")
    else:
        token_data = password_reset_tokens[token]
        locale = token_data.get("locale", "fr")
        translations = get_translations(locale)
        text_direction = "rtl" if locale == "ar" else "ltr"
        i18n = {"t": translations, "locale": locale, "text_direction": text_direction}
        if datetime.now() > token_data["expiry"]:
            del password_reset_tokens[token]
            pr = translations.get("password_reset", {})
            error = pr.get("error_expired", "Ce lien a expiré. Veuillez demander un nouveau lien.")
    
    if 'i18n' not in locals():
        i18n = get_i18n_context(request)
    
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token,
        "error": error,
        **i18n
    })

@app.post("/api/reset-password")
async def api_reset_password(request: Request):
    """Réinitialise le mot de passe et connecte automatiquement l'utilisateur."""
    from fastapi.responses import JSONResponse
    import hashlib
    
    try:
        data = await request.json()
        token = data.get("token", "")
        new_password = data.get("password", "")
        
        if not token or token not in password_reset_tokens:
            return JSONResponse({"success": False, "error": "Lien invalide ou expiré."})
        
        token_data = password_reset_tokens[token]
        
        if datetime.now() > token_data["expiry"]:
            del password_reset_tokens[token]
            return JSONResponse({"success": False, "error": "Ce lien a expiré."})
        
        if len(new_password) < 8:
            return JSONResponse({"success": False, "error": "Le mot de passe doit contenir au moins 8 caractères."})
        
        email = token_data["email"]
        user = get_demo_user(email)
        
        if not user:
            del password_reset_tokens[token]
            return JSONResponse({"success": False, "error": "Utilisateur non trouvé."})
        
        user["password"] = hash_password(new_password)
        save_demo_user(email, user)
        
        del password_reset_tokens[token]
        
        from auth_utils import generate_session_token
        session_token = generate_session_token(email)
        role = user.get("role", "client")
        
        log.info(f"✅ Mot de passe réinitialisé pour {email}")
        
        response = JSONResponse({
            "success": True, 
            "email": email,
            "role": role
        })
        
        base = _get_base_url(request)
        use_secure = os.environ.get("REPLIT_DEPLOYMENT") == "1" or (base or "").lower().startswith("https") or os.environ.get("RENDER")
        response.set_cookie(
            key="session_token",
            value=session_token,
            path="/",
            httponly=True,
            secure=use_secure,
            samesite="lax",
            max_age=86400 * 30,
        )
        
        return response
        
    except Exception as e:
        log.error(f"Erreur reset-password: {e}")
        return JSONResponse({"success": False, "error": "Une erreur est survenue."})

# Espace Coach - Page de connexion/inscription dédiée aux coaches
@app.get("/coach-login", response_class=HTMLResponse)
async def coach_login_page(
    request: Request,
    tab: Optional[str] = None,
    error: Optional[str] = None,
):
    """Page de connexion/inscription pour les coaches."""
    i18n = get_i18n_context(request)
    if error == "session_expired":
        error_msg = "Lien expiré. Réessayez de créer votre compte (bouton ci-dessous)."
    elif error == "missing_token":
        error_msg = "Lien invalide. Remplissez le formulaire et cliquez sur « Créer mon compte coach »."
    else:
        error_msg = None
    csrf_token = _generate_csrf_token()
    resp = templates.TemplateResponse("coach_login.html", {
        "request": request,
        "tab": tab,
        "error": error_msg,
        "csrf_token": csrf_token,
        **i18n
    })
    _set_csrf_cookie(resp, csrf_token)
    return resp

@app.post("/coach-login")
@limiter.limit("10/minute")
async def coach_login_submit(
    request: Request,
    action: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    name: Optional[str] = Form(None),
    csrf_token: Optional[str] = Form(None),
):
    """Traitement de la connexion/inscription coach."""
    i18n = get_i18n_context(request)
    try:
        if not _verify_csrf(request, csrf_token or request.headers.get(CSRF_HEADER_NAME)):
            return JSONResponse(status_code=403, content={"detail": "Invalid CSRF token"})
        email = email.lower().strip()
    except Exception as e:
        log.error(f"Erreur coach-login (csrf/email): {e}")
        return templates.TemplateResponse("coach_login.html", {
            "request": request, "error": "Erreur de validation. Veuillez réessayer.", "tab": "login", **i18n
        }, status_code=400)
    
    if action == "signup":
        # Inscription coach
        i18n = get_i18n_context(request)
        if not name or len(name.strip()) < 2:
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Le nom est requis (minimum 2 caractères).",
                "tab": "signup",
                **i18n
            }, status_code=400)
        
        if len(password) < 8:
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Le mot de passe doit contenir au moins 8 caractères.",
                "tab": "signup",
                **i18n
            }, status_code=400)
        
        # Vérifier si l'email existe déjà (utilise fallback si DB inaccessible)
        existing_user = get_demo_user(email)
        if existing_user:
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Un compte existe déjà avec cet email.",
                "tab": "signup",
                **i18n
            }, status_code=400)
        
        # Créer le compte coach avec statut "en attente de paiement"
        locale = get_locale_from_request(request)
        new_coach = {
            "email": email,
            "password": hash_password(password),
            "full_name": name.strip(),
            "role": "coach",
            "verified": True,
            "profile_completed": False,
            "subscription_status": "pending_payment",
            "lang": locale or "fr",
        }
        try:
            save_demo_user(email, new_coach)
        except Exception as e:
            log.error(f"Erreur inscription coach {email}: {e}")
            import traceback
            traceback.print_exc()
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Une erreur s'est produite lors de l'inscription. Réessayez ou contactez le support.",
                "tab": "signup",
                **i18n
            }, status_code=500)
        log.info(f"✅ Nouveau coach inscrit (en attente de paiement): {email}")
        
        # Redirection vers la page offre coach (landing marketing + choix abonnement)
        base = _get_base_url(request)
        signup_token = _create_signup_token(email)
        pay_url = f"{base.rstrip('/')}/coach/offre?token={signup_token}"
        response = RedirectResponse(url=pay_url, status_code=302)
        _set_session_cookie(response, email, request)
        return response
    
    else:
        # Connexion coach
        user_found = None
        try:
            # Vérifier les utilisateurs inscrits
            cached_user = get_demo_user(email)
            if cached_user:
                stored_password = cached_user.get("password", "").strip()
                if stored_password and verify_password(password.strip(), stored_password):
                    # Vérifier que c'est bien un coach
                    if cached_user.get("role") == "coach":
                        user_found = cached_user
                    else:
                        return templates.TemplateResponse("coach_login.html", {
                            "request": request,
                            "error": "Ce compte n'est pas un compte coach. Utilisez la connexion client.",
                            "tab": "login",
                            **i18n
                        }, status_code=401)
            
            if user_found:
                from auth_utils import generate_session_token
                unique_token = generate_session_token(email)
                
                # Auto-upgrade grandfathered accounts (created before OTP/subscription system)
                profile_completed = user_found.get("profile_completed", False)
                subscription_status = user_found.get("subscription_status")
                email_verified = user_found.get("email_verified")
                is_legacy_account = profile_completed and (subscription_status is None or subscription_status == "")
                
                if is_legacy_account:
                    log.info(f"Auto-upgrading grandfathered coach account: {email}")
                    updated_user = get_demo_user(email)
                    if updated_user:
                        updated_user["subscription_status"] = "active"
                        if email_verified is None or email_verified == "":
                            updated_user["email_verified"] = True
                        save_demo_user(email, updated_user)
                        user_found["subscription_status"] = "active"
                        if email_verified is None or email_verified == "":
                            user_found["email_verified"] = True
                        subscription_status = "active"

                if not user_found.get("lang"):
                    coach_locale = get_locale_from_request(request)
                    if coach_locale:
                        u = get_demo_user(email)
                        if u:
                            u["lang"] = coach_locale
                            save_demo_user(email, u)
                            user_found["lang"] = coach_locale
                
                if subscription_status == "pending_payment":
                    pay_token = _create_signup_token(email)
                    base = _get_base_url(request)
                    redirect_url = f"{base.rstrip('/')}/coach/offre?token={pay_token}"
                else:
                    redirect_url = "/coach/portal" if profile_completed else "/coach/profile-setup"
                response = RedirectResponse(url=redirect_url, status_code=302)
                _set_session_cookie(response, email, request)
                return response
            else:
                # Fallback Supabase Auth : si le coach n'est pas dans users (inscrit via Auth)
                if supabase_anon:
                    result = sign_in_with_email_password(email, password)
                    if result.get("success"):
                        user_id = result["user"].id
                        profile = get_user_profile(get_supabase_client_for_user(result["session"].access_token), user_id)
                        if profile and profile.get("role") == "coach":
                            response = RedirectResponse(url="/coach/portal", status_code=302)
                            response.set_cookie(
                                key="session_token",
                                value=result["session"].access_token,
                                httponly=True,
                                secure=os.environ.get("REPLIT_DEPLOYMENT") == "1",
                                samesite="lax",
                                max_age=3600 * 24 * 7
                            )
                            return response
                return templates.TemplateResponse("coach_login.html", {
                    "request": request,
                    "error": "Email ou mot de passe incorrect.",
                    "tab": "login",
                    **i18n
                }, status_code=401)
        except Exception as e:
            log.error(f"Erreur connexion coach {email}: {e}")
            import traceback
            traceback.print_exc()
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Erreur de connexion. Veuillez réessayer ou contacter le support si le problème persiste.",
                "tab": "login",
                "email": email,
                **i18n
            }, status_code=500)

# Déconnexion coach
@app.get("/coach-logout")
async def coach_logout(request: Request):
    """Déconnexion coach : vide la session et supprime le cookie."""
    response = RedirectResponse(url="/coach-login", status_code=303)
    response.delete_cookie("session_token")
    if hasattr(request, "session") and request.session:
        try:
            request.session.clear()
        except Exception:
            pass
    return response

# Routes protégées - Espace Coach
@app.get("/coach/dashboard", response_class=HTMLResponse)
async def coach_dashboard_redirect(request: Request, user=Depends(require_coach_session_or_cookie)):
    """Alias vers /coach/portal (dashboard coach)."""
    return RedirectResponse(url="/coach/portal", status_code=302)

@app.get("/coach/portal", response_class=HTMLResponse)
async def coach_portal(request: Request, user = Depends(require_coach_session_or_cookie)):
    """Dashboard coach - avec vérification du profil complété, abonnement et email (verified_at)."""
    
    # Charger les données fraîches depuis le fichier JSON (ou session si multi-instances)
    coach_email = user.get("email")
    demo_users = load_demo_users()
    coach_data_fresh = demo_users.get(coach_email, {})

    subscription_status = coach_data_fresh.get("subscription_status") or user.get("subscription_status", "") or "active"
    log.info(f"🔍 Portal check: email={coach_email}, subscription_status='{subscription_status}'")
    
    if not get_session_email(request):
        try:
            from utils import use_database
            if use_database():
                from email_verification_service import is_email_verified
                if not is_email_verified(coach_email):
                    from urllib.parse import quote
                    return RedirectResponse(url=f"/coach/verify-email?email={quote(coach_email)}", status_code=303)
            elif not demo_users.get(coach_email, {}).get("email_verified", False):
                from urllib.parse import quote
                return RedirectResponse(url=f"/coach/verify-email?email={quote(coach_email)}", status_code=303)
        except Exception as e:
            log.warning(f"Check verified_at: {e}")
    
    if subscription_status in ["blocked", "cancelled", "past_due"]:
        return RedirectResponse(url="/coach/subscription", status_code=302)
    if subscription_status == "pending_payment":
        # Page offre coach (landing + choix abonnement)
        pay_token = _create_signup_token(coach_email)
        base = _get_base_url(request)
        return RedirectResponse(url=f"{base.rstrip('/')}/coach/offre?token={pay_token}", status_code=302)
    
    # Vérifier si le profil est complété
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        try:
            # Récupérer le statut du profil
            user_id = user.get("id", user.get("email", "demo_user"))
            profile_response = user_supabase.table("profiles").select("profile_completed").eq("user_id", user_id).single().execute()
            profile_completed = profile_response.data.get("profile_completed", False) if profile_response.data else False
            
            # Si le profil n'est pas complété, rediriger vers l'onboarding
            if not profile_completed:
                return RedirectResponse(url="/coach/profile-setup", status_code=302)
                
            # Récupérer les transformations du coach
            transformations = get_transformations_by_coach_supabase(user_supabase, user_id)
        except Exception as e:
            log.error(f"Erreur lors de la vérification du profil: {e}")
            # En cas d'erreur, rediriger vers l'onboarding par sécurité
            return RedirectResponse(url="/coach/profile-setup", status_code=302)
    else:
        # Vérifier si le profil est complété (demo_users / DB)
        profile_completed = coach_data_fresh.get("profile_completed", False) or user.get("profile_completed", False)
        if not profile_completed:
            return RedirectResponse(url="/coach/profile-setup", status_code=302)
        transformations = []
    
    # Inclure payment_mode, slug (profile_slug) depuis demo_users pour le dashboard
    coach_slug = coach_data_fresh.get("profile_slug") or (user.get("profile_slug") or "")
    if not coach_slug and user.get("full_name"):
        coach_slug = generate_slug((user.get("full_name") or "Coach").split()[0]) if (user.get("full_name") or "").strip() else "coach"
    if not coach_slug:
        coach_slug = "coach"
    coach_for_template = {
        **user,
        "payment_mode": coach_data_fresh.get("payment_mode", "disabled"),
        "slug": coach_slug,
        "profile_slug": coach_slug,
    }

    i18n = get_i18n_context(request)
    return templates.TemplateResponse("coach_portal.html", {
        "request": request,
        "coach": coach_for_template,
        "transformations": transformations,
        **i18n
    })

@app.post("/coach/portal")
async def coach_portal_update(
    request: Request,
    user = Depends(require_coach_session_or_cookie),
    full_name: str = Form(...),
    bio: str = Form(""),
    city: str = Form(""),
    instagram_url: str = Form(""),
    price_from: Optional[int] = Form(None),
    radius_km: int = Form(25)
):
    """Mise à jour du profil coach."""
    
    profile_data = {
        "full_name": full_name,
        "bio": bio,
        "city": city,
        "instagram_url": instagram_url,
        "price_from": price_from,
        "radius_km": radius_km
    }
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        user_id = user.get("id", user.get("email", "demo_user"))
        success = update_coach_profile(user_supabase, user_id, profile_data)
        if not success:
            demo_users = load_demo_users()
            coach_data_fresh = demo_users.get(user.get("email"), {})
            coach_for_template = {**user, "payment_mode": coach_data_fresh.get("payment_mode", "disabled")}
            i18n = get_i18n_context(request)
            return templates.TemplateResponse("coach_portal.html", {
                "request": request,
                "coach": coach_for_template,
                "error": "Erreur lors de la mise à jour du profil.",
                **i18n
            })
    
    return RedirectResponse(url="/coach/portal", status_code=303)

# Route onboarding coach
@app.get("/coach/profile-setup", response_class=HTMLResponse)
async def coach_profile_setup_get(request: Request, user = Depends(require_coach_session_or_cookie)):
    """Page d'onboarding/configuration du profil coach. Accepte session OTP ou cookie."""
    coach_email = user.get("email")
    if not get_session_email(request):
        demo_users = load_demo_users()
        coach_data_check = demo_users.get(coach_email, {})
        verified = False
        try:
            from utils import use_database
            if use_database():
                from email_verification_service import is_email_verified
                verified = is_email_verified(coach_email)
            if not verified:
                verified = coach_data_check.get("email_verified", False)
            if not verified:
                from urllib.parse import quote
                return RedirectResponse(url=f"/coach/verify-email?email={quote(coach_email)}", status_code=303)
        except Exception:
            if not coach_data_check.get("email_verified", False):
                from urllib.parse import quote
                return RedirectResponse(url=f"/coach/verify-email?email={quote(coach_email)}", status_code=303)
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    coach_data = None
    profile_completed = False
    
    if user_supabase:
        try:
            # Récupérer les données actuelles du profil
            user_id = user.get("id", user.get("email", "demo_user"))
            profile_response = user_supabase.table("profiles").select("*").eq("user_id", user_id).single().execute()
            if profile_response.data:
                coach_data = profile_response.data
                profile_completed = coach_data.get("profile_completed", False)
        except Exception as e:
            log.error(f"Erreur lors de la récupération du profil: {e}")
    else:
        # Charger les données depuis l'utilisateur connecté
        coach_data = user
        profile_completed = user.get("profile_completed", False)
        log.info(f"🔧 Chargement des données du profil pour {user.get('email', 'coach')}")
    
    error_param = request.query_params.get("error", "")
    error_messages = {
        "photo_vide": "Fichier photo vide ou invalide.",
        "photo_trop_grande": "Photo trop volumineuse (max 10 Mo).",
        "upload_photo": "Erreur lors de l'upload de la photo.",
        "sauvegarde": "Erreur lors de la sauvegarde. Veuillez réessayer.",
        "session_expired": "Session expirée. Veuillez vous reconnecter.",
    }
    error_message = error_messages.get(error_param, error_param) if error_param else None

    i18n_context = get_i18n_context(request)
    return templates.TemplateResponse("coach_profile_setup.html", {
        "request": request,
        "coach": coach_data,
        "profile_completed": profile_completed,
        "user": user,
        "error_message": error_message,
        **i18n_context
    })

@app.post("/coach/profile-setup")
async def coach_profile_setup_post(
    request: Request,
    full_name: str = Form(...),
    bio: str = Form(...),
    city: str = Form(...),
    instagram_url: Optional[str] = Form(""),
    price_from: Optional[int] = Form(None),
    radius_km: int = Form(25),
    specialties: List[str] = Form([]),
    selected_gym_ids: Optional[str] = Form(""),
    selected_gyms_data: Optional[str] = Form(""),
    profile_photo: Optional[UploadFile] = File(None),
    user = Depends(require_coach_session_or_cookie)
):
    """Traitement du formulaire d'onboarding coach."""
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    error_message = None
    success_message = None
    profile_completed_before = user.get("profile_completed", False)
    
    # Photo obligatoire uniquement en mode Supabase ; en mode OTP/demo, optionnelle
    if user_supabase and not profile_completed_before and not (profile_photo and profile_photo.filename):
        error_message = "Photo de profil obligatoire"
        i18n_context = get_i18n_context(request)
        return templates.TemplateResponse("coach_profile_setup.html", {
            "request": request,
            "coach": {"full_name": full_name, "bio": bio, "city": city, "instagram_url": instagram_url, "price_from": price_from, "radius_km": radius_km, "specialties": specialties},
            "profile_completed": False,
            "error_message": error_message,
            "user": user,
            **i18n_context
        }, status_code=400)
    
    try:
        # Gérer l'upload de la photo de profil
        profile_photo_url = None
        if profile_photo and profile_photo.filename:
            try:
                photo_content = await profile_photo.read()
                user_id = user.get("id", user.get("email", "demo_user"))
                
                if user_supabase:
                    # Mode Supabase - Upload vers Supabase Storage
                    original_content, thumb_content, filename = process_image_for_upload(photo_content, str(user_id))
                    profile_photo_url = await upload_to_supabase_storage(user_supabase, original_content, f"profile_{filename}")
                    
                    if not profile_photo_url:
                        error_message = "Erreur lors de l'upload de la photo de profil."
                else:
                    # Stocker localement dans attached_assets
                    import os
                    os.makedirs("attached_assets/profile_photos", exist_ok=True)
                    
                    # Traiter l'image
                    original_content, thumb_content, filename = process_image_for_upload(photo_content, str(user_id))
                    
                    # Sauvegarder localement
                    local_path = f"attached_assets/profile_photos/{filename.replace('/', '_')}"
                    with open(local_path, "wb") as f:
                        f.write(original_content)
                    
                    profile_photo_url = f"/attached_assets/profile_photos/{filename.replace('/', '_')}"
                    log.info(f"✅ Photo sauvegardée localement: {profile_photo_url}")
                    
            except Exception as e:
                log.error(f"Erreur lors du traitement de la photo: {e}")
                error_message = f"Erreur lors du traitement de la photo: {str(e)}"
        
        if user_supabase:
            # Mode Supabase - Préparer les données de profil
            profile_data = {
                "full_name": full_name.strip(),
                "bio": bio.strip(),
                "city": city.strip(),
                "instagram_url": instagram_url.strip() if instagram_url else None,
                "price_from": price_from,
                "radius_km": radius_km,
                "profile_completed": True  # Marquer le profil comme complété
            }
            
            # Ajouter l'URL de la photo si elle a été uploadée
            if profile_photo_url:
                profile_data["profile_photo_url"] = profile_photo_url
            
            # Mettre à jour le profil principal
            user_id = user.get("id", user.get("email", "demo_user"))
            profile_response = user_supabase.table("profiles").update(profile_data).eq("user_id", user_id).execute()
            
            if profile_response.data:
                # Traiter les spécialités si fournies
                if specialties:
                    # Supprimer les anciennes spécialités
                    user_supabase.table("coach_specialties").delete().eq("coach_id", user_id).execute()
                    
                    # Ajouter les nouvelles spécialités
                    specialty_data = [{"coach_id": user_id, "specialty": spec} for spec in specialties]
                    user_supabase.table("coach_specialties").insert(specialty_data).execute()
                
                # Traiter les salles sélectionnées si fournies
                if selected_gym_ids and selected_gym_ids.strip():
                    gym_ids = [gid.strip() for gid in selected_gym_ids.split(",") if gid.strip()]
                    if gym_ids:
                        # Supprimer les anciennes associations
                        user_supabase.table("coach_gyms").delete().eq("coach_id", user_id).execute()
                        
                        # Ajouter les nouvelles associations
                        gym_data = [{"coach_id": user_id, "gym_id": gym_id} for gym_id in gym_ids]
                        user_supabase.table("coach_gyms").insert(gym_data).execute()
                
                request.session["profile_completed"] = True
                return RedirectResponse(url="/coach/portal", status_code=303)
            else:
                error_message = "Erreur lors de la mise à jour du profil."
        else:
            # Mise à jour réussie du profil
            log.info(f"✅ Profil mis à jour pour {user.get('email', 'coach')} avec:")
            log.info(f"   - Nom: {full_name}")
            log.info(f"   - Ville: {city}")
            log.info(f"   - Spécialités: {specialties}")
            log.info(f"   - Salles IDs: {selected_gym_ids}")
            log.info(f"   - Salles data: {selected_gyms_data[:100] if selected_gyms_data else 'None'}...")
            
            # Mettre à jour l'utilisateur et sauvegarder dans le stockage persistant
            from utils import save_demo_user
            session_token = user.get("_access_token", "")
            user_email = user.get("email", "").strip().lower() or None
            
            if not user_email and (session_token.startswith("demo_") or session_token.startswith("session_")):
                if session_token.startswith("session_"):
                    user_email = session_token.replace("session_", "", 1).strip().lower() or None
                    if user_email:
                        log.info(f"[OK] Email extrait du token session: {user_email}")
                else:
                    from utils import load_demo_users
                    from auth_utils import get_email_from_session_token
                    user_email = get_email_from_session_token(session_token, load_demo_users)
                    if user_email:
                        log.info(f"[OK] Email extrait du token: {user_email}")
            
            if not user_email:
                log.error(f" Impossible d'identifier l'utilisateur (token invalide ou expiré)")
                error_message = "Session invalide. Veuillez vous reconnecter."
                i18n_context = get_i18n_context(request)
                return templates.TemplateResponse("coach_profile_setup.html", {
                    "request": request,
                    "coach": {"full_name": full_name, "bio": bio, "city": city, "instagram_url": instagram_url, "price_from": price_from, "radius_km": radius_km, "specialties": specialties},
                    "profile_completed": False,
                    "error_message": error_message,
                    "user": user,
                    **i18n_context
                }, status_code=401)
            
            log.info(f"🔧 Sauvegarde profil pour: {user_email}")
            
            # CORRECTION : Récupérer les données existantes pour préserver le mot de passe
            existing_user = get_demo_user(user_email) or {}
            
            # Générer un slug unique pour ce coach (ou garder l'existant)
            existing_slug = existing_user.get("profile_slug")
            if existing_slug:
                profile_slug = existing_slug
            else:
                profile_slug = generate_unique_slug_for_coach(user_email, full_name)
            log.info(f"🔗 Slug du profil: {profile_slug}")
            
            updated_user = {
                "id": user.get("id", user_email),  # Utiliser email comme ID si pas d'ID
                "email": user_email,
                "role": user.get("role", "coach"),
                "profile_completed": True,
                "profile_slug": profile_slug,  # ✅ Slug unique pour l'URL
                "full_name": full_name,
                "bio": bio,
                "city": city,
                "instagram_url": instagram_url,
                "price_from": price_from,
                "radius_km": radius_km,
                "specialties": specialties,  # ✅ Sauvegarder les spécialités
                "selected_gym_ids": selected_gym_ids,  # ✅ Sauvegarder les IDs des salles
                "selected_gyms_data": selected_gyms_data,  # ✅ Sauvegarder les détails complets des salles
                "profile_photo_url": profile_photo_url or existing_user.get("profile_photo_url"),  # ✅ Sauvegarder la photo
                # PRÉSERVER les données d'inscription existantes
                "password": existing_user.get("password"),  # ✅ Conserver le mot de passe !
                "gender": existing_user.get("gender"),
                "country_code": existing_user.get("country_code"),
                "coach_gender_preference": existing_user.get("coach_gender_preference"),
                "selected_gyms": existing_user.get("selected_gyms"),
                # ✅ PRÉSERVER les données d'abonnement et vérification (actif par défaut après finalisation)
                "subscription_status": existing_user.get("subscription_status") or "active",
                "email_verified": existing_user.get("email_verified"),
                "stripe_customer_id": existing_user.get("stripe_customer_id"),
                "stripe_subscription_id": existing_user.get("stripe_subscription_id"),
                "subscription_period_end": existing_user.get("subscription_period_end"),
                "otp_code": existing_user.get("otp_code"),
                "otp_expiry": existing_user.get("otp_expiry")
            }
            
            log.info(f"🔒 Mot de passe préservé: {'✅' if updated_user['password'] else '❌'}")
            
            # Sauvegarder les modifications dans le stockage persistant
            save_demo_user(user_email, updated_user)
            log.info(f"Profil coach sauvegarde avec profile_completed=True")
            # Session pour que le portail reconnaisse profile_completed (multi-instances)
            request.session["profile_completed"] = True
            request.session["subscription_status"] = "active"
            # Redirection vers le dashboard apres succes
            return RedirectResponse(url="/coach/portal", status_code=303)
            
    except Exception as e:
        log.error(f"Erreur lors de la soumission du profil: {e}")
        error_message = "Une erreur s'est produite lors de la sauvegarde."
    
    # En cas d'erreur, recharger la page avec le message d'erreur
    i18n_context = get_i18n_context(request)
    return templates.TemplateResponse("coach_profile_setup.html", {
        "request": request,
        "coach": {"full_name": full_name, "bio": bio, "city": city, "instagram_url": instagram_url, "price_from": price_from, "radius_km": radius_km, "specialties": specialties},
        "profile_completed": False,
        "error_message": error_message,
        "user": user,
        **i18n_context
    })


def _wants_json_response(request: Request, form_data=None) -> bool:
    """True si la requête vient d'un fetch/XHR. form_submit=1 (soumission native) force RedirectResponse."""
    if form_data is not None:
        val = form_data.get("form_submit") if hasattr(form_data, "get") else None
        if val == "1" or val == 1:
            return False
    accept = (request.headers.get("accept") or "").lower()
    xrw = (request.headers.get("x-requested-with") or "").lower()
    return "application/json" in accept or xrw == "xmlhttprequest"


@app.post("/api/coach/profile-setup")
@limiter.limit("10/minute")
async def api_coach_profile_setup(request: Request):
    """API profile-setup : multipart/form-data. XHR/fetch -> JSON. Submit HTML classique -> RedirectResponse 303."""
    coach_email = None
    form = None
    try:
        form = await request.form()
        coach_email = get_session_email(request) or request.session.get("coach_email")
        if not coach_email:
            user = get_coach_from_session_or_cookie(request)
            coach_email = (user or {}).get("email", "").strip().lower()
        if not coach_email:
            log.warning("[profile-setup] Not authenticated")
            if _wants_json_response(request, form):
                return JSONResponse({"success": False, "error": "Not authenticated"}, status_code=401)
            return RedirectResponse(url="/coach-login?error=session_expired", status_code=303)

        profile_photo = form.get("profile_photo") or form.get("photo")
        if hasattr(profile_photo, "file") and profile_photo.file and (getattr(profile_photo, "filename") or "").strip():
            pass
        else:
            profile_photo = None

        def _str(v, default=""):
            if v is None: return default
            s = str(v).strip() if v else default
            return s or default

        def _int(v, default=None):
            if v is None or v == "": return default
            try: return int(float(str(v).replace(",", ".")))
            except (ValueError, TypeError): return default

        full_name = _str(form.get("full_name"))
        bio = _str(form.get("bio"))
        city = _str(form.get("city"))
        postal_code = _str(form.get("postal_code"))
        instagram_url = _str(form.get("instagram_url")) or None
        price_from = _int(form.get("price_from")) or _int(form.get("price")) or 50
        radius_km = _int(form.get("radius_km")) or 25
        specialties_raw = form.getlist("specialties") if hasattr(form, "getlist") else []
        specialties = [s for s in specialties_raw] if isinstance(specialties_raw, list) else []
        if not specialties and form.get("specialties"):
            specialties = [str(form.get("specialties"))]
        selected_gym_ids = _str(form.get("selected_gym_ids"))
        selected_gyms_data = _str(form.get("selected_gyms_data"))

        log.info(f"[profile-setup] coach_email={coach_email} full_name={full_name!r} city={city!r} bio_len={len(bio)} photo_present={profile_photo is not None}")

        photo_url = None
        if profile_photo and hasattr(profile_photo, "read"):
            try:
                contents = await profile_photo.read()
                if not contents or len(contents) == 0:
                    log.warning("[profile-setup] Photo file empty")
                    if _wants_json_response(request, form):
                        return JSONResponse({"success": False, "error": "PHOTO_UPLOAD_FAILED", "detail": "Fichier photo vide ou invalide."}, status_code=400)
                    return RedirectResponse(url="/coach/profile-setup?error=photo_vide", status_code=303)
                if len(contents) > 10 * 1024 * 1024:
                    log.warning("[profile-setup] Photo too large")
                    if _wants_json_response(request, form):
                        return JSONResponse({"success": False, "error": "PHOTO_UPLOAD_FAILED", "detail": "Photo trop volumineuse (max 10 Mo)."}, status_code=400)
                    return RedirectResponse(url="/coach/profile-setup?error=photo_trop_grande", status_code=303)
                os.makedirs("uploads", exist_ok=True)
                ext = "jpg"
                if hasattr(profile_photo, "content_type") and profile_photo.content_type and "png" in str(profile_photo.content_type):
                    ext = "png"
                filename = f"{uuid.uuid4()}.{ext}"
                path = f"uploads/{filename}"
                with open(path, "wb") as f:
                    f.write(contents)
                photo_url = f"/uploads/{filename}"
                log.info(f"[profile-setup] Photo upload OK: {photo_url}")
            except Exception as e:
                log.error(f"[profile-setup] Photo upload FAILED: {e}")
                if _wants_json_response(request, form):
                    return JSONResponse({"success": False, "error": "PHOTO_UPLOAD_FAILED", "detail": str(e) or "Erreur lors de l'upload de la photo."}, status_code=400)
                return RedirectResponse(url="/coach/profile-setup?error=upload_photo", status_code=303)

        existing = get_demo_user(coach_email) or {}
        profile_slug = existing.get("profile_slug") or generate_unique_slug_for_coach(coach_email, full_name or "Coach")

        # Note: La table "coaches" n'existe pas dans Supabase. On utilise uniquement save_demo_user
        # (PostgreSQL users ou demo_users_fallback.json) pour le flux OTP/post-paiement.
        updated = {
            "id": existing.get("id", coach_email),
            "email": coach_email,
            "role": existing.get("role", "coach"),
            "profile_completed": True,
            "profile_slug": profile_slug,
            "full_name": full_name or existing.get("full_name", ""),
            "bio": bio or existing.get("bio", ""),
            "city": city or existing.get("city", ""),
            "postal_code": postal_code or existing.get("postal_code", ""),
            "instagram_url": instagram_url or existing.get("instagram_url"),
            "price_from": price_from or existing.get("price_from", 50),
            "radius_km": radius_km or existing.get("radius_km", 25),
            "specialties": specialties or existing.get("specialties", []),
            "selected_gym_ids": selected_gym_ids or existing.get("selected_gym_ids", ""),
            "selected_gyms_data": selected_gyms_data or existing.get("selected_gyms_data", ""),
            "profile_photo_url": photo_url or existing.get("profile_photo_url"),
            "password": existing.get("password"),
            "gender": existing.get("gender"),
            "country_code": existing.get("country_code"),
            "coach_gender_preference": existing.get("coach_gender_preference"),
            "selected_gyms": existing.get("selected_gyms"),
            "subscription_status": existing.get("subscription_status", "active"),
            "email_verified": existing.get("email_verified"),
            "stripe_customer_id": existing.get("stripe_customer_id"),
            "stripe_subscription_id": existing.get("stripe_subscription_id"),
            "subscription_period_end": existing.get("subscription_period_end"),
            "otp_code": existing.get("otp_code"),
            "otp_expiry": existing.get("otp_expiry"),
        }

        # Toujours mettre à jour demo_users : le portail lit profile_completed depuis get_demo_user()
        try:
            ok = save_demo_user(coach_email, updated)
            if not ok:
                log.error(f"[profile-setup] save_demo_user FAILED for {coach_email}")
                if _wants_json_response(request, form):
                    return JSONResponse({"success": False, "error": "DB_UPDATE_FAILED", "detail": "Erreur lors de la sauvegarde."}, status_code=500)
                return RedirectResponse(url="/coach/profile-setup?error=sauvegarde", status_code=303)
        except Exception as db_err:
            import traceback
            err_detail = traceback.format_exc()
            print("PROFILE UPDATE ERROR:")
            print(err_detail)
            log.error(f"[profile-setup] PROFILE UPDATE ERROR:\n{err_detail}")
            if _wants_json_response(request, form):
                return JSONResponse(status_code=500, content={"success": False, "error": "PROFILE_SAVE_EXCEPTION", "detail": str(db_err)})
            return RedirectResponse(url="/coach/profile-setup?error=sauvegarde", status_code=303)
        log.info(f"[profile-setup] OK coach={coach_email} profile_completed=True")

        # Stocker dans la session (cookie) pour que le portail reconnaisse profile_completed
        request.session["profile_completed"] = True

        redirect_url = "/coach/portal"
        if _wants_json_response(request, form):
            resp = JSONResponse({"success": True, "redirect": redirect_url})
            resp.headers["X-Redirect-To"] = redirect_url
            return resp
        return RedirectResponse(url=redirect_url, status_code=303)
    except Exception as e:
        log.error(f"[profile-setup] ERROR: {e} (coach={coach_email})")
        if _wants_json_response(request, form):
            return JSONResponse({"success": False, "error": str(e), "detail": str(e)}, status_code=500)
        from urllib.parse import quote
        return RedirectResponse(url="/coach/profile-setup?error=" + quote(str(e)[:80]), status_code=303)


# Endpoint de test : crée une session coach (uniquement si TEST_SESSION=1)
@app.get("/api/test/create-session")
async def test_create_session(request: Request, email: str = Query(...)):
    """Crée une session coach pour les tests. Nécessite TEST_SESSION=1."""
    if os.environ.get("TEST_SESSION") != "1":
        raise HTTPException(status_code=404, detail="Not found")
    email = email.strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email requis")
    request.session["user_email"] = email
    request.session["coach_email"] = email
    request.session["is_coach"] = True
    resp = JSONResponse({"ok": True, "email": email})
    _set_session_cookie(resp, email, request)
    return resp


@app.post("/coach/specialties")
async def coach_specialties_update(
    request: Request,
    user = Depends(require_coach_session_or_cookie),
    specialties: List[str] = Form([])
):
    """Mise à jour des spécialités du coach."""
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        success = update_coach_specialties(user_supabase, user["id"], specialties)
        if not success:
            return RedirectResponse(url="/coach/portal?error=specialties", status_code=303)
    
    return RedirectResponse(url="/coach/portal", status_code=303)

@app.post("/coach/transformations")
async def coach_transformations_add(
    request: Request,
    user = Depends(require_coach_session_or_cookie),
    title: str = Form(...),
    description: str = Form(""),
    duration_weeks: Optional[int] = Form(None),
    consent: bool = Form(False),
    before_image: Optional[UploadFile] = File(None),
    after_image: Optional[UploadFile] = File(None)
):
    """Ajout d'une transformation avec upload d'images sécurisé."""
    
    if not consent:
        return RedirectResponse(url="/coach/portal?error=consent", status_code=303)
    
    # Valider les images si présentes
    error_msg = ""
    
    if before_image and before_image.filename:
        is_valid, msg = validate_image_file(before_image)
        if not is_valid:
            error_msg = f"Image avant: {msg}"
    
    if after_image and after_image.filename and not error_msg:
        is_valid, msg = validate_image_file(after_image)
        if not is_valid:
            error_msg = f"Image après: {msg}"
    
    if error_msg:
        return RedirectResponse(url=f"/coach/portal?error={error_msg}", status_code=303)
    
    transformation_data = {
        "title": title,
        "description": description,
        "duration_weeks": duration_weeks,
        "consent": consent
    }
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    if user_supabase:
        try:
            # Ajouter la transformation
            transformation = add_transformation(user_supabase, user["id"], transformation_data)
            
            if transformation and (before_image or after_image):
                coach_id = user["id"]
                update_data = {}
                
                # Traiter l'image avant
                if before_image and before_image.filename:
                    before_content = before_image.file.read()
                    original_content, thumb_content, filename = process_image_for_upload(before_content, coach_id)
                    
                    # Upload sécurisé vers Supabase Storage
                    original_url = await upload_to_supabase_storage(user_supabase, original_content, f"original_{filename}")
                    thumb_url = await upload_to_supabase_storage(user_supabase, thumb_content, f"thumb_{filename}")
                    
                    if original_url and thumb_url:
                        update_data["before_url"] = original_url
                        update_data["before_thumbnail_url"] = thumb_url
                    else:
                        error_msg = "Erreur lors de l'upload de l'image avant."
                
                # Traiter l'image après
                if after_image and after_image.filename and not error_msg:
                    after_content = after_image.file.read()
                    original_content, thumb_content, filename = process_image_for_upload(after_content, coach_id)
                    
                    # Upload sécurisé vers Supabase Storage
                    original_url = await upload_to_supabase_storage(user_supabase, original_content, f"original_{filename}")
                    thumb_url = await upload_to_supabase_storage(user_supabase, thumb_content, f"thumb_{filename}")
                    
                    if original_url and thumb_url:
                        update_data["after_url"] = original_url
                        update_data["after_thumbnail_url"] = thumb_url
                    else:
                        error_msg = "Erreur lors de l'upload de l'image après."
                
                # Gestion d'erreur et redirection
                if error_msg:
                    return RedirectResponse(url=f"/coach/portal?error={error_msg}", status_code=303)
                
                # Mettre à jour la transformation avec les URLs
                if update_data:
                    user_supabase.table("transformations").update(update_data).eq("id", transformation["id"]).execute()
                    
        except Exception as e:
            return RedirectResponse(url=f"/coach/portal?error=Erreur lors de l'upload: {str(e)}", status_code=303)
    
    return RedirectResponse(url="/coach/portal", status_code=303)

# ======================================
# UTILITAIRE - GÉNÉRATION DE SLUG
# ======================================

def generate_slug(name: str) -> str:
    """Génère un slug URL-friendly à partir d'un nom."""
    import unicodedata
    import re
    # Supprimer les accents
    slug = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Convertir en minuscules et supprimer les espaces
    slug = slug.lower().strip()
    # Remplacer les espaces par des tirets
    slug = re.sub(r'\s+', '-', slug)
    # Supprimer les caractères non-alphanumériques
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    return slug

def generate_unique_slug_for_coach(email: str, full_name: str) -> str:
    """Génère un slug unique pour un coach. Ajoute -2, -3, etc. si nécessaire."""
    from utils import load_demo_users
    demo_users = load_demo_users()
    
    # Extraire le prénom
    first_name = full_name.split()[0] if full_name.strip() else "coach"
    base_slug = generate_slug(first_name)
    
    if not base_slug:
        base_slug = "coach"
    
    # Vérifier si ce slug est déjà pris par un AUTRE coach
    existing_slugs = set()
    for other_email, user_data in demo_users.items():
        if user_data.get("role") == "coach" and other_email != email:
            if user_data.get("profile_slug"):
                existing_slugs.add(user_data.get("profile_slug"))
    
    # Si le slug de base est libre, l'utiliser
    if base_slug not in existing_slugs:
        return base_slug
    
    # Sinon, ajouter un suffixe numérique
    counter = 2
    while f"{base_slug}-{counter}" in existing_slugs:
        counter += 1
    
    return f"{base_slug}-{counter}"


def find_coach_by_slug(slug: str):
    """Trouve un coach par son slug unique stocké."""
    from utils import load_demo_users
    demo_users = load_demo_users()
    
    slug_lower = slug.lower()
    
    # 1. Chercher par slug stocké (priorité)
    for email, user_data in demo_users.items():
        if user_data.get("role") == "coach":
            stored_slug = user_data.get("profile_slug", "")
            if stored_slug and stored_slug.lower() == slug_lower:
                coach_data = user_data.copy()
                coach_data["email"] = email
                return coach_data
    
    # 2. Fallback: chercher par prénom (pour anciens comptes sans slug)
    for email, user_data in demo_users.items():
        if user_data.get("role") == "coach" and user_data.get("profile_completed"):
            full_name = user_data.get("full_name", "")
            first_name = full_name.split()[0] if full_name.strip() else ""
            coach_slug = generate_slug(first_name)
            
            if coach_slug == slug_lower:
                coach_data = user_data.copy()
                coach_data["email"] = email
                return coach_data
    
    return None

# ======================================
# ROUTE PUBLIQUE - RÉSERVATION AVEC SLUG
# ======================================

@app.get("/reserver/{slug}", response_class=HTMLResponse)
async def reserver_by_slug(request: Request, slug: str):
    """Page de profil coach avec URL propre (prénom)."""
    
    coach = find_coach_by_slug(slug)
    
    i18n_404 = get_i18n_context(request)
    if not coach:
        return templates.TemplateResponse("404.html", {"request": request, "message": f"Le coach '{slug}' n'a pas été trouvé.", **i18n_404}, status_code=404)
    subscription_status = coach.get("subscription_status", "")
    if subscription_status in ["blocked", "cancelled", "past_due"]:
        return templates.TemplateResponse("404.html", {"request": request, "message": f"Le profil de ce coach n'est plus accessible.", **i18n_404}, status_code=404)
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    
    # S'assurer que les spécialités sont une liste
    specialties = coach.get("specialties", [])
    if isinstance(specialties, str):
        try:
            import json
            coach["specialties"] = json.loads(specialties)
        except Exception:
            coach["specialties"] = [s.strip() for s in specialties.split(",") if s.strip()]
    
    # Récupérer les salles associées au coach
    gyms = []
    if coach.get("selected_gyms_data"):
        try:
            import json
            gyms_data = coach.get("selected_gyms_data")
            if isinstance(gyms_data, str) and gyms_data.strip():
                gyms = json.loads(gyms_data)
            elif isinstance(gyms_data, list):
                gyms = gyms_data
        except Exception:
            pass
    
    log.info(f"📋 Profil coach {slug}: spécialités={coach.get('specialties')}, salles={len(gyms)}")
    i18n_profile = get_i18n_context(request)
    return templates.TemplateResponse("coach_profile.html", {"request": request, "coach": coach, "gyms": gyms, "slug": slug, **i18n_profile})

@app.get("/reserver/{slug}/book", response_class=HTMLResponse)
async def booking_by_slug(request: Request, slug: str):
    """Page de réservation avec URL propre (prénom)."""
    coach = find_coach_by_slug(slug)
    i18n_book = get_i18n_context(request)
    if not coach:
        return templates.TemplateResponse("404.html", {"request": request, "message": f"Le coach '{slug}' n'a pas été trouvé.", **i18n_book}, status_code=404)
    subscription_status = coach.get("subscription_status", "")
    if subscription_status in ["blocked", "cancelled", "past_due"]:
        return templates.TemplateResponse("404.html", {"request": request, "message": f"Le profil de ce coach n'est plus accessible.", **i18n_book}, status_code=404)
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    gyms = []
    if coach.get("selected_gyms_data"):
        try:
            import json
            gyms = json.loads(coach.get("selected_gyms_data"))
        except Exception:
            pass
    # Identifiant stable pour les appels API (availability, bookings) - priorité au slug pour /reserver/{slug}/book
    coach = dict(coach)
    coach["id"] = coach.get("profile_slug") or slug or (coach.get("email") or "").replace("@", "_").replace(".", "_")
    return templates.TemplateResponse("booking.html", {"request": request, "coach": coach, "gyms": gyms, "slug": slug, **i18n_book})

# ======================================
# ROUTE ABONNEMENT COACH (doit être AVANT /coach/{coach_id})
# ======================================

@app.get("/coach/subscription/set-session", response_class=HTMLResponse)
async def coach_subscription_set_session(
    request: Request,
    signup_token: Optional[str] = Query(None),
):
    """Après inscription : redirige vers la page offre coach /coach/offre."""
    if not signup_token:
        return RedirectResponse(url="/coach-login?tab=signup&error=missing_token", status_code=302)
    email = _validate_signup_token(signup_token)
    if not email:
        return RedirectResponse(url="/coach-login?tab=signup&error=session_expired", status_code=302)
    base = _get_base_url(request)
    response = RedirectResponse(url=f"{base.rstrip('/')}/coach/offre?token={signup_token}", status_code=302)
    _set_session_cookie(response, email, request)
    return response


@app.get("/coach/pay", response_class=HTMLResponse)
async def coach_pay_page(
    request: Request,
    token: Optional[str] = Query(None),
):
    """Redirection vers la page offre coach (ancienne URL)."""
    if not token:
        return RedirectResponse(url="/coach-login?tab=signup", status_code=302)
    base = _get_base_url(request)
    return RedirectResponse(url=f"{base.rstrip('/')}/coach/offre?token={token}", status_code=302)


@app.get("/coach/offre", response_class=HTMLResponse)
async def coach_offre_page(
    request: Request,
    token: Optional[str] = Query(None),
):
    """
    Page landing "offre coach" : arguments FitMatch + choix abonnement (20€/mois ou 200€/an).
    Token requis pour authentification au checkout.
    """
    if not token:
        return RedirectResponse(url="/coach-login?tab=signup", status_code=302)
    email = _validate_signup_token(token)
    if not email:
        return RedirectResponse(url="/coach-login?tab=signup&error=session_expired", status_code=302)
    i18n = get_i18n_context(request)
    response = templates.TemplateResponse("coach_offre.html", {"request": request, **i18n})
    _set_session_cookie(response, email, request)
    return response


@app.get("/coach/subscription", response_class=HTMLResponse)
async def coach_subscription_page(
    request: Request, 
    user = Depends(require_coach_or_pending),
    success: Optional[str] = None,
    session_id: Optional[str] = None
):
    """Page d'abonnement pour les coachs (accessible même sans abonnement actif)."""
    import stripe
    
    coach_email = user.get("email")
    
    # Si retour de Stripe avec succès, vérifier et activer l'abonnement
    if success == "true" and session_id:
        payment_confirmed = False
        try:
            init_stripe()
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            if checkout_session.payment_status == "paid":
                payment_confirmed = True
                subscription_id = checkout_session.subscription
                customer_id = checkout_session.customer
                
                try:
                    if subscription_id:
                        subscription = stripe.Subscription.retrieve(subscription_id)
                        period_end = datetime.fromtimestamp(subscription.current_period_end).isoformat()
                        
                        update_coach_subscription(
                            coach_email=coach_email,
                            stripe_customer_id=customer_id,
                            stripe_subscription_id=subscription_id,
                            subscription_status="active",
                            current_period_end=period_end
                        )
                        log.info(f"✅ Abonnement activé via redirect pour {coach_email}")
                    else:
                        update_coach_subscription(
                            coach_email=coach_email,
                            stripe_customer_id=customer_id,
                            subscription_status="active"
                        )
                        log.info(f"✅ Paiement confirmé (sans subscription_id) pour {coach_email}")
                except Exception as sub_err:
                    log.warning(f"Erreur récupération détails abonnement: {sub_err}")
                    # Activer quand même l'abonnement
                    update_coach_subscription(
                        coach_email=coach_email,
                        stripe_customer_id=customer_id if customer_id else "",
                        subscription_status="active"
                    )
                
        except Exception as e:
            log.warning(f"Erreur vérification session Stripe: {e}")
            # Si on a un session_id valide, on considère le paiement comme fait
            payment_confirmed = True
            update_coach_subscription(
                coach_email=coach_email,
                subscription_status="active"
            )
        
        # Toujours générer et envoyer l'OTP si le paiement semble confirmé
        if payment_confirmed:
            import random
            from resend_service import send_otp_email_resend
            
            otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            otp_expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
            
            # Sauvegarder l'OTP dans les données du coach
            demo_users = load_demo_users()
            if coach_email in demo_users:
                demo_users[coach_email]["otp_code"] = otp_code
                demo_users[coach_email]["otp_expiry"] = otp_expiry
                demo_users[coach_email]["email_verified"] = False
                save_demo_users(demo_users)
                log.info(f"✅ OTP sauvegardé pour {coach_email}")
            else:
                # Créer l'entrée si elle n'existe pas
                demo_users[coach_email] = {
                    "email": coach_email,
                    "otp_code": otp_code,
                    "otp_expiry": otp_expiry,
                    "email_verified": False,
                    "subscription_status": "active"
                }
                save_demo_users(demo_users)
                log.info(f"✅ Nouvelle entrée + OTP créés pour {coach_email}")
            
            # Envoyer l'email avec le code
            full_name = user.get("full_name", "Coach")
            locale = get_locale_from_request(request)
            try:
                send_otp_email_resend(coach_email, otp_code, full_name, lang=locale)
                log.info(f"📧 Code OTP envoyé à {coach_email}: {otp_code}")
            except Exception as email_err:
                log.warning(f"Erreur envoi email OTP: {email_err}")
            
            # Rediriger vers la page de vérification email
            return RedirectResponse(url="/coach/verify-email", status_code=303)
    
    # Charger les données fraîches depuis le fichier JSON
    demo_users = load_demo_users()
    coach_data_fresh = demo_users.get(coach_email, {})
    
    subscription_info = get_coach_subscription_info(coach_email)
    
    stripe_available = _is_stripe_configured()
    try:
        publishable_key = get_publishable_key() if stripe_available else ""
    except Exception:
        publishable_key = ""
        stripe_available = False
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_subscription.html", {
        "request": request,
        "coach": user,
        "subscription_info": subscription_info,
        "monthly_price": COACH_MONTHLY_PRICE // 100,
        "annual_price": (COACH_ANNUAL_PRICE // 100) if STRIPE_AVAILABLE else 300,
        "publishable_key": publishable_key,
        "stripe_available": stripe_available,
        "t": translations,
        "locale": locale
    })

# ======================================
# ROUTES verify-email (post-paiement Stripe, OTP DB)
# ======================================

@app.get("/verify-email", response_class=HTMLResponse)
async def verify_email_redirect(
    request: Request,
    email: Optional[str] = Query(None),
    payment: Optional[str] = Query(None),
):
    """Redirige vers /coach/verify-email (alias pour compatibilité)."""
    from urllib.parse import quote
    params = []
    if email:
        params.append(f"email={quote(email)}")
    if payment:
        params.append(f"payment={payment}")
    qs = "&".join(params)
    url = f"/coach/verify-email?{qs}" if qs else "/coach/verify-email"
    return RedirectResponse(url=url, status_code=302)


@app.get("/coach/verify-email", response_class=HTMLResponse)
async def coach_verify_email_page(
    request: Request,
    email: Optional[str] = Query(None),
    payment: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Page de saisie du code OTP après paiement. PUBLIC, pas d'auth. Email en query."""
    if not email:
        email = get_session_email(request)
    email_val = (email or "").strip().lower()
    payment_success = payment == "success"
    i18n = get_i18n_context(request)
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("verify_email_subscription.html", {
        "request": request,
        "email": email_val,
        "payment_success": payment_success,
        "error": error,
        "t": translations,
        "locale": locale,
        "csp_nonce": getattr(request.state, "csp_nonce", ""),
    })


@app.get("/api/coach/verify-email")
async def api_coach_verify_email_get():
    """API uniquement en POST. GET retourne 405."""
    return JSONResponse({"detail": "Method Not Allowed"}, status_code=405)


@app.post("/api/coach/verify-email")
@limiter.limit("10/minute")
async def api_coach_verify_email_post(request: Request):
    """Vérifie le code OTP, crée la session (request.session), retourne JSON. PUBLIC, pas d'auth."""
    try:
        data = await request.json()
        email = (data.get("email") or "").strip().lower()
        code = (data.get("code") or data.get("otp_code") or "").strip()
        if not email or not code:
            return JSONResponse({"success": False, "error": "Code invalide ou expiré"}, status_code=400)
        if len(code) != 6:
            return JSONResponse({"success": False, "error": "Code invalide"}, status_code=400)
        from email_verification_service import verify_email_code
        ok, err = verify_email_code(email, code)
        if not ok:
            return JSONResponse({"success": False, "error": err or "Code invalide ou expiré"}, status_code=400)
        coach_data = get_demo_user(email)
        if not coach_data:
            new_user = {
                "email": email,
                "full_name": "",
                "role": "coach",
                "subscription_status": "active",
                "profile_completed": False,
            }
            save_demo_user(email, new_user)
            coach_data = get_demo_user(email) or new_user
            log.info(f"Utilisateur coach cree automatiquement: {email}")
        if coach_data.get("role") != "coach":
            return JSONResponse({"success": False, "error": "Compte non trouvé"}, status_code=404)
        # OTP verifié = paiement effectué : accepter et activer l'abonnement si besoin
        sub_status = coach_data.get("subscription_status", "")
        if sub_status not in ("active", "trialing"):
            coach_data["subscription_status"] = "active"
            save_demo_user(email, coach_data)
            log.info(f"Abonnement active pour {email} apres verification OTP")
        # Session serveur (cookie "session") : requis pour get_session_email
        request.session["user_email"] = email
        request.session["coach_email"] = email
        request.session["is_coach"] = True
        request.session["subscription_status"] = "active"
        log.info(f"Email verifie pour {email}, session creee")
        profile_completed = coach_data.get("profile_completed", False)
        redirect_url = "/coach/portal" if profile_completed else "/coach/profile-setup"
        # JSON + cookies : session (SessionMiddleware) ET session_token (fallback pour get_current_user)
        # Certains navigateurs/proxies ne transmettent pas correctement "session" -> session_token assure l'auth
        resp = JSONResponse({"success": True, "redirect": redirect_url})
        _set_session_cookie(resp, email, request)
        return resp
    except Exception as e:
        log.error(f"Erreur verify_email: {e}")
        return JSONResponse({"success": False, "error": "Erreur serveur"}, status_code=500)


@app.post("/api/coach/verify-email/resend")
@limiter.limit("3/minute")
async def api_coach_verify_email_resend(request: Request):
    """Renvoye un nouveau code OTP. PUBLIC, pas d'auth."""
    try:
        data = await request.json()
        email = (data.get("email") or "").strip().lower()
        if not email:
            return JSONResponse({"success": False, "error": "Email requis"}, status_code=400)
        from email_verification_service import send_email_verification_code
        ok, err = send_email_verification_code(email)
        if ok:
            return JSONResponse({"success": True})
        return JSONResponse({"success": False, "error": err or "Erreur envoi"}, status_code=400)
    except Exception as e:
        log.error(f"Erreur verify_email resend: {e}")
        return JSONResponse({"success": False, "error": "Erreur serveur"}, status_code=500)


@app.post("/api/coach/resend-otp")
@limiter.limit("3/minute")
async def resend_coach_otp(request: Request):
    """Alias pour /api/coach/verify-email/resend (compatibilité)."""
    return await api_coach_verify_email_resend(request)

# ======================================
# ROUTE PUBLIQUE - PROFIL DU COACH
# ======================================

@app.get("/coach/{coach_id}", response_class=HTMLResponse)
async def view_coach_profile(request: Request, coach_id: str):
    """Affiche le profil public d'un coach."""
    
    # Charger tous les coaches
    coaches = load_coaches_from_json()
    
    # Trouver le coach par ID (convertir en int si nécessaire)
    coach = None
    try:
        coach_id_int = int(coach_id)
        coach = next((c for c in coaches if c.get("id") == coach_id_int), None)
    except ValueError:
        # Si l'ID n'est pas un nombre, chercher par chaîne
        coach = next((c for c in coaches if str(c.get("id")) == coach_id), None)
    
    # Si coach non trouvé par ID, essayer Supabase puis la base de données
    if not coach:
        user_supabase = None
        if supabase_anon:
            try:
                response = supabase_anon.table("profiles").select("*").eq("user_id", coach_id).single().execute()
                if response.data:
                    coach = response.data
            except Exception as e:
                log.info(f"Coach non trouvé dans Supabase: {e}")
        
        if not coach:
            from utils import load_demo_users
            demo_users = load_demo_users()
            for email, user_data in demo_users.items():
                # Encoder l'email pour comparer avec coach_id (format: email@domain.com -> email_domain_com)
                encoded_email = email.replace("@", "_").replace(".", "_")
                if user_data.get("role") == "coach" and (str(user_data.get("id")) == coach_id or user_data.get("email") == coach_id or encoded_email == coach_id):
                    coach = user_data
                    break
    
    if not coach:
        raise HTTPException(status_code=404, detail="Coach non trouvé")
    
    # Vérifier si le coach est bloqué - cacher son profil
    subscription_status = coach.get("subscription_status", "")
    is_blocked = subscription_status in ["blocked", "cancelled", "past_due"]
    if is_blocked:
        raise HTTPException(status_code=404, detail="Profil temporairement indisponible")
    
    # Cacher le lien Instagram si abonnement non actif
    if subscription_status not in ["active", "trialing", ""]:
        coach["instagram"] = None
    
    # Assurer qu'il y a une photo (profile_photo_url ou photo, sinon défaut)
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    
    # S'assurer que les spécialités sont une liste
    specialties = coach.get("specialties", [])
    if isinstance(specialties, str):
        try:
            import json
            coach["specialties"] = json.loads(specialties)
        except Exception:
            coach["specialties"] = [s.strip() for s in specialties.split(",") if s.strip()]
    
    # Récupérer les salles associées au coach
    gyms = []
    if coach.get("gyms"):
        gym_ids = coach.get("gyms", [])
        gyms_map = get_gyms_by_ids(gym_ids)
        gyms = [gyms_map[gid] for gid in gym_ids if gid in gyms_map]
    elif coach.get("selected_gyms_data"):
        # Pour les coaches avec selected_gyms_data (format JSON string)
        try:
            import json
            gyms_data = coach.get("selected_gyms_data")
            if isinstance(gyms_data, str) and gyms_data.strip():
                gyms = json.loads(gyms_data)
            elif isinstance(gyms_data, list):
                gyms = gyms_data
        except Exception:
            pass
    
    log.info(f"📋 Profil coach {coach_id}: spécialités={coach.get('specialties')}, salles={len(gyms)}")
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_profile.html", {
        "request": request,
        "coach": coach,
        "gyms": gyms
    })

# ======================================
# SYSTÈME DE RÉSERVATION
# ======================================

@app.get("/coach/{coach_id}/book", response_class=HTMLResponse)
async def booking_page(request: Request, coach_id: str):
    """Page de réservation pour un coach."""
    # Charger les infos du coach (même logique que view_coach_profile)
    coaches = load_coaches_from_json()
    
    coach = None
    try:
        coach_id_int = int(coach_id)
        coach = next((c for c in coaches if c.get("id") == coach_id_int), None)
    except ValueError:
        coach = next((c for c in coaches if str(c.get("id")) == coach_id), None)
    
    if not coach:
        if supabase_anon:
            try:
                response = supabase_anon.table("profiles").select("*").eq("user_id", coach_id).single().execute()
                if response.data:
                    coach = response.data
            except Exception as e:
                log.info(f"Coach non trouvé dans Supabase: {e}")
        
        if not coach:
            from utils import load_demo_users
            demo_users = load_demo_users()
            for email, user_data in demo_users.items():
                encoded_email = email.replace("@", "_").replace(".", "_")
                if user_data.get("role") == "coach" and (str(user_data.get("id")) == coach_id or user_data.get("email") == coach_id or encoded_email == coach_id):
                    coach = user_data.copy()
                    coach["email"] = email
                    break
    
    if not coach:
        raise HTTPException(status_code=404, detail="Coach non trouvé")
    
    subscription_status = coach.get("subscription_status", "")
    is_blocked = subscription_status in ["blocked", "cancelled", "past_due"]
    if is_blocked:
        raise HTTPException(status_code=404, detail="Profil temporairement indisponible")
    
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    
    # Parser les données des salles pour le template
    gyms = []
    if coach.get("selected_gyms_data"):
        try:
            import json
            gyms_data = coach["selected_gyms_data"]
            gyms = json.loads(gyms_data) if isinstance(gyms_data, str) else gyms_data
        except Exception:
            pass
    if not gyms and coach.get("gyms"):
        gyms = coach["gyms"]
    
    i18n_book = get_i18n_context(request)
    return templates.TemplateResponse("booking.html", {
        "request": request,
        "coach": coach,
        "gyms": gyms,
        **i18n_book
    })

@app.get("/reservation", response_class=HTMLResponse)
async def reservation_page(request: Request):
    """Page de confirmation de réservation avec identification."""
    import time
    i18n = get_i18n_context(request)
    return templates.TemplateResponse("reservation.html", {
        "request": request,
        "cache_bust": int(time.time()),
        **i18n
    })

@app.get("/account", response_class=HTMLResponse)
async def account_page(
    request: Request,
    user=Depends(get_current_user),
    tab: Optional[str] = Query(None),
):
    """Page Mon compte : redirection vers /mon-compte si client, sinon page compte (coach) avec onglet."""
    i18n = get_i18n_context(request)
    if user and user.get("email") and (user.get("role") or "client") == "client":
        return RedirectResponse(url="/mon-compte", status_code=303)
    return templates.TemplateResponse("account.html", {
        "request": request,
        "account_tab": tab or "bookings",
        **i18n
    })


@app.get("/account/info", response_class=HTMLResponse)
async def account_info_page(request: Request, user=Depends(get_current_user)):
    """Redirige vers la page compte, onglet Mes informations."""
    if user and user.get("email") and (user.get("role") or "client") == "client":
        return RedirectResponse(url="/mon-compte", status_code=303)
    return RedirectResponse(url="/account?tab=info", status_code=302)


@app.get("/account/payments", response_class=HTMLResponse)
async def account_payments_page(request: Request, user=Depends(get_current_user)):
    """Redirige vers la page compte, onglet Mes paiements."""
    if user and user.get("email") and (user.get("role") or "client") == "client":
        return RedirectResponse(url="/mon-compte", status_code=303)
    return RedirectResponse(url="/account?tab=payments", status_code=302)

@app.get("/api/bookings/availability")
async def get_availability(coach_id: str, from_date: str = Query(..., alias="from"), to_date: str = Query(..., alias="to")):
    """Récupère les disponibilités d'un coach pour une période donnée, basées sur les horaires de travail."""
    try:
        from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        # Charger les données du coach
        demo_users = load_demo_users()
        coach_email = None
        coach_data = None
        
        for email, user_data in demo_users.items():
            encoded_email = email.replace("@", "_").replace(".", "_")
            user_slug = user_data.get("slug", "") or user_data.get("profile_slug", "")
            if user_data.get("role") == "coach" and (
                str(user_data.get("id")) == coach_id or 
                user_data.get("email") == coach_id or 
                encoded_email == coach_id or
                user_slug == coach_id or
                str(coach_id).lower() == str(user_slug).lower()
            ):
                coach_email = email
                coach_data = user_data
                break
        
        # Récupérer les indisponibilités
        unavailable_dates = set()
        if coach_data:
            for date_str in coach_data.get("unavailable_days", []):
                unavailable_dates.add(date_str)
        
        # Récupérer les horaires de travail (8h-23h par défaut pour permettre séances jusqu'à 22h)
        day_names = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        default_hours = {
            "monday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "tuesday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "wednesday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "thursday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "friday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "saturday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "sunday": {"enabled": True, "start": "08:00", "end": "23:00"}
        }
        wh_raw = coach_data.get("working_hours", default_hours) if coach_data else default_hours
        if isinstance(wh_raw, str):
            try:
                working_hours = json.loads(wh_raw) if wh_raw else default_hours
            except Exception:
                working_hours = default_hours
        else:
            working_hours = wh_raw if isinstance(wh_raw, dict) else default_hours
        
        availability = []
        current = from_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current <= to_dt:
            date_str = current.strftime("%Y-%m-%d")
            
            # Si le jour complet est indisponible, on passe au suivant
            if date_str in unavailable_dates:
                current += timedelta(days=1)
                continue
            
            # Récupérer le jour de la semaine (0=lundi, 6=dimanche)
            weekday = current.weekday()
            day_name = day_names[weekday]
            
            # Récupérer les horaires pour ce jour
            day_config = working_hours.get(day_name, default_hours[day_name])
            
            if day_config.get("enabled", True):
                # Parser les horaires
                start_time = day_config.get("start", "08:00")
                end_time = day_config.get("end", "20:00")
                
                start_hour, start_min = map(int, start_time.split(":"))
                end_hour, end_min = map(int, end_time.split(":"))
                
                # Créer le créneau de disponibilité (sans timezone pour éviter les décalages)
                date_str = current.strftime("%Y-%m-%d")
                availability.append({
                    "start": f"{date_str}T{start_time}:00",
                    "end": f"{date_str}T{end_time}:00"
                })
            
            current += timedelta(days=1)
        
        return availability
    except Exception as e:
        log.info(f"Erreur lors de la récupération des disponibilités: {e}")
        return []

@app.get("/api/coach/unavailability")
async def get_coach_unavailability(coach_email: str):
    """Récupère les indisponibilités d'un coach."""
    try:
        demo_users = load_demo_users()
        coach_data = demo_users.get(coach_email, {})
        
        return {
            "unavailable_days": coach_data.get("unavailable_days", []),
            "unavailable_slots": coach_data.get("unavailable_slots", [])
        }
    except Exception as e:
        log.info(f"Erreur: {e}")
        return {"unavailable_days": [], "unavailable_slots": []}

@app.post("/api/coach/unavailability")
async def set_coach_unavailability(request: Request, user=Depends(require_coach_session_or_cookie)):
    """Ajoute ou supprime des indisponibilités pour un coach."""
    try:
        data = await request.json()
        coach_email = user.get("email") or data.get("coach_email")
        action = data.get("action")  # "add" ou "remove"
        unavailable_type = data.get("type")  # "day" ou "slot"
        date = data.get("date")  # Format: "2025-12-05"
        time = data.get("time")  # Format: "14:00" (pour les créneaux)
        
        if not coach_email or not action or not date:
            return JSONResponse(status_code=400, content={"error": "Paramètres manquants"})
        
        demo_users = load_demo_users()
        
        if coach_email not in demo_users:
            return JSONResponse(status_code=404, content={"error": "Coach non trouvé"})
        
        coach_data = demo_users[coach_email]
        
        # Initialiser les listes si elles n'existent pas
        if "unavailable_days" not in coach_data:
            coach_data["unavailable_days"] = []
        if "unavailable_slots" not in coach_data:
            coach_data["unavailable_slots"] = []
        
        if unavailable_type == "day":
            # Gérer les jours complets
            if action == "add":
                if date not in coach_data["unavailable_days"]:
                    coach_data["unavailable_days"].append(date)
            elif action == "remove":
                if date in coach_data["unavailable_days"]:
                    coach_data["unavailable_days"].remove(date)
        
        elif unavailable_type == "slot" and time:
            # Gérer les créneaux spécifiques
            slot = {"date": date, "time": time}
            if action == "add":
                if slot not in coach_data["unavailable_slots"]:
                    coach_data["unavailable_slots"].append(slot)
            elif action == "remove":
                coach_data["unavailable_slots"] = [
                    s for s in coach_data["unavailable_slots"] 
                    if not (s.get("date") == date and s.get("time") == time)
                ]
        
        # Sauvegarder (utiliser save_demo_user pour une mise à jour atomique)
        save_demo_user(coach_email, coach_data)
        
        return {
            "success": True,
            "unavailable_days": coach_data["unavailable_days"],
            "unavailable_slots": coach_data["unavailable_slots"]
        }
        
    except Exception as e:
        log.info(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/coach/working-hours")
async def get_coach_working_hours(coach_email: str):
    """Récupère les horaires de travail d'un coach."""
    try:
        demo_users = load_demo_users()
        coach_data = demo_users.get(coach_email, {})
        
        # Horaires par défaut (8h-23h tous les jours pour permettre séances jusqu'à 22h)
        default_hours = {
            "monday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "tuesday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "wednesday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "thursday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "friday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "saturday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "sunday": {"enabled": True, "start": "08:00", "end": "23:00"}
        }
        
        wh = coach_data.get("working_hours", default_hours)
        if isinstance(wh, str):
            try:
                wh = json.loads(wh) if wh else default_hours
            except Exception:
                wh = default_hours
        return wh if isinstance(wh, dict) else default_hours
    except Exception as e:
        log.info(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/coach/working-hours")
async def set_coach_working_hours(request: Request, user=Depends(require_coach_session_or_cookie)):
    """Définit les horaires de travail d'un coach."""
    try:
        data = await request.json()
        coach_email = user.get("email") or data.get("coach_email")
        working_hours = data.get("working_hours")
        
        if not coach_email or not working_hours:
            return JSONResponse(status_code=400, content={"error": "Missing data"})
        
        demo_users = load_demo_users()
        
        if coach_email not in demo_users:
            return JSONResponse(status_code=404, content={"error": "Coach not found"})
        
        coach_data = demo_users[coach_email]
        coach_data["working_hours"] = working_hours
        save_demo_user(coach_email, coach_data)
        
        return {"success": True, "working_hours": working_hours}
        
    except Exception as e:
        log.info(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/coach/session-duration")
async def get_coach_session_duration(coach_email: str):
    """Récupère la durée de séance d'un coach."""
    try:
        demo_users = load_demo_users()
        coach_data = demo_users.get(coach_email, {})
        duration = coach_data.get("session_duration", 60)  # 60 min par défaut
        return {"success": True, "duration": duration}
    except Exception as e:
        log.info(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/coach/session-duration")
async def set_coach_session_duration(request: Request, user=Depends(require_coach_session_or_cookie)):
    """Définit la durée de séance d'un coach."""
    try:
        data = await request.json()
        coach_email = user.get("email") or data.get("coach_email")
        duration = data.get("duration")
        
        try:
            duration = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            duration = None
        if not coach_email or duration not in [30, 60, 90, 120]:
            return JSONResponse(status_code=400, content={"success": False, "error": "Données invalides"})
        
        demo_users = load_demo_users()
        
        if coach_email not in demo_users:
            return JSONResponse(status_code=404, content={"success": False, "error": "Coach non trouvé"})
        
        demo_users[coach_email]["session_duration"] = duration
        save_demo_user(coach_email, demo_users[coach_email])
        
        log.info(f"Durée de séance mise à jour pour {coach_email}: {duration} min")
        
        return {"success": True, "duration": duration}
        
    except Exception as e:
        log.info(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/coach/pricing")
async def get_coach_pricing(coach_email: str):
    """Récupère le prix actuel d'une séance d'un coach."""
    try:
        demo_users = load_demo_users()
        coach_data = demo_users.get(coach_email, {})
        # Essayer session_price puis price_from
        price = coach_data.get("session_price") or coach_data.get("price_from") or 40
        log.info(f"💰 Prix coach {coach_email}: {price}€")
        return {"success": True, "price": price}
    except Exception as e:
        log.info(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/coach/payment-mode")
async def set_coach_payment_mode(request: Request, user = Depends(require_coach_session_or_cookie)):
    """Definit le mode de paiement d'un coach (disabled ou required)."""
    try:
        from stripe_connect_facade import get_stripe_connect_info
        
        data = await request.json()
        payment_mode = data.get("payment_mode")
        
        if payment_mode not in ["disabled", "required"]:
            return JSONResponse(status_code=400, content={"success": False, "error": "Mode invalide"})
        
        coach_email = user.get("email")
        demo_users = load_demo_users()
        
        if coach_email not in demo_users:
            return JSONResponse(status_code=404, content={"success": False, "error": "Coach non trouve"})
        
        if payment_mode == "required":
            connect_info = get_stripe_connect_info(coach_email)
            log.info(f"📋 Vérification Stripe Connect pour {coach_email}")
            log.info(f"   Connect Info: {connect_info}")
            if not connect_info:
                log.info(f"   ❌ Pas de compte Stripe Connect")
                return JSONResponse(status_code=400, content={
                    "success": False, 
                    "error": "Vous devez d'abord connecter votre compte Stripe pour activer le paiement en ligne.",
                    "need_stripe_connect": True
                })
            
            # Vérifier que le compte Stripe est complètement vérifié
            if not connect_info.get("charges_enabled"):
                details_submitted = connect_info.get("details_submitted", False)
                
                log.info(f"   ⚠️  charges_enabled = False")
                log.info(f"   Account ID: {connect_info.get('account_id')}")
                log.info(f"   Details submitted: {details_submitted}")
                
                # Rejeter les comptes non vérifiés
                return JSONResponse(status_code=400, content={
                    "success": False, 
                    "error": "Votre compte Stripe n'est pas encore vérifié. Veuillez compléter la vérification de votre identité sur Stripe avant d'activer le paiement obligatoire.",
                    "need_stripe_connect": True,
                    "charges_enabled": False,
                    "details_submitted": details_submitted
                })
        
        demo_users[coach_email]["payment_mode"] = payment_mode
        save_demo_user(coach_email, demo_users[coach_email])
        
        log.info(f"✅ Mode de paiement mis a jour pour {coach_email}: {payment_mode}")
        
        return {"success": True, "payment_mode": payment_mode}
        
    except Exception as e:
        log.error(f"Erreur mise a jour mode paiement: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/coach/{coach_id}/payment-mode")
async def get_coach_payment_mode(coach_id: str):
    """Récupère le mode de paiement d'un coach (public, pour le frontend de réservation)."""
    try:
        demo_users = load_demo_users()
        
        # Chercher le coach par ID, email ou slug
        coach_email = None
        for email, user_data in demo_users.items():
            if user_data.get("role") != "coach":
                continue
            encoded_email = email.replace("@", "_").replace(".", "_")
            user_slug = user_data.get("profile_slug", "")
            if (email == coach_id or 
                encoded_email == coach_id or
                user_slug == coach_id):
                coach_email = email
                break
        
        if not coach_email:
            return {"payment_mode": "disabled"}  # Par défaut si coach non trouvé
        
        coach_data = demo_users.get(coach_email, {})
        payment_mode = coach_data.get("payment_mode", "disabled")
        
        return {
            "payment_mode": payment_mode,
            "coach_email": coach_email,
            "coach_name": coach_data.get("full_name", "Coach"),
            "price_from": coach_data.get("price_from", 50)
        }
        
    except Exception as e:
        log.info(f"Erreur récupération mode paiement: {e}")
        return {"payment_mode": "disabled"}


@app.get("/api/coach/stripe-connect/status")
async def get_stripe_connect_status(user = Depends(require_coach_session_or_cookie)):
    """Récupère le statut Stripe Connect d'un coach."""
    try:
        from stripe_connect_facade import get_stripe_connect_info
        from stripe_connect_service import get_account_status
        
        coach_email = user.get("email")
        connect_info = get_stripe_connect_info(coach_email)
        
        if not connect_info or not connect_info.get("account_id"):
            return {
                "connected": False,
                "status": "not_connected",
                "message": "Compte Stripe non connecté"
            }
        
        account_status = get_account_status(connect_info["account_id"])
        
        if not account_status.get("success"):
            return {
                "connected": False,
                "status": "error",
                "message": "Erreur de connexion avec Stripe"
            }
        
        return {
            "connected": True,
            "status": account_status.get("status"),
            "charges_enabled": account_status.get("charges_enabled"),
            "payouts_enabled": account_status.get("payouts_enabled"),
            "details_submitted": account_status.get("details_submitted"),
            "currently_due": account_status.get("currently_due", []),
            "message": "Compte Stripe actif" if account_status.get("charges_enabled") else "Configuration en cours"
        }
        
    except Exception as e:
        log.info(f"Erreur statut Stripe Connect: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/coach/stripe-connect/onboard")
async def start_stripe_connect_onboarding(request: Request, user = Depends(require_coach_session_or_cookie)):
    """Démarre l'onboarding Stripe Connect pour un coach."""
    try:
        from stripe_connect_facade import get_stripe_connect_info, update_stripe_connect_status
        from stripe_connect_service import create_connect_account, create_account_link
        
        coach_email = user.get("email")
        coach_name = user.get("full_name", "Coach")
        
        base_url = _get_base_url(request)
        connect_info = get_stripe_connect_info(coach_email)
        account_id = connect_info.get("account_id") if connect_info else None
        
        if not account_id:
            result = create_connect_account(coach_email, coach_name)
            if not result.get("success"):
                return JSONResponse(status_code=500, content={
                    "success": False,
                    "error": result.get("error", "Erreur création compte Stripe")
                })
            account_id = result["account_id"]
            update_stripe_connect_status(
                email=coach_email,
                account_id=account_id,
                status="pending"
            )
        
        link_result = create_account_link(
            account_id=account_id,
            return_url=f"{base_url}/coach/portal?stripe_connected=1",
            refresh_url=f"{base_url}/api/coach/stripe-connect/refresh"
        )
        
        if not link_result.get("success"):
            return JSONResponse(status_code=500, content={
                "success": False,
                "error": link_result.get("error", "Erreur création lien Stripe")
            })
        
        return {
            "success": True,
            "onboarding_url": link_result["url"]
        }
        
    except Exception as e:
        log.info(f"Erreur onboarding Stripe Connect: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/coach/stripe-connect/refresh")
async def refresh_stripe_connect_onboarding(request: Request, user = Depends(require_coach_session_or_cookie)):
    """Génère un nouveau lien d'onboarding si l'ancien a expiré."""
    try:
        from stripe_connect_facade import get_stripe_connect_info
        from stripe_connect_service import create_account_link
        
        coach_email = user.get("email")
        connect_info = get_stripe_connect_info(coach_email)
        
        if not connect_info or not connect_info.get("account_id"):
            return RedirectResponse(url="/coach/portal?error=no_account")
        
        base_url = _get_base_url(request)
        link_result = create_account_link(
            account_id=connect_info["account_id"],
            return_url=f"{base_url}/coach/portal?stripe_connected=1",
            refresh_url=f"{base_url}/api/coach/stripe-connect/refresh"
        )
        
        if link_result.get("success"):
            return RedirectResponse(url=link_result["url"])
        
        return RedirectResponse(url="/coach/portal?error=stripe_link")
        
    except Exception as e:
        log.info(f"Erreur refresh Stripe Connect: {e}")
        return RedirectResponse(url="/coach/portal?error=stripe_error")


@app.post("/api/coach/stripe-connect/sync")
async def sync_stripe_connect_status(user = Depends(require_coach_session_or_cookie)):
    """Synchronise le statut Stripe Connect après le retour de l'onboarding."""
    try:
        from stripe_connect_facade import get_stripe_connect_info, update_stripe_connect_status
        from stripe_connect_service import get_account_status
        
        coach_email = user.get("email")
        connect_info = get_stripe_connect_info(coach_email)
        
        if not connect_info or not connect_info.get("account_id"):
            return {"success": False, "error": "Aucun compte Stripe Connect"}
        
        status_result = get_account_status(connect_info["account_id"])
        
        if not status_result.get("success"):
            return {"success": False, "error": "Impossible de récupérer le statut"}
        
        update_stripe_connect_status(
            email=coach_email,
            status=status_result.get("status"),
            charges_enabled=status_result.get("charges_enabled"),
            payouts_enabled=status_result.get("payouts_enabled"),
            details_submitted=status_result.get("details_submitted")
        )
        
        return {
            "success": True,
            "status": status_result.get("status"),
            "charges_enabled": status_result.get("charges_enabled"),
            "payouts_enabled": status_result.get("payouts_enabled")
        }
        
    except Exception as e:
        log.info(f"Erreur sync Stripe Connect: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/bookings")
async def get_bookings(coach_id: str, from_date: str = Query(..., alias="from"), to_date: str = Query(..., alias="to"), include_pending: bool = Query(False)):
    """Récupère les réservations existantes d'un coach.
    
    Args:
        include_pending: Si True, inclut les réservations en attente (pour le calendrier du coach).
                        Si False, n'inclut que les confirmées (pour le calendrier de réservation client).
    """
    # Charger depuis la base de données
    try:
        demo_users = load_demo_users()
        
        # Chercher le coach par ID ou slug
        coach_email = None
        for email, user_data in demo_users.items():
            encoded_email = email.replace("@", "_").replace(".", "_")
            user_slug = user_data.get("slug", "") or user_data.get("profile_slug", "")
            if user_data.get("role") == "coach" and (
                str(user_data.get("id")) == coach_id or 
                user_data.get("email") == coach_id or 
                encoded_email == coach_id or
                user_slug == coach_id or
                str(coach_id).lower() == str(user_slug).lower()
            ):
                coach_email = email
                break
        
        if not coach_email:
            return []
        
        coach_data = demo_users.get(coach_email, {})
        
        # Récupérer les réservations selon le contexte
        pending_bookings = coach_data.get("pending_bookings", []) if include_pending else []
        confirmed_bookings = coach_data.get("confirmed_bookings", [])
        
        # Récupérer les indisponibilités
        unavailable_days = coach_data.get("unavailable_days", [])
        unavailable_slots = coach_data.get("unavailable_slots", [])
        
        # Récupérer les horaires de travail (8h-23h par défaut tous les jours pour permettre séances jusqu'à 22h)
        default_hours = {
            "monday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "tuesday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "wednesday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "thursday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "friday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "saturday": {"enabled": True, "start": "08:00", "end": "23:00"},
            "sunday": {"enabled": True, "start": "08:00", "end": "23:00"}
        }
        wh_raw = coach_data.get("working_hours", default_hours)
        if isinstance(wh_raw, str):
            try:
                working_hours = json.loads(wh_raw) if wh_raw else default_hours
            except Exception:
                working_hours = default_hours
        else:
            working_hours = wh_raw if isinstance(wh_raw, dict) else default_hours
        
        # Filtrer par période
        from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        filtered_bookings = []
        
        # Ajouter les réservations pending
        session_dur = coach_data.get("session_duration", 60)
        for booking in pending_bookings:
            booking_date = booking.get("date", "")
            booking_time = booking.get("time", "")
            if booking_date and booking_time:
                try:
                    booking_start = datetime.fromisoformat(f"{booking_date}T{booking_time}:00")
                    dur_mins = int(booking.get("duration", session_dur)) if str(booking.get("duration", session_dur)).isdigit() else session_dur
                    booking_end = booking_start + timedelta(minutes=dur_mins)
                    if from_dt.date() <= booking_start.date() <= to_dt.date():
                        filtered_bookings.append({
                            "start": booking_start.isoformat(),
                            "end": booking_end.isoformat(),
                            "title": f"{booking.get('client_name', 'Client')} - En attente",
                            "status": "pending"
                        })
                except Exception:
                    pass
        
        # Ajouter les réservations confirmées
        for booking in confirmed_bookings:
            booking_date = booking.get("date", "")
            booking_time = booking.get("time", "")
            if booking_date and booking_time:
                try:
                    booking_start = datetime.fromisoformat(f"{booking_date}T{booking_time}:00")
                    dur_mins = int(booking.get("duration", session_dur)) if str(booking.get("duration", session_dur)).isdigit() else session_dur
                    booking_end = booking_start + timedelta(minutes=dur_mins)
                    if from_dt.date() <= booking_start.date() <= to_dt.date():
                        filtered_bookings.append({
                            "start": booking_start.isoformat(),
                            "end": booking_end.isoformat(),
                            "title": f"{booking.get('client_name', 'Client')} - Confirmé",
                            "status": "confirmed"
                        })
                except Exception:
                    pass
        
        slot_mins = coach_data.get("session_duration", 60)
        # Ajouter les jours complets indisponibles (bloquer tous les créneaux de la journée)
        for date_str in unavailable_days:
            try:
                # Parser la date (format: "2025-12-05")
                day_date = datetime.strptime(date_str, "%Y-%m-%d")
                if from_dt.replace(tzinfo=None).date() <= day_date.date() <= to_dt.replace(tzinfo=None).date():
                    # Bloquer toute la journée (créneaux selon session_duration du coach)
                    for hour in range(10, 24):
                        slot_start = day_date.replace(hour=hour, minute=0)
                        slot_end = slot_start + timedelta(minutes=slot_mins)
                        filtered_bookings.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "title": "Indisponible",
                            "status": "unavailable"
                        })
            except Exception as e:
                log.info(f"Erreur parsing date indisponible {date_str}: {e}")
                pass
        
        # Ajouter les créneaux spécifiques indisponibles
        for slot in unavailable_slots:
            slot_date = slot.get("date", "")
            slot_time = slot.get("time", "")
            if slot_date and slot_time:
                try:
                    slot_start = datetime.fromisoformat(f"{slot_date}T{slot_time}:00")
                    slot_end = slot_start + timedelta(minutes=slot_mins)
                    if from_dt.date() <= slot_start.date() <= to_dt.date():
                        filtered_bookings.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "title": "Indisponible",
                            "status": "unavailable"
                        })
                except Exception:
                    pass
        
        return {
            "bookings": filtered_bookings,
            "working_hours": working_hours
        }
    except Exception as e:
        log.info(f"Erreur lors de la récupération des réservations: {e}")
        return {"bookings": [], "working_hours": {}}

@app.post("/api/bookings")
async def create_booking(request: Request):
    """Crée une nouvelle réservation."""
    try:
        data = await request.json()
        coach_id = data.get("coach_id")
        starts_at = data.get("starts_at")
        ends_at = data.get("ends_at")
        
        if not coach_id or not starts_at or not ends_at:
            raise HTTPException(status_code=400, detail="Données manquantes")
        
        # Charger les utilisateurs
        demo_users = load_demo_users()
        
        # Trouver le coach
        coach_email = None
        for email, user_data in demo_users.items():
            encoded_email = email.replace("@", "_").replace(".", "_")
            if user_data.get("role") == "coach" and (str(user_data.get("id")) == coach_id or user_data.get("email") == coach_id or encoded_email == coach_id):
                coach_email = email
                break
        
        if not coach_email:
            raise HTTPException(status_code=404, detail="Coach non trouvé")
        
        coach_data_check = demo_users[coach_email]
        sub_status = coach_data_check.get("subscription_status", "")
        if sub_status in ["blocked", "cancelled", "past_due"]:
            raise HTTPException(status_code=403, detail="Ce coach n'accepte pas de réservations actuellement")
        
        # Créer la réservation
        booking = {
            "id": str(uuid.uuid4()),
            "start": starts_at,
            "end": ends_at,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Ajouter aux réservations du coach
        if "bookings" not in demo_users[coach_email]:
            demo_users[coach_email]["bookings"] = []
        
        demo_users[coach_email]["bookings"].append(booking)
        
        # Sauvegarder
        save_demo_user(coach_email, demo_users[coach_email])
        
        return {"ok": True, "id": booking["id"]}
    except HTTPException:
        raise
    except Exception as e:
        log.info(f"Erreur lors de la création de la réservation: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la réservation")

# ======================================
# ENDPOINTS API COACH - GESTION DES LIEUX
# ======================================

@app.get("/api/coach/gyms")
async def get_coach_gym_locations(user = Depends(require_coach_session_or_cookie)):
    """Récupère les lieux de coaching d'un coach."""
    try:
        coach_id = str(user.get("id") or user.get("email", ""))
        gym_relations = get_coach_gyms(coach_id)
        
        return {
            "success": True,
            "gyms": gym_relations
        }
        
    except Exception as e:
        log.info(f"Erreur récupération lieux coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des lieux",
            "gyms": []
        }

@app.post("/api/coach/gyms")
async def add_coach_gym_location(
    request: Request,
    user = Depends(require_coach_session_or_cookie)
):
    """
    Ajoute un lieu de coaching pour un coach.
    Accepte 2 formats :
    1. Ancien : {"query": "nom ou adresse"} -> géocodage automatique
    2. Nouveau : {"gym_data": {...}} -> salle pré-sélectionnée avec toutes les infos
    """
    try:
        coach_id = str(user.get("id") or user.get("email", ""))
        
        # Récupérer les données JSON de la requête
        data = await request.json()
        
        gym_data = None
        
        # Format NOUVEAU : gym_data complet (salle sélectionnée depuis l'autocomplétion)
        if "gym_data" in data:
            log.info("🎯 NOUVEAU FORMAT: Salle pré-sélectionnée")
            gym_data = data["gym_data"]
            
            # Valider les champs requis
            required_fields = ["name", "address", "lat", "lng"]
            missing_fields = [field for field in required_fields if field not in gym_data]
            
            if missing_fields:
                return {
                    "success": False,
                    "message": f"Données de salle incomplètes. Champs manquants: {', '.join(missing_fields)}"
                }
        
        # Format ANCIEN : query à géocoder (pour compatibilité)
        elif "query" in data:
            log.info("🔄 ANCIEN FORMAT: Géocodage nécessaire")
            query = data["query"].strip()
            if not query:
                return {
                    "success": False,
                    "message": "Adresse ne peut pas être vide"
                }
            
            # Géocoder l'adresse
            gym_data = geocode_address(query)
            if not gym_data:
                return {
                    "success": False,
                    "message": f"Impossible de localiser '{query}'. Vérifiez l'adresse."
                }
        
        # Aucun format valide
        else:
            return {
                "success": False,
                "message": "Données requises: 'gym_data' (salle sélectionnée) OU 'query' (adresse à géocoder)"
            }
        
        log.info(f"📍 Ajout salle: {gym_data['name']} à {gym_data['address']}")
        
        # Ajouter la relation coach-salle
        success = add_coach_gym(coach_id, gym_data)
        
        if success:
            return {
                "success": True,
                "message": f"Salle '{gym_data['name']}' ajoutée avec succès !",
                "gym": gym_data
            }
        else:
            return {
                "success": False,
                "message": "Cette salle est déjà dans votre liste de lieux de coaching"
            }
            
    except Exception as e:
        log.info(f"Erreur ajout lieu coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de l'ajout du lieu"
        }

@app.delete("/api/coach/gyms/{gym_id}")
async def remove_coach_gym_location(
    gym_id: str,
    user = Depends(require_coach_session_or_cookie)
):
    """Supprime un lieu de coaching d'un coach."""
    try:
        coach_id = str(user.get("id") or user.get("email", ""))
        
        success = remove_coach_gym(coach_id, gym_id)
        
        if success:
            return {
                "success": True,
                "message": "Lieu supprimé avec succès"
            }
        else:
            return {
                "success": False,
                "message": "Lieu non trouvé ou non autorisé"
            }
            
    except Exception as e:
        log.info(f"Erreur suppression lieu coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la suppression"
        }

# ======================================
# ENDPOINTS API CLIENT - RECHERCHE SALLES
# ======================================

@app.get("/api/gyms/search")
async def search_gyms_by_location_api(
    q: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: int = 25,
    postal_code: Optional[str] = None
):
    """
    Recherche de salles par localisation, nom ou code postal.
    Paramètres: q (nom/adresse) OU lat,lng + radius_km OU postal_code
    """
    try:
        results = []
        search_lat = None
        search_lng = None
        search_google_error = None
        
        # 🆕 Recherche par code postal
        if postal_code:
            log.info(f"🔍 Recherche salles par code postal: {postal_code}")
            import json
            import os
            import re
            
            # 1. Charger les salles depuis le JSON statique
            gyms_file = os.path.join("static", "data", "gyms.json")
            if os.path.exists(gyms_file):
                with open(gyms_file, 'r', encoding='utf-8') as f:
                    all_gyms = json.load(f)
                    gyms_postal = [g for g in all_gyms if g.get("postal_code") == postal_code]
                    coach_counts = get_coaches_count_by_gym_ids([g["id"] for g in gyms_postal if g.get("id")]) if gyms_postal else {}
                    for gym in gyms_postal:
                        gym_result = gym.copy()
                        gym_result["coach_count"] = coach_counts.get(gym.get("id"), 0)
                        results.append(gym_result)
            
            # 2. AUSSI charger les salles Google Places depuis les profils des coaches
            demo_users = load_demo_users()
            google_gyms_seen = set()
            google_gyms_to_add = []
            for email, user_data in demo_users.items():
                if user_data.get("role") == "coach" and user_data.get("profile_completed"):
                    selected_gyms_data = user_data.get("selected_gyms_data", "[]")
                    try:
                        if isinstance(selected_gyms_data, str):
                            selected_gyms = json.loads(selected_gyms_data)
                        else:
                            selected_gyms = selected_gyms_data if isinstance(selected_gyms_data, list) else []
                        
                        for gym in selected_gyms:
                            if isinstance(gym, dict) and gym.get("id", "").startswith("google_worldwide_"):
                                gym_id = gym.get("id")
                                if gym_id in google_gyms_seen:
                                    continue
                                address = gym.get("address", "")
                                cp_match = re.search(r'\b(\d{5})\b', address)
                                if cp_match and cp_match.group(1) == postal_code:
                                    google_gyms_seen.add(gym_id)
                                    google_gyms_to_add.append({
                                        "id": gym_id,
                                        "name": gym.get("name", "Salle de sport"),
                                        "chain": gym.get("chain", "Google Places"),
                                        "address": address,
                                        "city": gym.get("city", ""),
                                        "postal_code": postal_code,
                                        "lat": gym.get("lat"),
                                        "lng": gym.get("lng"),
                                        "phone": gym.get("phone", "Non disponible"),
                                        "hours": gym.get("hours", "Horaires non disponibles"),
                                        "photo": "/static/gym-default.jpg",
                                    })
                    except Exception:
                        continue
            if google_gyms_to_add:
                google_gym_ids = [g["id"] for g in google_gyms_to_add]
                google_coach_counts = get_coaches_count_by_gym_ids(google_gym_ids)
                for gym_result in google_gyms_to_add:
                    gym_result["coach_count"] = google_coach_counts.get(gym_result["id"], 0)
                    results.append(gym_result)
            
            log.info(f"✅ {len(results)} salles trouvées pour le code postal {postal_code}")
            return {
                "success": True,
                "gyms": results,
                "count": len(results),
                "search_type": "postal_code"
            }
        
        elif q:
            # 1. Google Places (source principale)
            has_google_key = bool(os.environ.get("GOOGLE_PLACES_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY"))
            geocoded = geocode_address(q)
            search_lat = geocoded["lat"] if geocoded else None
            search_lng = geocoded["lng"] if geocoded else None
            
            if has_google_key:
                search_query = q.strip() if q else "salle de sport"
                google_results, google_error = search_gyms_google_places(
                    search_query,
                    lat=search_lat,
                    lng=search_lng,
                    radius_km=radius_km
                )
                if google_results:
                    # 2. Résultats > 0 → retourner immédiatement (pas de Data ES ni DB)
                    results = google_results
                else:
                    # 3. Sinon → fallback Data ES + DB
                    search_google_error = google_error
                    zone_results = search_gyms_by_zone(q)
                    results = list(zone_results)
                    seen_ids = {g.get("id") for g in results}
                    q_lower = q.lower()
                    for gym in GYMS_DATABASE:
                        if (q_lower in (gym.get("name") or "").lower() or
                            q_lower in (gym.get("address") or "").lower() or
                            q_lower in (gym.get("city") or "").lower()):
                            if gym["id"] not in seen_ids:
                                seen_ids.add(gym["id"])
                                results.append(gym.copy())
                    if search_lat and search_lng:
                        for g in search_gyms_by_location(search_lat, search_lng, radius_km):
                            if g.get("id") not in seen_ids:
                                seen_ids.add(g.get("id"))
                                results.append(g)
                    if google_error:
                        log.warning("[Google Places] query=%s fallback data_es/db (google_error=%s)", q[:80] if q else "?", google_error.get("status") or "?")
            else:
                zone_results = search_gyms_by_zone(q)
                if zone_results:
                    results = zone_results
                elif geocoded:
                    results = search_gyms_by_location(geocoded["lat"], geocoded["lng"], radius_km)
                else:
                    results = []
                    matching_gyms = [g for g in GYMS_DATABASE if q.lower() in g["name"].lower() or q.lower() in g["address"].lower()]
                    coach_counts = get_coaches_count_by_gym_ids([g["id"] for g in matching_gyms]) if matching_gyms else {}
                    for gym in matching_gyms:
                        gr = gym.copy()
                        gr["distance_km"] = None
                        gr["coach_count"] = coach_counts.get(gym["id"], 0)
                        results.append(gr)
            
            if results:
                seen_gyms = set()
                unique = []
                for gym in results:
                    key = f"{gym.get('name', '').lower()[:30]}_{gym.get('address', '')[:30].lower()}"
                    if key not in seen_gyms:
                        seen_gyms.add(key)
                        unique.append(gym)
                results = unique
                results.sort(key=lambda x: x.get("distance_km", 999))
        
        elif lat is not None and lng is not None:
            # 1. Google Places, 2. si résultats > 0 retourner, 3. sinon fallback
            google_results, google_error = search_gyms_google_places("salle de sport", lat=lat, lng=lng, radius_km=radius_km)
            if google_results:
                results = google_results
            else:
                results = search_gyms_by_location(lat, lng, radius_km)
                search_google_error = google_error
                if google_error:
                    log.warning("[Google Places] latlng(%.4f,%.4f) fallback data_es/db (google_error=%s)", lat, lng, google_error.get("status") or "?")
            if results:
                seen_gyms = set()
                unique = []
                for gym in results:
                    key = f"{gym.get('name', '').lower()[:30]}_{gym.get('address', '')[:30].lower()}"
                    if key not in seen_gyms:
                        seen_gyms.add(key)
                        unique.append(gym)
                results = unique
                results.sort(key=lambda x: x.get("distance_km", 999))
        
        else:
            return {
                "success": False,
                "message": "Paramètres requis: 'q' (recherche) OU 'lat' + 'lng'",
                "gyms": []
            }
        
        return {
            "success": True,
            "gyms": results,
            "count": len(results),
            "google_error": search_google_error
        }
        
    except Exception as e:
        log.info(f"Erreur recherche salles: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche",
            "gyms": []
        }

@app.get("/api/gyms/worldwide-search")
async def search_gyms_worldwide(q: Optional[str] = Query(None)):
    """
    🌍 Recherche MONDIALE de salles (Google Places API ou fallback local).
    Paramètres: q = nom, adresse, ville, pays...
    """
    try:
        q_clean = (q or "").strip()[:200]
        if len(q_clean) < 2:
            return {
                "success": True,
                "gyms": [],
                "message": "Tapez au moins 2 caractères (ex. Basic-Fit, Paris, Lyon)",
                "count": 0
            }
        has_key = bool(os.environ.get("GOOGLE_PLACES_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY"))
        
        def _fallback_data_es_db():
            """Fallback Data ES + GYMS_DATABASE quand Google renvoie 0 ou erreur."""
            results = []
            q_lower = q_clean.lower()
            generic_keywords = ("salle", "gym", "fitness", "sport", "room")
            if any(kw in q_lower for kw in generic_keywords):
                results = [{
                    "id": g["id"], "place_id": g["id"], "name": g["name"],
                    "address": g.get("address", ""), "formatted_address": g.get("address", ""),
                    "city": g.get("city", ""),
                } for g in GYMS_DATABASE[:25]]
            else:
                for gym in GYMS_DATABASE:
                    if (q_lower in (gym.get("name") or "").lower() or
                        q_lower in (gym.get("address") or "").lower() or
                        q_lower in (gym.get("city") or "").lower() or
                        q_lower in (gym.get("chain") or "").lower()):
                        results.append({
                            "id": gym["id"], "place_id": gym["id"], "name": gym["name"],
                            "address": gym.get("address", ""), "formatted_address": gym.get("address", ""),
                            "city": gym.get("city", ""),
                        })
            try:
                zone_results = search_gyms_by_zone(q_clean)
                seen_ids = {g["id"] for g in results}
                for gym in zone_results:
                    if gym.get("id") not in seen_ids:
                        seen_ids.add(gym["id"])
                        results.append({
                            "id": gym["id"], "place_id": gym["id"], "name": gym["name"],
                            "address": gym.get("address", ""), "formatted_address": gym.get("address", ""),
                            "city": gym.get("city", gym.get("zone", "")),
                        })
            except Exception as zone_err:
                log.warning(f"Recherche zone fallback: {zone_err}")
            return results
        
        if not has_key:
            results = _fallback_data_es_db()
            log.info(f"source=data_es/db query={q_clean!r} nb_results={len(results)} (Google non configuré)")
            return {
                "success": True,
                "gyms": results[:30],
                "count": len(results),
                "message": f"{len(results)} salle(s) trouvée(s)" if results else "Aucune salle trouvée. Essayez: Basic-Fit, Paris, Lyon",
                "source": "data_es_db",
                "google_error": None
            }

        # 1. Google Places (source principale)
        google_results, google_error = search_gyms_google_places(q_clean)
        
        if google_results:
            # 2. Résultats > 0 → retourner immédiatement
            return {
                "success": True,
                "gyms": google_results,
                "count": len(google_results),
                "message": f"{len(google_results)} salle(s) trouvée(s)",
                "source": "google",
                "google_error": None
            }
        
        # 3. Sinon → fallback Data ES + DB
        if google_error:
            log.warning("[Google Places] query=%s fallback data_es/db (google_error=%s)", q_clean[:80] if q_clean else "?", google_error.get("status") or "?")
        results = _fallback_data_es_db()
        log.info("[Google Places] query=%s fallback nb_results=%d", q_clean[:80] if q_clean else "?", len(results))
        return {
            "success": True,
            "gyms": results,
            "count": len(results),
            "message": f"{len(results)} salle(s) trouvée(s)" if results else "Aucune salle trouvée pour cette recherche",
            "source": "data_es_db",
            "google_error": google_error
        }
    except Exception as e:
        log.error(f"Erreur recherche mondiale: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche mondiale",
            "gyms": [],
            "count": 0
        }

@app.get("/api/gyms/suggestions")
async def get_gym_suggestions(q: str):
    """
    ENDPOINT COACH : Recherche TOUTES les salles de France pour l'autocomplétion coach.
    Utilise l'API Data ES (7951 salles de musculation + 4125 salles collectives).
    Paramètres: q = nom partiel de salle ou ville
    """
    try:
        log.info(f"🎯 COACH RECHERCHE: {q}")
        
        if len(q.strip()) < 2:
            return {
                "success": True,
                "suggestions": [],
                "message": "Tapez au moins 2 caractères"
            }
        
        # Utiliser notre fonction existante qui interroge l'API Data ES
        results = search_gyms_by_zone(q)
        
        # Formater pour l'autocomplétion coach
        suggestions = []
        for gym in results[:20]:  # Limiter à 20 suggestions
            suggestion = {
                "id": gym["id"],
                "name": gym["name"],
                "address": gym["address"],
                "city": gym.get("city", gym.get("zone", "Ville inconnue")),
                "lat": gym["lat"],
                "lng": gym["lng"],
                "chain": gym.get("chain", "Salle de sport"),
                "source": gym.get("source", "Data ES (officiel)"),
                "display_name": f"{gym['name']} - {gym['address']}"
            }
            suggestions.append(suggestion)
        
        # Si pas de résultats via zone, essayer par nom de salle directement dans API Data ES
        if len(suggestions) == 0:
            try:
                import requests
                api_url = "https://equipements.sports.gouv.fr/api/explore/v2.1/catalog/datasets/data-es/records"
                
                # Recherche par nom de salle
                params_name = {
                    "limit": 20,
                    "where": f'equip_nom like "%{q}%" AND (equip_type_name like "Salle de musculation" OR equip_type_name like "Salle de cours collectifs" OR equip_type_name like "Salle de culturisme" OR equip_type_name like "Salle multisports")'
                }
                
                response = requests.get(api_url, params=params_name, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    for record in data.get("results", []):
                        gym_name = record.get("equip_nom", "Salle sans nom")
                        city = record.get("new_name", "Ville inconnue")
                        address = record.get("inst_adresse", "")
                        postal_code = record.get("inst_cp", "")
                        
                        coords = record.get("equip_coordonnees", {})
                        lat = coords.get("lat", 0) if coords else 0
                        lng = coords.get("lon", 0) if coords else 0
                        
                        full_address = f"{address}, {postal_code} {city}" if address else f"{postal_code} {city}"
                        
                        suggestion = {
                            "id": f"data_es_{record.get('equip_numero', gym_name.replace(' ', '_'))}",
                            "name": gym_name,
                            "address": full_address,
                            "city": city,
                            "lat": lat,
                            "lng": lng,
                            "chain": f"Vraie salle - {record.get('equip_type_name', 'Salle de sport')}",
                            "source": "Data ES (officiel)",
                            "display_name": f"{gym_name} - {full_address}"
                        }
                        suggestions.append(suggestion)
                        
                log.info(f"🏛️ API Data ES (par nom): {len(suggestions)} suggestions trouvées")
                        
            except Exception as api_error:
                log.warning(f"Erreur API Data ES (par nom): {api_error}")
        
        # Compléter avec notre base locale si pas assez de résultats
        if len(suggestions) < 10:
            for gym in GYMS_DATABASE:
                if (q.lower() in gym["name"].lower() or 
                    q.lower() in gym["address"].lower() or
                    q.lower() in gym.get("city", "").lower()):
                    
                    # Éviter les doublons
                    if not any(s["id"] == gym["id"] for s in suggestions):
                        suggestion = {
                            "id": gym["id"],
                            "name": gym["name"],
                            "address": gym["address"],
                            "city": gym.get("city", "Ville inconnue"),
                            "lat": gym["lat"],
                            "lng": gym["lng"],
                            "chain": gym.get("chain", "Salle de sport"),
                            "source": "Base locale",
                            "display_name": f"{gym['name']} - {gym['address']}"
                        }
                        suggestions.append(suggestion)
        
        log.info(f"🎯 TOTAL SUGGESTIONS COACH: {len(suggestions)} salles trouvées")
        
        return {
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        log.info(f"Erreur suggestions coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche de suggestions",
            "suggestions": []
        }

@app.get("/api/gyms/{gym_address:path}/coaches")
async def get_gym_coaches(gym_address: str):
    """
    Récupère tous les coachs disponibles dans une salle spécifique.
    gym_address: adresse complète de la salle
    """
    try:
        # Décoder l'adresse (au cas où elle est URL-encodée)
        from urllib.parse import unquote
        gym_address = unquote(gym_address)
        
        coaches = get_coaches_by_gym(gym_address)
        
        # Ajouter des infos spécifiques à la salle si nécessaire
        enhanced_coaches = []
        for coach in coaches:
            enhanced_coach = coach.copy()
            # Ici on pourrait ajouter des infos spécifiques comme prix dans cette salle
            # Pour l'instant, on garde les infos de base
            enhanced_coaches.append(enhanced_coach)
        
        return {
            "success": True,
            "coaches": enhanced_coaches,
            "count": len(enhanced_coaches),
            "gym_address": gym_address
        }
        
    except Exception as e:
        log.info(f"Erreur récupération coachs pour salle '{gym_address}': {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des coachs",
            "coaches": []
        }

@app.get("/api/gyms/{gym_id}/coaches")  
async def get_gym_coaches_by_id(
    gym_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Récupère tous les coachs disponibles dans une salle par ID.
    🆕 NOUVEAU: Charge depuis static/data/coaches.json + tri par vérification, note, avis.
    """
    try:
        log.info(f"🔍 Recherche coaches pour gym_id: {gym_id}")
        
        # 🆕 Charger depuis le JSON statique
        coaches = get_coaches_by_gym_id(gym_id)
        
        # Normaliser le champ nom pour l'affichage (DB = full_name, JSON = name)
        for c in coaches:
            if not c.get("name"):
                c["name"] = c.get("full_name", "Coach")
        coaches_sorted = sorted(
            coaches,
            key=lambda c: (
                -int(c.get("verified", False)),
                -float(c.get("rating", 0)),
                -int(c.get("reviews_count", 0) or c.get("review_count", 0))
            )
        )
        gym_info = get_gym_by_id(gym_id) if gym_id else None
        if not gym_info:
            import json as _json
            import os as _os
            gyms_file = _os.path.join("static", "data", "gyms.json")
            if _os.path.exists(gyms_file):
                with open(gyms_file, 'r', encoding='utf-8') as f:
                    all_gyms = _json.load(f)
                    gym_info = next((g for g in all_gyms if g.get("id") == gym_id), None)
        total = len(coaches_sorted)
        coaches_page = coaches_sorted[offset:offset + limit]
        return {
            "success": True,
            "coaches": coaches_page,
            "count": len(coaches_page),
            "total": total,
            "limit": limit,
            "offset": offset,
            "gym_id": gym_id,
            "gym_info": gym_info
        }
        
    except Exception as e:
        log.error(f"Erreur récupération coachs pour gym_id '{gym_id}': {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": "Erreur lors de la récupération des coachs",
            "coaches": [],
            "gym_id": gym_id
        }

@app.get("/api/gym/{gym_id}/coaches")  
async def get_coaches_for_gym(gym_id: str, gym_name: Optional[str] = None):
    """
    🆕 Récupère tous les coaches d'une salle par ID ou par nom.
    Supporte les place_id Google Places ET les IDs locaux.
    Paramètres:
    - gym_id: ID de la salle (place_id Google ou ID local)
    - gym_name: Nom de la salle (optionnel, pour recherche par nom)
    """
    try:
        log.info(f"🔍 Recherche coaches - gym_id: {gym_id}, gym_name: {gym_name}")
        
        coaches_found = []
        demo_users = load_demo_users()
        
        # Normaliser le nom de salle pour comparaison
        search_name = gym_name.lower().strip() if gym_name else None
        
        for email, user_data in demo_users.items():
            if user_data.get("role") == "coach" and user_data.get("profile_completed"):
                selected_gyms_data = user_data.get("selected_gyms_data", "[]")
                
                try:
                    if isinstance(selected_gyms_data, str):
                        selected_gyms = json.loads(selected_gyms_data)
                    else:
                        selected_gyms = selected_gyms_data if isinstance(selected_gyms_data, list) else []
                except Exception:
                    selected_gyms = []
                
                gym_match = False
                
                for gym in selected_gyms:
                    if isinstance(gym, dict):
                        # Match par place_id Google Places
                        if gym.get("place_id") == gym_id or gym.get("id") == gym_id:
                            gym_match = True
                            break
                        
                        # Match par nom de salle (insensible à la casse)
                        if search_name:
                            gym_name_lower = gym.get("name", "").lower().strip()
                            if search_name in gym_name_lower or gym_name_lower in search_name:
                                gym_match = True
                                break
                
                if gym_match:
                    coach_obj = {
                        "id": email.replace("@", "_").replace(".", "_"),
                        "email": email,
                        "name": user_data.get("full_name", "Coach"),
                        "photo_url": user_data.get("profile_photo_url", "/static/default-avatar.jpg"),
                        "verified": user_data.get("verified", False),
                        "rating": user_data.get("rating", 5.0),
                        "review_count": user_data.get("reviews_count", 0),
                        "specialties": user_data.get("specialties", []),
                        "price": user_data.get("price_from", 40),
                        "hourly_rate": user_data.get("price_from", 40),
                        "bio": user_data.get("bio", ""),
                        "city": user_data.get("city", "")
                    }
                    coaches_found.append(coach_obj)
        
        # Trier par vérifiés, puis par note
        coaches_sorted = sorted(
            coaches_found,
            key=lambda c: (-int(c.get("verified", False)), -c.get("rating", 0))
        )
        
        log.info(f"📊 Résultat: {len(coaches_sorted)} coaches trouvés pour {gym_name or gym_id}")
        
        return {
            "success": True,
            "coaches": coaches_sorted,
            "count": len(coaches_sorted),
            "gym_id": gym_id,
            "gym_name": gym_name
        }
        
    except Exception as e:
        log.error(f"Erreur récupération coaches: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": "Erreur lors de la récupération des coaches",
            "coaches": []
        }

# ======================================
# ENDPOINTS API SALLES - BASE MONDIALE 
# ======================================

@app.get("/api/gyms/countries")
async def get_countries():
    """Retourne la liste complète des pays pour le sélecteur."""
    try:
        countries = get_countries_list()
        return {
            "success": True,
            "countries": countries,
            "count": len(countries)
        }
    except Exception as e:
        log.error(f"Erreur récupération pays: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des pays",
            "countries": []
        }

@app.get("/api/gyms/worldwide")
async def get_gyms_worldwide(
    country: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100)
):
    """
    API pour récupérer les salles de sport par pays avec pagination.
    Paramètres:
    - country: Code pays ISO 3166-1 alpha-2 (optionnel)
    - page: Numéro de page (défaut 1)
    - page_size: Taille de page (défaut 50, max 100)
    """
    try:
        if not supabase_anon:
            return {
                "success": False,
                "message": "Base de données non disponible",
                "gyms": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 0
                }
            }
        
        # Construire la requête Supabase
        query = supabase_anon.table("gyms").select("*")
        
        # Filtrer par pays si spécifié
        if country:
            query = query.eq("country_code", country.upper())
        
        # Compter le total d'abord
        count_query = supabase_anon.table("gyms").select("id", count="exact")
        if country:
            count_query = count_query.eq("country_code", country.upper())
        
        count_response = count_query.execute()
        total_gyms = count_response.count if count_response.count else 0
        
        # Calculer les paramètres de pagination
        offset = (page - 1) * page_size
        total_pages = (total_gyms + page_size - 1) // page_size
        
        # Exécuter la requête avec pagination
        response = query.range(offset, offset + page_size - 1).order("name").execute()
        
        gyms = []
        if response.data:
            for gym in response.data:
                gym_data = {
                    "id": gym["id"],
                    "name": gym["name"],
                    "country_code": gym["country_code"],
                    "country_name": get_country_name(gym["country_code"]),
                    "city": gym["city"],
                    "address": gym.get("address"),
                    "lat": float(gym["lat"]) if gym["lat"] else None,
                    "lng": float(gym["lng"]) if gym["lng"] else None,
                    "phone": gym.get("phone"),
                    "website": gym.get("website"),
                    "amenities": gym.get("amenities", []),
                    "source": gym.get("source", "manual")
                }
                gyms.append(gym_data)
        
        return {
            "success": True,
            "gyms": gyms,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_gyms,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            },
            "filters": {
                "country": country,
                "country_name": get_country_name(country) if country else None
            }
        }
        
    except Exception as e:
        log.error(f"Erreur récupération salles mondiales: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des salles",
            "gyms": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": 0,
                "total_pages": 0
            }
        }

@app.get("/api/gyms/near")
async def search_gyms_near_location(
    lat: float = Query(..., description="Latitude de recherche"),
    lng: float = Query(..., description="Longitude de recherche"),
    radius: int = Query(25, ge=1, le=100, description="Rayon de recherche en km"),
    country: Optional[str] = Query(None, description="Code pays ISO 3166-1 alpha-2 (optionnel)")
):
    """
    Recherche géographique de salles dans un rayon donné.
    Utilise la fonction Haversine de Supabase pour calculer les distances.
    """
    try:
        if not supabase_anon:
            return {
                "success": False,
                "message": "Base de données non disponible",
                "gyms": []
            }
        
        # Utiliser la fonction PostgreSQL search_gyms_near
        query = f"""
        SELECT * FROM search_gyms_near({lat}, {lng}, {radius}, {f"'{country.upper()}'" if country else 'NULL'})
        """
        
        response = supabase_anon.rpc("search_gyms_near", {
            "search_lat": lat,
            "search_lng": lng,
            "radius_km": radius,
            "search_country_code": country.upper() if country else None
        }).execute()
        
        gyms = []
        if response.data:
            for gym in response.data:
                gym_data = {
                    "id": gym["id"],
                    "name": gym["name"],
                    "country_code": gym["country_code"],
                    "country_name": get_country_name(gym["country_code"]),
                    "city": gym["city"],
                    "address": gym.get("address"),
                    "lat": float(gym["lat"]) if gym["lat"] else None,
                    "lng": float(gym["lng"]) if gym["lng"] else None,
                    "phone": gym.get("phone"),
                    "website": gym.get("website"),
                    "distance_km": float(gym["distance_km"]) if gym.get("distance_km") else None
                }
                gyms.append(gym_data)
        
        return {
            "success": True,
            "gyms": gyms,
            "count": len(gyms),
            "search_params": {
                "lat": lat,
                "lng": lng,
                "radius_km": radius,
                "country": country,
                "country_name": get_country_name(country) if country else None
            }
        }
        
    except Exception as e:
        log.error(f"[Google Maps] Erreur recherche géographique salles (lat={lat}, lng={lng}): {type(e).__name__}: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche géographique",
            "gyms": []
        }

# Route pour la page de recherche de salles Google Maps
@app.get("/gyms/finder")
async def gym_finder_page(request: Request, user = Depends(get_current_user)):
    """Page de recherche de salles avec Google Maps integration."""
    try:
        from config import get_maps_api_key
        google_maps_api_key = get_maps_api_key() or ""
    except Exception:
        google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_PLACES_API_KEY") or ""
    i18n = get_i18n_context(request)
    return templates.TemplateResponse("gym_finder.html", {
        "request": request,
        "user": user,
        "google_maps_api_key": google_maps_api_key,
        **i18n
    })

# Route pour les images uploadées (stub : en prod utiliser Supabase Storage)
@app.get("/images/{image_path:path}")
async def serve_image(image_path: str):
    """Images : en production utiliser Supabase Storage. Retourne 404 ici."""
    from fastapi.responses import Response
    return Response(status_code=404)

# ===== API ENDPOINTS POUR VÉRIFICATION EMAIL =====

class SendOTPRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str

class SignupReservationRequest(BaseModel):
    fullName: str
    email: EmailStr
    password: str

# Stockage temporaire des codes OTP (en production, utiliser Redis ou DB)
otp_storage = {}

@app.post("/api/signup-reservation")
@limiter.limit("8/minute")
async def signup_reservation(request: Request, body: SignupReservationRequest):
    """Inscription rapide depuis la page de réservation avec création de session."""
    try:
        email = body.email.lower().strip()
        full_name = body.fullName.strip()
        password = body.password
        
        log.info(f"🔐 API signup-reservation appelée pour {email} ({full_name})")
        
        # Vérifier si l'utilisateur existe déjà
        demo_users = load_demo_users()
        if email in demo_users:
            # L'utilisateur existe déjà, on met à jour le nom si différent
            existing_user = demo_users[email]
            if existing_user.get("full_name") != full_name:
                existing_user["full_name"] = full_name
                save_demo_users(demo_users)
                log.info(f"✅ Nom mis à jour pour {email}: {full_name}")
        else:
            # Créer un nouvel utilisateur client
            user_data = {
                "full_name": full_name,
                "gender": "homme",
                "role": "client",
                "password": hash_password(password),
                "coach_gender_preference": "aucune",
                "selected_gyms": []
            }
            demo_users[email] = user_data
            save_demo_users(demo_users)
            log.info(f"✅ Nouvel utilisateur créé: {email} ({full_name})")
        
        # Créer un token de session pour le client
        token = f"demo_{secrets.token_hex(8)}"
        demo_token_map[token] = email
        
        log.info(f"🔐 Session créée pour {email} avec token {token}")
        
        # Créer la réponse JSON et y ajouter le cookie
        json_response = JSONResponse({
            "success": True,
            "message": "Compte créé avec succès",
            "token": token,
            "email": email,
            "fullName": full_name
        })
        
        # Ajouter le cookie directement à la JSONResponse (même nom que /login)
        json_response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            max_age=60*60*24*30,  # 30 jours
            samesite="lax",
            path="/",
            secure=os.environ.get("REPLIT_DEPLOYMENT") == "1"
        )
        
        log.info(f"🍪 Cookie session_token défini avec token {token}")
        
        return json_response
        
    except Exception as e:
        log.error(f"Erreur inscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send-otp-email")
async def send_otp_email(request: SendOTPRequest, raw_request: Request = None):
    """Envoie un code OTP à 6 chiffres par email via Resend (utilise le même service que /signup)."""
    try:
        code = str(random.randint(100000, 999999))
        
        locale = get_locale_from_request(raw_request) if raw_request else 'en'
        email_result = send_otp_email_resend(request.email, code, None, lang=locale)
        
        if not email_result.get("success"):
            raise Exception(email_result.get("error", "Erreur envoi email"))
        
        # Stocker le code avec expiration (5 minutes)
        otp_storage[request.email] = {
            "code": code,
            "expires_at": datetime.now() + timedelta(minutes=5)
        }
        
        log.info(f"✅ Email OTP envoyé à {request.email} avec le code {code}")
        
        return JSONResponse({
            "success": True,
            "message": f"Code envoyé à {request.email}",
            "mode": email_result.get("mode", "resend")
        })
        
    except Exception as e:
        log.error(f"Erreur envoi email: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi de l'email: {str(e)}")

@app.post("/api/verify-otp")
async def verify_otp(request: VerifyOTPRequest):
    """Vérifie le code OTP saisi par l'utilisateur."""
    try:
        # Vérifier si le code existe
        if request.email not in otp_storage:
            raise HTTPException(status_code=400, detail="Aucun code actif pour cet e-mail")
        
        stored_data = otp_storage[request.email]
        
        # Vérifier l'expiration
        if datetime.now() > stored_data["expires_at"]:
            del otp_storage[request.email]
            raise HTTPException(status_code=400, detail="Le code a expiré. Renvoyez-le.")
        
        # Vérifier le code
        if stored_data["code"] != request.code:
            raise HTTPException(status_code=400, detail="Code incorrect")
        
        # Code valide - supprimer de la mémoire
        del otp_storage[request.email]
        
        return JSONResponse({
            "success": True,
            "message": "Email vérifié avec succès"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Erreur vérification OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification: {str(e)}")


# ===== CONFIRMATION DE RÉSERVATION AVEC EMAIL =====
from models.booking import ConfirmBookingRequest, CancelBookingRequest, CoachBookingRequest, DeleteBookingRequest

@app.post("/api/confirm-booking")
@limiter.limit("30/minute")
async def confirm_booking(request: Request, body: ConfirmBookingRequest):
    """Enregistre une demande de réservation selon le mode de paiement du coach.
    - Mode 'disabled': réservation en attente, coach notifié pour accepter/refuser
    - Mode 'required': paiement Stripe requis, réservation confirmée automatiquement après paiement
    """
    try:
        from resend_service import send_coach_notification_email, send_booking_confirmation_email
        import uuid
        
        date_fr = body.date
        
        log.info(f"📧 Confirmation réservation pour {body.client_name} ({body.client_email})")
        log.info(f"   Coach: {body.coach_name}, Salle: {body.gym_name}")
        log.info(f"   Date: {date_fr} à {body.time}")
        
        # Générer un ID unique pour la réservation
        booking_id = str(uuid.uuid4())[:8]
        
        # Sauvegarder la réservation en base (sous le coach correspondant)
        try:
            demo_users = load_demo_users()
            
            # Trouver le coach - priorité à l'email si fourni
            coach_email = None
            log.info(f"🔍 Recherche coach - email reçu: '{body.coach_email}', nom: '{body.coach_name}'")
            
            # 1. Match direct par email
            if body.coach_email and body.coach_email in demo_users:
                coach_email = body.coach_email
                log.info(f"✅ Coach trouvé par email direct: {coach_email}")
            
            # 2. Fallback: décoder le slug (email_avec_underscore → email@réel)
            if not coach_email and body.coach_email:
                # Essayer de décoder le slug en email
                for email in demo_users.keys():
                    encoded_email = email.replace("@", "_").replace(".", "_")
                    if encoded_email == body.coach_email:
                        if demo_users[email].get("role") == "coach":
                            coach_email = email
                            log.info(f"✅ Coach trouvé par slug décodé: {coach_email}")
                            break
            
            # 3. Fallback: recherche par nom normalisé (strip + lower)
            if not coach_email:
                normalized_coach_name = body.coach_name.strip().lower()
                for email, user_data in demo_users.items():
                    if user_data.get("role") == "coach":
                        stored_name = user_data.get("full_name", "").strip().lower()
                        if stored_name == normalized_coach_name:
                            coach_email = email
                            log.info(f"✅ Coach trouvé par nom normalisé: {coach_email}")
                            break
            
            if not coach_email:
                log.warning(f" Coach non trouvé - email: {body.coach_email}, nom: {body.coach_name}")
                return JSONResponse({
                    "success": False,
                    "message": "Coach non trouvé",
                    "error": "coach_not_found"
                }, status_code=404)
            
            # Vérifier le mode de paiement du coach
            coach_data = demo_users[coach_email]
            payment_mode = coach_data.get("payment_mode", "disabled")
            log.info(f"💳 Mode de paiement du coach: {payment_mode}")
            
            # Créer l'objet réservation
            new_booking = {
                "id": booking_id,
                "client_name": body.client_name,
                "client_email": body.client_email,
                "gym_name": body.gym_name,
                "gym_address": body.gym_address or "",
                "date": body.date,
                "time": body.time,
                "service": body.service,
                "duration": body.duration,
                "price": body.price,
                "lang": body.lang,
                "created_at": datetime.now().isoformat()
            }
            
            if payment_mode == "required":
                # MODE PAIEMENT OBLIGATOIRE
                # La réservation nécessite un paiement Stripe avant confirmation
                new_booking["status"] = "awaiting_payment"
                new_booking["payment_required"] = True
                
                # Stocker temporairement la réservation en attente de paiement
                if "pending_bookings" not in demo_users[coach_email]:
                    demo_users[coach_email]["pending_bookings"] = []
                demo_users[coach_email]["pending_bookings"].append(new_booking)
                save_demo_user(coach_email, demo_users[coach_email])
                
                log.info(f"💳 Réservation {booking_id} en attente de paiement")
                
                # Créer une session Stripe Checkout pour le paiement de la séance
                if STRIPE_AVAILABLE:
                    try:
                        from stripe_connect_facade import get_stripe_connect_info
                        from stripe_connect_service import create_session_payment_checkout
                        
                        # Vérifier que le coach a un compte Stripe Connect actif
                        connect_info = get_stripe_connect_info(coach_email)
                        
                        # Accepter les comptes Stripe partiels
                        if not connect_info:
                            log.error(f" Coach {coach_email} n'a pas de compte Stripe Connect")
                            return JSONResponse({
                                "success": False,
                                "message": "Le coach n'a pas configuré son compte bancaire pour recevoir les paiements",
                                "error": "connect_not_configured"
                            }, status_code=400)
                        
                        has_account_id = connect_info.get("account_id") is not None
                        if not has_account_id:
                            log.error(f" Coach {coach_email} n'a pas d'account_id Stripe")
                            return JSONResponse({
                                "success": False,
                                "message": "Le coach n'a pas configuré son compte bancaire pour recevoir les paiements",
                                "error": "connect_not_configured"
                            }, status_code=400)
                        
                        if not connect_info.get("charges_enabled"):
                            log.error(f" Coach {coach_email} a un compte Stripe non vérifié (charges_enabled=False)")
                            return JSONResponse({
                                "success": False,
                                "message": "Le coach n'a pas terminé la vérification de son compte Stripe. Le paiement en ligne n'est pas disponible.",
                                "error": "stripe_not_verified"
                            }, status_code=400)
                        
                        coach_connect_account_id = connect_info.get("account_id")
                        
                        # Prix en centimes
                        price_cents = int(float(body.price)) * 100
                        
                        # Construire les URLs de retour (prod: SITE_URL, sinon host de la requête)
                        base_url = os.environ.get('SITE_URL') or os.environ.get('REPLIT_DEV_DOMAIN') or str(request.base_url).rstrip("/")
                        if base_url and not base_url.startswith('http'):
                            base_url = f"https://{base_url}"
                        
                        # Créer le checkout avec transfer_data vers le coach
                        checkout_result = create_session_payment_checkout(
                            coach_account_id=coach_connect_account_id,
                            coach_email=coach_email,
                            client_email=body.client_email,
                            client_name=body.client_name,
                            amount_cents=price_cents,
                            service_name=f"Séance avec {body.coach_name} - {body.service} - {body.duration} min @ {body.gym_name}",
                            booking_id=booking_id,
                            success_url=f"{base_url}/booking-success?booking_id={booking_id}&session_id={{CHECKOUT_SESSION_ID}}",
                            cancel_url=f"{base_url}/booking-cancelled?booking_id={booking_id}",
                            lang=body.lang or "fr",
                        )
                        
                        if not checkout_result.get("success"):
                            log.error(f"Erreur création checkout: {checkout_result.get('error')}")
                            return JSONResponse({
                                "success": False,
                                "message": "Erreur lors de la création du paiement",
                                "error": checkout_result.get("error")
                            }, status_code=500)
                        
                        log.info(f"✅ Session Stripe Connect créée: {checkout_result.get('session_id')}")
                        log.info(f"   💸 L'argent ira directement au coach ({coach_connect_account_id})")
                        
                        return JSONResponse({
                            "success": True,
                            "message": "Paiement requis pour confirmer la réservation",
                            "booking_id": booking_id,
                            "status": "awaiting_payment",
                            "payment_required": True,
                            "checkout_url": checkout_result.get("checkout_url"),
                            "checkout_session_id": checkout_result.get("session_id")
                        })
                        
                    except Exception as stripe_error:
                        log.error(f"[Stripe] Erreur paiement séance (coach={coach_email}, client={client_email}): {type(stripe_error).__name__}: {stripe_error}")
                        return JSONResponse({
                            "success": False,
                            "message": "Erreur lors de la création du paiement",
                            "error": str(stripe_error)
                        }, status_code=500)
                else:
                    return JSONResponse({
                        "success": False,
                        "message": "Le paiement en ligne n'est pas disponible",
                        "error": "stripe_not_available"
                    }, status_code=503)
            
            else:
                # MODE PAIEMENT DÉSACTIVÉ (flux standard)
                # La réservation est en attente de confirmation du coach
                new_booking["status"] = "pending"
                
                if "pending_bookings" not in demo_users[coach_email]:
                    demo_users[coach_email]["pending_bookings"] = []
                demo_users[coach_email]["pending_bookings"].append(new_booking)
                save_demo_user(coach_email, demo_users[coach_email])
                
                log.info(f"✅ Réservation {booking_id} sauvegardée pour coach {coach_email}")
                
                # Envoyer notification au coach
                coach_notification = send_coach_notification_email(
                    to_email=coach_email,
                    coach_name=coach_data.get("full_name", "Coach"),
                    client_name=body.client_name,
                    client_email=body.client_email,
                    gym_name=body.gym_name,
                    gym_address=body.gym_address or "",
                    date_str=date_fr,
                    time_str=body.time,
                    service_name=body.service,
                    duration=f"{body.duration} min",
                    price=f"{body.price}€",
                    booking_id=booking_id,
                    lang=coach_data.get("lang", "fr")
                )
                log.info(f"📧 Notification coach: {coach_notification}")
                
                log.info(f"📋 Réservation en attente de confirmation du coach")
                
                return JSONResponse({
                    "success": True,
                    "message": "Demande de réservation envoyée au coach",
                    "booking_id": booking_id,
                    "coach_notified": True,
                    "client_email_sent": False,
                    "status": "pending",
                    "payment_required": False
                })
                
        except Exception as save_error:
            log.warning(f"Erreur sauvegarde réservation: {save_error}")
            return JSONResponse({
                "success": False,
                "message": "Erreur lors de la sauvegarde de la réservation",
                "error": str(save_error)
            }, status_code=500)
            
    except Exception as e:
        log.error(f"Erreur confirmation réservation: {e}")
        return JSONResponse({
            "success": False,
            "message": "Erreur lors de la réservation",
            "email_sent": False,
            "error": str(e)
        })


@app.post("/api/cancel-booking")
@limiter.limit("20/minute")
async def cancel_booking(request: Request, body: CancelBookingRequest):
    """Annule une réservation et envoie l'email d'annulation au client ET au coach."""
    try:
        from resend_service import send_cancellation_email, send_cancellation_to_coach_email
        
        log.info(f"📧 Annulation réservation pour {body.client_name} ({body.client_email})")
        log.info(f"   Coach: {body.coach_name}, Salle: {body.gym_name}")
        log.info(f"   Date: {body.date} à {body.time}")
        
        # Supprimer la réservation en base
        demo_users = load_demo_users()
        booking_removed = False
        found_coach_email = None
        found_coach_name = None
        found_coach_data = None
        
        # STRATÉGIE 1: Recherche par booking_id (méthode fiable)
        if body.booking_id:
            for coach_email, coach_data in demo_users.items():
                if coach_data.get("role") != "coach":
                    continue
                
                for list_name in ["pending_bookings", "confirmed_bookings"]:
                    bookings = coach_data.get(list_name, [])
                    new_bookings = [b for b in bookings if b.get("id") != body.booking_id]
                    if len(new_bookings) < len(bookings):
                        coach_data[list_name] = new_bookings
                        booking_removed = True
                        found_coach_email = coach_email
                        found_coach_name = coach_data.get("full_name", body.coach_name)
                        found_coach_data = coach_data
                        log.info(f"✅ Réservation {body.booking_id} supprimée de {list_name} du coach {coach_email}")
                        break
                
                if booking_removed:
                    break
        
        # STRATÉGIE 2: Fallback par coach email/nom + client email + time
        if not booking_removed:
            for coach_email, coach_data in demo_users.items():
                if coach_data.get("role") != "coach":
                    continue
                
                coach_name = coach_data.get("full_name", "").lower().strip()
                if body.coach_email and coach_email.lower() == body.coach_email.lower():
                    pass
                elif body.coach_name and coach_name == body.coach_name.lower().strip():
                    pass
                else:
                    continue
                
                found_coach_email = coach_email
                found_coach_name = coach_data.get("full_name", body.coach_name)
                found_coach_data = coach_data
                
                for list_name in ["pending_bookings", "confirmed_bookings"]:
                    bookings = coach_data.get(list_name, [])
                    new_bookings = [b for b in bookings if not (
                        b.get("client_email", "").lower() == body.client_email.lower() and
                        b.get("time") == body.time
                    )]
                    if len(new_bookings) < len(bookings):
                        coach_data[list_name] = new_bookings
                        booking_removed = True
                        log.info(f"✅ Réservation supprimée de {list_name} du coach {coach_email} (fallback)")
                
                if booking_removed:
                    break
        
        # Sauvegarder les modifications
        if booking_removed:
            save_demo_users(demo_users)
            log.info(f"✅ Base de données mise à jour")
        
        # Envoyer l'email d'annulation AU COACH
        coach_notified = False
        if found_coach_email:
            coach_result = send_cancellation_to_coach_email(
                to_email=found_coach_email,
                coach_name=found_coach_name or body.coach_name,
                client_name=body.client_name,
                client_email=body.client_email,
                gym_name=body.gym_name,
                gym_address=body.gym_address or "Adresse non renseignée",
                date_str=body.date,
                time_str=body.time,
                service_name=body.service,
                duration=body.duration,
                price=body.price,
                lang=(found_coach_data or demo_users.get(found_coach_email, {})).get("lang", "fr")
            )
            coach_notified = coach_result.get("success", False)
            if coach_notified:
                log.info(f"✅ Email d'annulation envoyé au coach {found_coach_email}")
            else:
                log.warning(f"Erreur envoi email au coach: {coach_result.get('error')}")
        
        # Envoyer l'email d'annulation AU CLIENT
        result = send_cancellation_email(
            to_email=body.client_email,
            client_name=body.client_name,
            coach_name=body.coach_name,
            gym_name=body.gym_name,
            gym_address=body.gym_address or "Adresse non renseignée",
            date_str=body.date,
            time_str=body.time,
            service_name=body.service,
            duration=body.duration,
            price=body.price,
            coach_photo=body.coach_photo,
            booking_url=body.booking_url,
            lang=body.lang
        )
        
        if result.get("success"):
            return JSONResponse({
                "success": True,
                "message": "Réservation annulée, emails envoyés",
                "email_sent": True,
                "coach_notified": coach_notified,
                "booking_removed": booking_removed,
                "email_id": result.get("email_id")
            })
        else:
            log.warning(f" Email client non envoyé mais réservation annulée: {result.get('error')}")
            return JSONResponse({
                "success": True,
                "message": "Réservation annulée (email client non envoyé)",
                "email_sent": False,
                "coach_notified": coach_notified,
                "booking_removed": booking_removed,
                "error": result.get("error")
            })
            
    except Exception as e:
        log.error(f"Erreur annulation réservation: {e}")
        return JSONResponse({
            "success": True,
            "message": "Réservation annulée (erreur email)",
            "email_sent": False,
            "error": str(e)
        })


@app.get("/reservation-cancelled", response_class=HTMLResponse)
async def reservation_cancelled(request: Request):
    """Page de confirmation d'annulation de réservation."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("reservation_cancelled.html", {"request": request, "t": translations, "locale": locale})


# ===== API COACH - GESTION DES RÉSERVATIONS =====

@app.get("/api/coach/bookings")
async def get_coach_bookings(
    user=Depends(require_coach_session_or_cookie),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Récupère les réservations du coach (pagination sur confirmed/rejected)."""
    coach_email = user.get("email")
    if not coach_email:
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=401)
    try:
        demo_users = load_demo_users()
        if coach_email not in demo_users:
            return JSONResponse({"success": False, "error": "Coach non trouvé"}, status_code=404)
        coach_data = demo_users[coach_email]
        pending_bookings = coach_data.get("pending_bookings", [])
        confirmed_bookings = coach_data.get("confirmed_bookings", [])
        rejected_bookings = coach_data.get("rejected_bookings", [])
        total_confirmed = len(confirmed_bookings)
        total_rejected = len(rejected_bookings)
        confirmed_page = confirmed_bookings[offset:offset + limit]
        rejected_page = rejected_bookings[offset:offset + limit]

        # Stats dashboard : revenus semaine, clients actifs
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=7)
        weekly_revenue = 0
        weekly_sessions = 0
        active_clients = set()
        price_default = coach_data.get("price_from") or coach_data.get("session_price") or 40
        for b in pending_bookings + confirmed_bookings:
            client_email = (b.get("client_email") or "").strip()
            if client_email:
                active_clients.add(client_email.lower())
            dt_str = b.get("date") or b.get("datetime") or b.get("confirmed_at") or ""
            if dt_str:
                try:
                    if "T" in dt_str:
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    else:
                        dt = datetime.strptime(dt_str[:10], "%Y-%m-%d")
                    if week_start <= dt < week_end:
                        weekly_sessions += 1
                        p = b.get("price") or b.get("amount") or price_default
                        weekly_revenue += int(p) if isinstance(p, (int, float)) else int(float(str(p).replace("€", "").strip() or price_default))
                except Exception:
                    pass

        return JSONResponse({
            "success": True,
            "pending": pending_bookings,
            "confirmed": confirmed_page,
            "rejected": rejected_page,
            "total_confirmed": total_confirmed,
            "total_rejected": total_rejected,
            "limit": limit,
            "offset": offset,
            "weekly_revenue": weekly_revenue,
            "weekly_sessions": weekly_sessions,
            "active_clients": len(active_clients)
        })
    except Exception as e:
        log.error(f"Erreur récupération réservations coach: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/booking/{booking_id}")
async def get_booking_by_id(booking_id: str, user=Depends(get_current_user)):
    """Récupère les détails d'un booking par son ID. Réservé au client ou au coach de la réservation."""
    if not user or not user.get("email"):
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=401)
    user_email = (user.get("email") or "").strip().lower()
    try:
        demo_users = load_demo_users()
        for coach_email, coach_data in demo_users.items():
            if coach_data.get("role") != "coach":
                continue
            for booking_list in ["pending_bookings", "confirmed_bookings", "rejected_bookings"]:
                bookings = coach_data.get(booking_list, [])
                for booking in bookings:
                    if booking.get("id") == booking_id:
                        booking_client = (booking.get("client_email") or "").strip().lower()
                        if user_email != coach_email.lower() and user_email != booking_client:
                            return JSONResponse({"success": False, "error": "Accès refusé à cette réservation"}, status_code=403)
                        booking_with_coach = booking.copy()
                        booking_with_coach["coach_email"] = coach_email
                        booking_with_coach["coach_name"] = coach_data.get("full_name", "Coach")
                        return JSONResponse({"success": True, "booking": booking_with_coach})
        return JSONResponse({"success": False, "error": "Booking non trouvé"}, status_code=404)
    except Exception as e:
        log.error(f"Erreur récupération booking: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/client/bookings", tags=["client"])
async def get_client_bookings(
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Récupère les réservations du client connecté (pagination: limit, offset)."""
    if not user or not user.get("email"):
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=401)
    client_email = user.get("email")
    try:
        demo_users = load_demo_users()
        client_bookings = []

        for coach_email, coach_data in demo_users.items():
            if coach_data.get("role") != "coach":
                continue
            coach_name = coach_data.get("full_name", "Coach")
            for booking_list in ["pending_bookings", "confirmed_bookings"]:
                bookings = coach_data.get(booking_list, [])
                for booking in bookings:
                    if (booking.get("client_email") or "").strip().lower() == client_email.strip().lower():
                        b = booking.copy()
                        b["coach_email"] = coach_email
                        b["coach_name"] = coach_name
                        client_bookings.append(b)

        total = len(client_bookings)
        page = client_bookings[offset:offset + limit]
        return JSONResponse({
            "success": True,
            "bookings": page,
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        log.error(f"Erreur récupération bookings client: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/coach/bookings/respond")
async def respond_to_booking(body: CoachBookingRequest, user=Depends(require_coach_session_or_cookie)):
    """Le coach confirme ou refuse une réservation (coach connecté uniquement)."""
    try:
        import json
        coach_email = user.get("email")
        if not coach_email:
            return JSONResponse({"success": False, "error": "Session coach invalide"}, status_code=401)
        demo_users = load_demo_users()
        if coach_email not in demo_users:
            return JSONResponse({"success": False, "error": "Coach non trouvé"}, status_code=404)
        
        coach_data = demo_users[coach_email]
        pending_bookings = coach_data.get("pending_bookings", [])
        
        # Trouver la réservation
        booking_to_update = None
        booking_index = -1
        for i, booking in enumerate(pending_bookings):
            if booking.get("id") == body.booking_id:
                booking_to_update = booking
                booking_index = i
                break
        
        if not booking_to_update:
            return JSONResponse({"success": False, "error": "Réservation non trouvée"}, status_code=404)
        
        # Retirer de pending
        pending_bookings.pop(booking_index)
        
        # Ajouter à la bonne liste selon l'action
        if body.action == "confirm":
            booking_to_update["status"] = "confirmed"
            booking_to_update["confirmed_at"] = datetime.now().isoformat()
            if "confirmed_bookings" not in coach_data:
                coach_data["confirmed_bookings"] = []
            coach_data["confirmed_bookings"].append(booking_to_update)
            action_label = "confirmée"
        elif body.action == "reject":
            booking_to_update["status"] = "rejected"
            booking_to_update["rejected_at"] = datetime.now().isoformat()
            if "rejected_bookings" not in coach_data:
                coach_data["rejected_bookings"] = []
            coach_data["rejected_bookings"].append(booking_to_update)
            action_label = "refusée"
        else:
            return JSONResponse({"success": False, "error": "Action invalide"}, status_code=400)
        
        # Mettre à jour pending_bookings
        coach_data["pending_bookings"] = pending_bookings
        
        # Sauvegarder dans la DB ET le fichier JSON
        save_demo_user(coach_email, coach_data)
        
        log.info(f"✅ Réservation {body.booking_id} {action_label} par {coach_email}")
        
        # Envoyer email au client pour l'informer
        email_sent = False
        email_error_msg = None
        
        # Vérifier que les données client sont présentes
        client_email = booking_to_update.get("client_email")
        client_name = booking_to_update.get("client_name", "Client")
        
        if not client_email:
            log.warning(f" Email client manquant pour la réservation {body.booking_id}")
            email_error_msg = "Email client non disponible"
        else:
            # Formater la date en français
            from datetime import datetime as dt
            try:
                date_obj = dt.strptime(booking_to_update.get("date", ""), "%Y-%m-%d")
                date_fr = date_obj.strftime("%A %d %B %Y").capitalize()
                jours = {"Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi", 
                         "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche"}
                mois = {"January": "janvier", "February": "février", "March": "mars", "April": "avril",
                        "May": "mai", "June": "juin", "July": "juillet", "August": "août",
                        "September": "septembre", "October": "octobre", "November": "novembre", "December": "décembre"}
                for en, fr in jours.items():
                    date_fr = date_fr.replace(en, fr)
                for en, fr in mois.items():
                    date_fr = date_fr.replace(en, fr)
            except Exception:
                date_fr = booking_to_update.get("date", "Date non spécifiée")
            
            coach_name = coach_data.get("full_name", "Coach")
            
            if body.action == "confirm":
                # Envoyer l'email de CONFIRMATION au client
                try:
                    from resend_service import send_booking_confirmation_email
                    
                    email_result = send_booking_confirmation_email(
                        to_email=client_email,
                        client_name=client_name,
                        coach_name=coach_name,
                        gym_name=booking_to_update.get("gym_name", "Salle de sport"),
                        gym_address=booking_to_update.get("gym_address", ""),
                        date_str=date_fr,
                        time_str=booking_to_update.get("time", ""),
                        service_name=booking_to_update.get("service", "Séance de coaching"),
                        duration=f"{booking_to_update.get('duration', '60')} min",
                        price=f"{booking_to_update.get('price', '40')}€",
                        coach_photo=coach_data.get("profile_photo_url"),
                        reservation_id=body.booking_id,
                        lang=booking_to_update.get("lang", "fr")
                    )
                    email_sent = email_result.get("success", False)
                    if not email_sent:
                        email_error_msg = email_result.get("error", "Erreur inconnue")
                    log.info(f"📧 Email confirmation client: {email_result}")
                    
                    # Programmer les rappels (24h avant + 2h avant)
                    schedule_booking_reminders(booking_to_update, coach_name)
                    
                except Exception as email_error:
                    email_error_msg = str(email_error)
                    log.warning(f"Erreur envoi email confirmation: {email_error}")
            
            elif body.action == "reject":
                # Envoyer l'email d'ANNULATION au client
                try:
                    from resend_service import send_rejection_email_to_client
                    
                    email_result = send_rejection_email_to_client(
                        to_email=client_email,
                        client_name=client_name,
                        coach_name=coach_name,
                        gym_name=booking_to_update.get("gym_name", "Salle de sport"),
                        gym_address=booking_to_update.get("gym_address", ""),
                        date_str=date_fr,
                        time_str=booking_to_update.get("time", ""),
                        service_name=booking_to_update.get("service", "Séance de coaching"),
                        duration=f"{booking_to_update.get('duration', '60')} min",
                        price=f"{booking_to_update.get('price', '40')}€",
                        lang=booking_to_update.get("lang", "fr")
                    )
                    email_sent = email_result.get("success", False)
                    if not email_sent:
                        email_error_msg = email_result.get("error", "Erreur inconnue")
                    log.info(f"📧 Email rejet client: {email_result}")
                except Exception as email_error:
                    email_error_msg = str(email_error)
                    log.warning(f"Erreur envoi email rejet: {email_error}")
        
        response_data = {
            "success": True,
            "message": f"Réservation {action_label}",
            "booking": serialize_for_json(booking_to_update),
            "email_sent": email_sent
        }
        if email_error_msg:
            response_data["email_error"] = email_error_msg
        
        return JSONResponse(response_data)
        
    except Exception as e:
        log.error(f"Erreur réponse réservation: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/coach/bookings/delete")
async def delete_booking(body: DeleteBookingRequest, user=Depends(require_coach_session_or_cookie)):
    """Le coach supprime une réservation (coach connecté uniquement)."""
    try:
        import json
        coach_email = user.get("email")
        if not coach_email:
            return JSONResponse({"success": False, "error": "Session coach invalide"}, status_code=401)
        demo_users = load_demo_users()
        if coach_email not in demo_users:
            return JSONResponse({"success": False, "error": "Coach non trouvé"}, status_code=404)
        
        coach_data = demo_users[coach_email]
        booking_found = False
        deleted_booking = None
        was_confirmed = False
        
        # Chercher dans pending_bookings
        pending_bookings = coach_data.get("pending_bookings", [])
        for i, booking in enumerate(pending_bookings):
            if booking.get("id") == body.booking_id:
                deleted_booking = pending_bookings.pop(i)
                coach_data["pending_bookings"] = pending_bookings
                booking_found = True
                was_confirmed = False
                break
        
        # Chercher dans confirmed_bookings si pas trouvé
        if not booking_found:
            confirmed_bookings = coach_data.get("confirmed_bookings", [])
            for i, booking in enumerate(confirmed_bookings):
                if booking.get("id") == body.booking_id:
                    deleted_booking = confirmed_bookings.pop(i)
                    coach_data["confirmed_bookings"] = confirmed_bookings
                    booking_found = True
                    was_confirmed = True
                    break
        
        if not booking_found:
            return JSONResponse({"success": False, "error": "Réservation non trouvée"}, status_code=404)
        
        # Sauvegarder via la fonction centralisée (DB ou JSON)
        save_demo_user(coach_email, coach_data)
        
        log.info(f"🗑️ Réservation {body.booking_id} supprimée par {coach_email}")
        
        # Annuler les rappels programmés pour cette réservation
        cancel_booking_reminders(body.booking_id)
        
        # Envoyer un email au client pour l'informer de l'annulation
        email_sent = False
        if deleted_booking:
            client_email = deleted_booking.get("client_email")
            client_name = deleted_booking.get("client_name", "Client")
            coach_name = coach_data.get("full_name", "Votre coach")
            gym_name = deleted_booking.get("gym_name", "")
            date_str = deleted_booking.get("date", "")
            time_str = deleted_booking.get("time", "")
            
            if client_email:
                try:
                    from resend_service import send_coach_cancelled_email
                    
                    # Formater la date
                    formatted_date = date_str
                    if date_str:
                        try:
                            from datetime import datetime
                            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                            jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                            mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                            formatted_date = f"{jours[date_obj.weekday()]} {date_obj.day} {mois[date_obj.month - 1]}"
                        except Exception:
                            pass
                    
                    log.info(f"📧 Envoi email annulation au client {client_name} ({client_email})")
                    log.info(f"   Coach: {coach_name}, Date: {formatted_date} à {time_str}")
                    
                    email_result = send_coach_cancelled_email(
                        client_email=client_email,
                        client_name=client_name,
                        coach_name=coach_name,
                        gym_name=gym_name,
                        date=f"{formatted_date} à {time_str}",
                        lang=deleted_booking.get("lang", "fr")
                    )
                    email_sent = email_result.get("success", False)
                    log.info(f"📧 Email annulation client: {email_result}")
                except Exception as email_error:
                    log.warning(f"Erreur envoi email annulation: {email_error}")
        
        return JSONResponse({
            "success": True,
            "message": "Séance supprimée",
            "email_sent": email_sent
        })
        
    except Exception as e:
        log.error(f"Erreur suppression réservation: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ============================================
# MESSAGERIE CLIENT-COACH
# ============================================

MESSAGES_FILE = "messages.json"

def load_messages():
    """Charge les messages depuis le fichier JSON."""
    if os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_messages(messages):
    """Sauvegarde les messages dans le fichier JSON."""
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

def get_conversation_id(client_email: str, coach_email: str, booking_id: str) -> str:
    """Génère un ID unique pour une conversation."""
    return f"{client_email}_{coach_email}_{booking_id}"

class SendMessageRequest(BaseModel):
    booking_id: str
    client_email: EmailStr
    coach_email: EmailStr
    sender_role: str  # "client" ou "coach"
    sender_name: str
    message: str

@app.post("/api/messages/send")
async def send_message(body: SendMessageRequest, user=Depends(get_current_user)):
    """Envoie un message dans une conversation. L'expéditeur doit être le client ou le coach de la réservation."""
    if not user or not user.get("email"):
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=401)
    user_email = (user.get("email") or "").strip().lower()
    if body.sender_role == "client":
        if (body.client_email or "").strip().lower() != user_email:
            return JSONResponse({"success": False, "error": "Accès refusé"}, status_code=403)
    elif body.sender_role == "coach":
        if (body.coach_email or "").strip().lower() != user_email:
            return JSONResponse({"success": False, "error": "Accès refusé"}, status_code=403)
    else:
        return JSONResponse({"success": False, "error": "Rôle invalide"}, status_code=400)
    try:
        messages = load_messages()
        conv_id = get_conversation_id(body.client_email, body.coach_email, body.booking_id)
        if conv_id not in messages:
            messages[conv_id] = {
                "booking_id": body.booking_id,
                "client_email": body.client_email,
                "coach_email": body.coach_email,
                "messages": []
            }
        new_message = {
            "id": str(uuid.uuid4())[:8],
            "sender_role": body.sender_role,
            "sender_name": body.sender_name,
            "message": body.message,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        messages[conv_id]["messages"].append(new_message)
        save_messages(messages)
        return JSONResponse({"success": True, "message": new_message})
    except Exception as e:
        log.error(f"Erreur envoi message: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/messages/{booking_id}")
async def get_messages(booking_id: str, user=Depends(get_current_user), client_email: str = None, coach_email: str = None):
    """Récupère les messages d'une conversation. Réservé au client ou au coach de la réservation."""
    if not user or not user.get("email"):
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=401)
    user_email = (user.get("email") or "").strip().lower()
    try:
        messages = load_messages()
        for conv_id, conv in messages.items():
            if conv.get("booking_id") != booking_id:
                continue
            c_client = (conv.get("client_email") or "").strip().lower()
            c_coach = (conv.get("coach_email") or "").strip().lower()
            if user_email != c_client and user_email != c_coach:
                return JSONResponse({"success": False, "error": "Accès refusé à cette conversation"}, status_code=403)
            return JSONResponse({"success": True, "conversation": conv})
        return JSONResponse({"success": True, "conversation": {"messages": []}})
    except Exception as e:
        log.error(f"Erreur récupération messages: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/conversations")
async def get_conversations(user=Depends(get_current_user), role: str = Query(None)):
    """Récupère toutes les conversations de l'utilisateur connecté (client ou coach)."""
    if not user or not user.get("email"):
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=401)
    email = (user.get("email") or "").strip().lower()
    try:
        messages = load_messages()
        user_conversations = []
        for conv_id, conv in messages.items():
            c_client = (conv.get("client_email") or "").strip().lower()
            c_coach = (conv.get("coach_email") or "").strip().lower()
            if email == c_client or email == c_coach:
                if role and role.lower() == "client" and email != c_client:
                    continue
                if role and role.lower() == "coach" and email != c_coach:
                    continue
                user_conversations.append(conv)
        return JSONResponse({"success": True, "conversations": user_conversations})
    except Exception as e:
        log.error(f"Erreur récupération conversations: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/messages/mark-read")
async def mark_messages_read(booking_id: str, reader_role: str, user=Depends(get_current_user)):
    """Marque les messages d'une conversation comme lus. Réservé au client ou au coach de la réservation."""
    if not user or not user.get("email"):
        return JSONResponse({"success": False, "error": "Non autorisé"}, status_code=401)
    user_email = (user.get("email") or "").strip().lower()
    try:
        messages = load_messages()
        for conv_id, conv in messages.items():
            if conv.get("booking_id") != booking_id:
                continue
            c_client = (conv.get("client_email") or "").strip().lower()
            c_coach = (conv.get("coach_email") or "").strip().lower()
            if user_email != c_client and user_email != c_coach:
                return JSONResponse({"success": False, "error": "Accès refusé"}, status_code=403)
            for msg in conv.get("messages", []):
                if msg.get("sender_role") != reader_role:
                    msg["read"] = True
            save_messages(messages)
            return JSONResponse({"success": True})
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/conversation/{booking_id}", response_class=HTMLResponse)
async def conversation_page(request: Request, booking_id: str, user = Depends(require_auth)):
    """Page de conversation pour client ou coach."""
    i18n_context = get_i18n_context(request)
    return templates.TemplateResponse("conversation.html", {
        "request": request,
        "booking_id": booking_id,
        **i18n_context
    })


# ============================================
# SYSTÈME DE RAPPELS - ENDPOINTS & BACKGROUND TASK
# ============================================

def _run_reminders_process(request: Request, secret: Optional[str] = None):
    """Logique commune pour traiter les rappels (utilisée par /api/reminders/process et /api/reminders_process)."""
    cron_secret = os.environ.get("CRON_SECRET")
    if cron_secret:
        provided = secret or request.headers.get("X-Cron-Secret") if request else None
        if provided != cron_secret:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
    try:
        sent_count = process_due_reminders()
        return JSONResponse({
            "success": True,
            "reminders_sent": sent_count,
            "message": f"{sent_count} rappel(s) envoyé(s)"
        })
    except Exception as e:
        log.error(f"Erreur API process reminders: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/reminders/process")
async def api_process_reminders(request: Request, secret: Optional[str] = Query(None)):
    """
    Traitement des rappels (24h/2h). À appeler par un cron toutes les 5-15 min.
    Si CRON_SECRET est défini en env, passer le secret en query ?secret=... ou en header X-Cron-Secret.
    """
    return _run_reminders_process(request, secret)


@app.get("/api/reminders_process")
async def api_reminders_process_vercel(request: Request, secret: Optional[str] = Query(None)):
    """
    Alias pour le cron Vercel (sans slash). Même logique que /api/reminders/process.
    """
    return _run_reminders_process(request, secret)

@app.get("/api/reminders/pending")
async def api_get_pending_reminders():
    """Récupère la liste des rappels en attente."""
    try:
        reminders_data = load_scheduled_reminders()
        pending = [r for r in reminders_data.get("reminders", []) if not r.get("sent")]
        return JSONResponse({
            "success": True,
            "pending_count": len(pending),
            "reminders": pending
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# Background task pour vérifier les rappels périodiquement
import threading
import time

def check_and_block_unpaid_coaches():
    """Vérifie les coaches avec paiement échoué depuis 24h+ et les bloque."""
    try:
        demo_users = load_demo_users()
        blocked_count = 0
        now = datetime.now()
        
        for email, user_data in demo_users.items():
            if user_data.get("role") != "coach":
                continue
            
            # Vérifier si le coach a un paiement échoué depuis 24h+
            payment_failed_at = user_data.get("payment_failed_at")
            subscription_status = user_data.get("subscription_status")
            
            if payment_failed_at and subscription_status == "past_due":
                failed_date = datetime.fromisoformat(payment_failed_at)
                hours_since_failure = (now - failed_date).total_seconds() / 3600
                
                if hours_since_failure >= 24:
                    # Bloquer le compte
                    user_data["subscription_status"] = "blocked"
                    user_data["blocked_at"] = now.isoformat()
                    save_demo_user(email, user_data)
                    blocked_count += 1
                    
                    # Envoyer email de blocage
                    from resend_service import send_account_blocked_email
                    base_url = os.environ.get("SITE_URL") or os.environ.get("REPLIT_DEV_DOMAIN", "")
                    if base_url and not base_url.startswith("http"):
                        base_url = f"https://{base_url}"
                    send_account_blocked_email(
                        to_email=email,
                        coach_name=user_data.get("full_name", "Coach"),
                        retry_url=f"{base_url}/coach/subscription" if base_url else "/coach/subscription",
                        lang=user_data.get("lang", "fr")
                    )
                    log.info(f"🚫 Compte bloqué pour non-paiement: {email}")
        
        return blocked_count
    except Exception as e:
        log.warning(f"Erreur vérification blocage: {e}")
        return 0

def reminder_checker_thread():
    """Thread qui vérifie les rappels et blocages toutes les 5 minutes."""
    log.info("🔔 Démarrage du thread de vérification des rappels...")
    while True:
        try:
            # Vérifier les rappels
            sent = process_due_reminders()
            if sent > 0:
                log.info(f"🔔 {sent} rappel(s) envoyé(s) automatiquement")
            
            # Vérifier les coaches à bloquer (paiement échoué depuis 24h+)
            blocked = check_and_block_unpaid_coaches()
            if blocked > 0:
                log.info(f"🚫 {blocked} compte(s) bloqué(s) pour non-paiement")
                
        except Exception as e:
            log.warning(f"Erreur thread rappels: {e}")
        
        # Attendre 5 minutes avant la prochaine vérification
        time.sleep(300)

# Démarrer le thread de vérification au lancement de l'application
reminder_thread = threading.Thread(target=reminder_checker_thread, daemon=True)
reminder_thread.start()

# ============================================

# ============================================
# STRIPE - ABONNEMENTS COACHS (API Endpoints)
# ============================================

async def get_coach_for_checkout(request: Request):
    """Utilisateur coach : session cookie OU token signup en header (fallback si cookie perdu)."""
    user = get_current_user(request.cookies.get("session_token"))
    if user and user.get("role") == "coach":
        return user
    token = (request.headers.get("X-Signup-Token") or "").strip()
    if token:
        email = _validate_signup_token(token)
        if email:
            from utils import get_demo_user
            u = get_demo_user(email)
            if u and u.get("role") == "coach":
                u["email"] = email
                return u
            if u is None:
                u = {"email": email, "role": "coach", "full_name": "Coach", "id": email}
                return u
    raise HTTPException(status_code=401, detail="Authentification requise. Rechargez la page /coach/offre et réessayez.")

# Routes Stripe (extrait dans routes/payment_routes.py)
from routes.payment_routes import register_payment_routes
register_payment_routes(app, {
    "get_coach_for_checkout": get_coach_for_checkout,
    "_get_base_url": _get_base_url,
    "_is_stripe_configured": _is_stripe_configured,
    "_get_stripe_not_configured_response": _get_stripe_not_configured_response,
    "create_or_get_customer": create_or_get_customer,
    "create_checkout_session": create_checkout_session,
    "update_coach_subscription": update_coach_subscription,
    "log": log,
})

@app.post("/api/stripe/create-portal-session")
async def api_create_portal_session(request: Request, user = Depends(require_coach_session_or_cookie)):
    """Crée une session du portail de facturation Stripe."""
    if not _is_stripe_configured():
        log.warning("Route Stripe appelée mais Stripe non configuré")
        return _get_stripe_not_configured_response()
    try:
        coach_email = user.get("email")
        subscription_info = get_coach_subscription_info(coach_email)
        
        if not subscription_info or not subscription_info.get("stripe_customer_id"):
            return JSONResponse({"error": "Aucun abonnement trouvé"}, status_code=404)
        
        base_url = _get_base_url(request)
        return_url = f"{base_url.rstrip('/')}/coach/subscription"
        
        session = create_portal_session(
            customer_id=subscription_info["stripe_customer_id"],
            return_url=return_url
        )
        
        return JSONResponse({"url": session.url})
    except Exception as e:
        log.error(f"[Stripe] Erreur création portal session (contexte: coach={user.get('email')}): {type(e).__name__}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/stripe/success", tags=["stripe"])
async def stripe_success(request: Request, session_id: Optional[str] = Query(None)):
    """
    Page publique après paiement Stripe Checkout.
    Vérifie payment_status puis redirige vers /verify-email?email=...&payment=success.
    """
    if not session_id:
        return RedirectResponse(url="/pricing?payment=failed", status_code=302)
    try:
        import stripe
        from stripe_service import init_stripe
        init_stripe()
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != "paid":
            return RedirectResponse(url="/pricing?payment=failed", status_code=302)
        details = getattr(session, "customer_details", None) or session.get("customer_details")
        meta = getattr(session, "metadata", None) or session.get("metadata") or {}
        email_from_details = details.get("email") if isinstance(details, dict) else (getattr(details, "email", None) if details else None)
        customer_email = email_from_details or meta.get("coach_email") or meta.get("email")
        if customer_email:
            from urllib.parse import quote
            redirect_url = f"/verify-email?email={quote(customer_email)}&payment=success"
            return RedirectResponse(url=redirect_url, status_code=302)
        return RedirectResponse(url="/coach-login?payment=success", status_code=302)
    except Exception as e:
        log.warning(f"[Stripe] Erreur stripe_success: {e}")
        return RedirectResponse(url="/pricing?payment=failed", status_code=302)


async def activate_coach_subscription(customer_email: str, session: dict):
    """Active l'abonnement coach après paiement Stripe (création DB, emails)."""
    import stripe
    from stripe_service import init_stripe
    init_stripe()
    subscription_id = session.get("subscription")
    customer_id = session.get("customer")
    coach_data = get_demo_user(customer_email)
    if not coach_data:
        demo_users = load_demo_users()
        demo_users[customer_email] = {
            "email": customer_email,
            "full_name": (session.get("customer_details") or {}).get("name", "Coach"),
            "role": "coach",
            "subscription_status": "inactive",
            "stripe_customer_id": customer_id or "",
            "stripe_subscription_id": subscription_id or "",
        }
        save_demo_users(demo_users)
        log.info(f"✅ Nouveau coach créé en DB: {customer_email}")
    if subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            period_end = datetime.fromtimestamp(subscription.current_period_end).isoformat()
            update_coach_subscription(
                coach_email=customer_email,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                subscription_status="active",
                current_period_end=period_end
            )
        except Exception as e:
            log.warning(f"Erreur récupération subscription: {e}")
    else:
        update_coach_subscription(
            coach_email=customer_email,
            stripe_customer_id=customer_id,
            subscription_status="active"
        )
    coach_data = get_demo_user(customer_email)
    base_url = (os.environ.get("SITE_URL") or os.environ.get("REPLIT_DEV_DOMAIN", "")).strip()
    if base_url and not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    try:
        from resend_service import send_subscription_success_email, send_subscription_payment_receipt
        subscription_type = session.get("metadata", {}).get("subscription_type", "monthly")
        send_subscription_success_email(
            to_email=customer_email,
            coach_name=coach_data.get("full_name", "Coach") if coach_data else "Coach",
            subscription_url=f"{base_url}/coach/portal" if base_url else "/coach/portal",
            lang=coach_data.get("lang", "fr") if coach_data else "fr"
        )
        amount_paid = 10.0 if subscription_type == "annual" else 1.0
        if subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                inv = stripe.Invoice.retrieve(sub.latest_invoice)
                amount_paid = inv.amount_paid / 100
            except Exception:
                pass
        from datetime import timedelta
        today = datetime.now()
        end_date = today + timedelta(days=365 if subscription_type == "annual" else 30)
        send_subscription_payment_receipt(
            to_email=customer_email,
            coach_name=coach_data.get("full_name", "Coach") if coach_data else "Coach",
            amount=f"{amount_paid:.2f}€",
            billing_period=subscription_type,
            subscription_start=today.strftime("%d/%m/%Y"),
            subscription_end=end_date.strftime("%d/%m/%Y"),
            lang=coach_data.get("lang", "fr") if coach_data else "fr"
        )
        # Envoi du code OTP pour vérification email (obligatoire avant accès portail)
        from email_verification_service import send_email_verification_code
        ok, err = send_email_verification_code(customer_email)
        if not ok:
            log.warning(f"Erreur envoi code OTP à {customer_email}: {err}")
    except Exception as e:
        log.warning(f"Erreur envoi email bienvenue: {e}")


async def stripe_webhook_handler(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        import stripe
        from stripe_service import init_stripe
        init_stripe()
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            os.getenv("STRIPE_WEBHOOK_SECRET")
        )

        # Gestion checkout.session.completed
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]

            customer_email = (
                session.get("customer_details", {}).get("email")
                or session.get("metadata", {}).get("coach_email")
                or session.get("metadata", {}).get("email")
            )

            if customer_email:
                await activate_coach_subscription(customer_email, session)

        return JSONResponse({"status": "success"})

    except Exception as e:
        log.error(f"Webhook error: {e}")
        return JSONResponse({"status": "error"}, status_code=400)


# IMPORTANT : enregistrer explicitement les routes POST
app.add_api_route(
    "/stripe/webhook",
    stripe_webhook_handler,
    methods=["POST"]
)

app.add_api_route(
    "/api/stripe/webhook",
    stripe_webhook_handler,
    methods=["POST"]
)

@app.get("/api/coach/subscription-status")
async def api_coach_subscription_status(request: Request, user = Depends(require_coach_session_or_cookie)):
    """Récupère le statut d'abonnement du coach connecté."""
    try:
        coach_email = user.get("email")
        subscription_info = get_coach_subscription_info(coach_email)
        is_subscribed = is_coach_subscribed(coach_email)
        
        return JSONResponse({
            "success": True,
            "is_subscribed": is_subscribed,
            "subscription_info": subscription_info
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

# ============================================
# PAGES PAIEMENT SÉANCE
# ============================================

@app.get("/booking-success", response_class=HTMLResponse)
async def booking_success_page(request: Request, booking_id: str = None, session_id: str = None):
    """Page de confirmation après paiement réussi d'une séance."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    
    # Confirmer la réservation en attente de paiement
    if booking_id:
        try:
            from resend_service import send_booking_confirmation_email
            demo_users = load_demo_users()
            
            # Chercher la réservation en attente
            for coach_email, coach_data in demo_users.items():
                if coach_data.get("role") != "coach":
                    continue
                
                pending = coach_data.get("pending_bookings", [])
                for booking in pending:
                    if booking.get("id") == booking_id:
                        # Déplacer de pending à confirmed_bookings
                        booking["status"] = "confirmed"
                        booking["payment_status"] = "paid"
                        booking["stripe_session_id"] = session_id
                        booking["confirmed_at"] = datetime.now().isoformat()
                        
                        # Mettre à jour les listes
                        coach_data["pending_bookings"] = [b for b in pending if b.get("id") != booking_id]
                        if "confirmed_bookings" not in coach_data:
                            coach_data["confirmed_bookings"] = []
                        coach_data["confirmed_bookings"].append(booking)
                        
                        # Sauvegarder
                        save_demo_user(coach_email, coach_data)
                        log.info(f"✅ Réservation {booking_id} confirmée après paiement Stripe")
                        
                        # Envoyer email de confirmation + reçu de paiement au client
                        try:
                            from datetime import datetime as dt
                            date_obj = dt.strptime(booking.get("date", ""), "%Y-%m-%d") if booking.get("date") else dt.now()
                            jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
                            mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                            date_fr = f"{jours[date_obj.weekday()]} {date_obj.day} {mois[date_obj.month - 1]} {date_obj.year}"
                            dur = f"{booking.get('duration', 60)} min"
                            pr = f"{booking.get('price', '')}€"
                            send_booking_confirmation_email(
                                to_email=booking.get("client_email"),
                                client_name=booking.get("client_name"),
                                coach_name=coach_data.get("full_name", "Coach"),
                                gym_name=booking.get("gym_name"),
                                gym_address=booking.get("gym_address", ""),
                                date_str=date_fr,
                                time_str=booking.get("time", ""),
                                service_name=booking.get("service", "Séance"),
                                duration=dur,
                                price=pr,
                                coach_photo=coach_data.get("profile_photo_url"),
                                reservation_id=booking_id,
                                lang=booking.get("lang", "fr")
                            )
                            log.info(f"📧 Email de confirmation envoyé à {booking.get('client_email')}")
                            from resend_service import send_session_payment_receipt
                            send_session_payment_receipt(
                                to_email=booking.get("client_email"),
                                client_name=booking.get("client_name"),
                                coach_name=coach_data.get("full_name", "Coach"),
                                gym_name=booking.get("gym_name"),
                                gym_address=booking.get("gym_address", ""),
                                session_date=date_fr,
                                session_time=booking.get("time", ""),
                                service_name=booking.get("service", "Séance"),
                                duration=dur,
                                amount=pr,
                                lang=booking.get("lang", "fr")
                            )
                            log.info(f"📧 Reçu de paiement envoyé à {booking.get('client_email')}")
                        except Exception as email_err:
                            log.warning(f"Erreur email: {email_err}")
                        break
        except Exception as e:
            log.warning(f"Erreur confirmation réservation: {e}")
    
    return templates.TemplateResponse("booking_success.html", {
        "request": request,
        "booking_id": booking_id,
        "session_id": session_id,
        "lang": locale,
        "t": translations
    })

@app.get("/booking-cancelled", response_class=HTMLResponse)
async def booking_cancelled_page(request: Request, booking_id: str = None):
    """Page affichée si le paiement est annulé."""
    lang = get_locale_from_request(request)
    t = get_translations(lang)
    return templates.TemplateResponse("booking_cancelled.html", {
        "request": request,
        "booking_id": booking_id,
        "lang": lang,
        "t": t
    })

# ============================================
# 404 globale : toute URL non gérée (GET) renvoie la page 404.html avec i18n
# Doit être en dernier pour ne pas capturer les routes existantes
# ============================================

@app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
async def catch_all_404(request: Request, full_path: str):
    """Route catch-all : page 404 HTML pour les URLs inconnues (hors API)."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    i18n = get_i18n_context(request)
    return templates.TemplateResponse(
        "404.html",
        {"request": request, "message": None, **i18n},
        status_code=404,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)