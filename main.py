from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, Cookie, Query, Response
import secrets
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List, Dict
from pydantic import BaseModel
import uvicorn
import jwt
import os
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
    search_gyms_worldwide_autocomplete,
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
        init_stripe
    )
    STRIPE_AVAILABLE = True
except Exception as stripe_import_error:
    print(f"⚠️ Stripe non disponible: {stripe_import_error}")
    STRIPE_AVAILABLE = False

# ============================================
# SYSTÈME DE RAPPELS PROGRAMMÉS
# ============================================

def load_scheduled_reminders() -> dict:
    """Charge les rappels programmés depuis le fichier JSON."""
    try:
        if os.path.exists("scheduled_reminders.json"):
            with open("scheduled_reminders.json", "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Erreur chargement rappels: {e}")
    return {"reminders": []}

def save_scheduled_reminders(data: dict):
    """Sauvegarde les rappels programmés dans le fichier JSON."""
    try:
        with open("scheduled_reminders.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Erreur sauvegarde rappels: {e}")

def schedule_booking_reminders(booking: dict, coach_name: str):
    """
    Programme les rappels pour une réservation confirmée.
    Crée 2 rappels: 24h avant et 2h avant le RDV.
    """
    try:
        booking_date = booking.get("date")
        booking_time = booking.get("time")
        
        if not booking_date or not booking_time:
            print(f"⚠️ Date/heure manquante pour programmer les rappels")
            return
        
        # Parser la date et l'heure du RDV
        booking_datetime = datetime.strptime(f"{booking_date} {booking_time}", "%Y-%m-%d %H:%M")
        
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
                "sent": False,
                "created_at": now.isoformat()
            })
            print(f"📅 Rappel 24h programmé pour {reminder_24h.strftime('%d/%m/%Y %H:%M')}")
        else:
            print(f"⏭️ RDV dans moins de 24h, pas de rappel J-1")
        
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
                "sent": False,
                "created_at": now.isoformat()
            })
            print(f"⏰ Rappel 2h programmé pour {reminder_2h.strftime('%d/%m/%Y %H:%M')}")
        else:
            print(f"⏭️ RDV dans moins de 2h, pas de rappel 2h")
        
        # Sauvegarder
        save_scheduled_reminders(reminders_data)
        print(f"✅ Rappels programmés pour la réservation {booking.get('id')}")
        
    except Exception as e:
        print(f"❌ Erreur programmation rappels: {e}")

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
            print(f"🗑️ {removed_count} rappel(s) annulé(s) pour la réservation {booking_id}")
        
    except Exception as e:
        print(f"❌ Erreur annulation rappels: {e}")

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
            
            send_at = datetime.fromisoformat(reminder.get("send_at"))
            
            if send_at <= now:
                # C'est l'heure d'envoyer ce rappel
                print(f"📧 Envoi du rappel {reminder.get('type')} pour {reminder.get('client_email')}")
                
                # Formater la date en français
                try:
                    date_obj = datetime.strptime(reminder.get("date"), "%Y-%m-%d")
                    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
                    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                    date_fr = f"{jours[date_obj.weekday()].capitalize()} {date_obj.day} {mois[date_obj.month - 1]} {date_obj.year}"
                except:
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
                    booking_id=reminder.get("booking_id")
                )
                
                if result.get("success"):
                    reminder["sent"] = True
                    reminder["sent_at"] = now.isoformat()
                    sent_count += 1
                    print(f"✅ Rappel {reminder.get('type')} envoyé à {reminder.get('client_email')}")
                else:
                    print(f"❌ Échec envoi rappel: {result.get('error')}")
        
        # Sauvegarder les mises à jour
        save_scheduled_reminders(reminders_data)
        
        # Nettoyer les rappels envoyés vieux de plus de 7 jours
        cleanup_old_reminders()
        
        return sent_count
        
    except Exception as e:
        print(f"❌ Erreur traitement rappels: {e}")
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
            print(f"🧹 {removed} ancien(s) rappel(s) nettoyé(s)")
            
    except Exception as e:
        print(f"⚠️ Erreur nettoyage rappels: {e}")

# ============================================

app = FastAPI()

# Précharger les traductions au démarrage
preload_all_translations()

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
                except:
                    continue
    
    return None

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
    
    # 3. Charger les VRAIS coachs depuis la base de données demo
    real_coaches = []
    demo_users = load_demo_users()
    
    for email, user_data in demo_users.items():
        # Vérifier si c'est un coach avec profil complété
        if user_data.get("role") == "coach" and user_data.get("profile_completed"):
            # selected_gyms_data est stocké en STRING JSON, il faut le parser
            selected_gyms_data = user_data.get("selected_gyms_data", "[]")
            
            # Parser le JSON string
            try:
                if isinstance(selected_gyms_data, str):
                    selected_gyms = json.loads(selected_gyms_data)
                else:
                    selected_gyms = selected_gyms_data if isinstance(selected_gyms_data, list) else []
            except:
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
    
    # 4. Combiner les deux listes
    all_coaches = json_coaches + real_coaches
    return all_coaches

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
        print(f"Erreur upload Supabase Storage: {e}")
        return None

# Exception handler pour rediriger automatiquement les utilisateurs non connectés
@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """Redirige automatiquement vers /login si utilisateur non connecté."""
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=303)
    return exc

# Configuration des templates et fichiers statiques
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/attached_assets", StaticFiles(directory="attached_assets"), name="attached_assets")

# Client Supabase anonyme (si disponible)
supabase_anon = get_supabase_anon_client()

# Cache en mémoire pour les codes OTP en mode démo (email -> code)
demo_otp_cache = {}
demo_user_cache = {}
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
    # Validation des prérequis
    if not session_token:
        return None
    
    # Validation du format du token
    if not isinstance(session_token, str) or len(session_token.strip()) < 10:
        print("❌ Token de session invalide (format)")
        return None
    
    # Mode démo si pas de Supabase
    if not supabase_anon:
        if session_token.startswith("demo_"):
            # Extraire l'email depuis le token unique
            from utils import load_demo_users, get_demo_user
            import hashlib
            
            print(f"🔍 Mode démo - Recherche utilisateur pour token: {session_token}")
            
            # D'abord vérifier le cache demo_token_map (pour les tokens créés via /api/signup-reservation)
            if session_token in demo_token_map:
                email = demo_token_map[session_token]
                print(f"✅ Token trouvé dans demo_token_map pour {email}")
                fresh_user_data = get_demo_user(email)
                if fresh_user_data:
                    fresh_user_data["_access_token"] = session_token
                    fresh_user_data["email"] = email
                    print(f"✅ Données récupérées: {email}, full_name: {fresh_user_data.get('full_name', 'N/A')}")
                    return fresh_user_data
            
            # D'abord essayer de récupérer depuis le stockage persistant
            # Charger tous les utilisateurs démo des DEUX sources (fichier + persistant)
            all_demo_users = load_demo_users()
            
            # Trouver l'utilisateur correspondant à ce token
            for email, user_data in all_demo_users.items():
                expected_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
                if session_token == expected_token:
                    print(f"✅ Token trouvé pour {email} - Récupération données persistantes...")
                    
                    # Récupérer les données les plus récentes depuis le stockage persistant
                    fresh_user_data = get_demo_user(email)
                    if fresh_user_data:
                        print(f"✅ Données fraîches récupérées: profile_completed={fresh_user_data.get('profile_completed', False)}")
                        fresh_user_data["_access_token"] = session_token
                        # IMPORTANT: Toujours inclure l'email dans les données retournées
                        fresh_user_data["email"] = email
                        print(f"✅ Email ajouté aux données: {email}, full_name: {fresh_user_data.get('full_name', 'N/A')}")
                        return fresh_user_data
                    else:
                        print(f"⚠️  Pas de données persistantes pour {email}, utilisation données fichier")
                        # Fallback sur les données du fichier
                        user_data["_access_token"] = session_token
                        user_data["email"] = email  # IMPORTANT: Inclure l'email
                        return user_data
            
            # Token démo non reconnu
            print(f"❌ Token démo non reconnu: {session_token}")
            return None
        elif session_token == "demo_token":
            # Support pour l'ancien token (rétrocompatibilité)
            from utils import get_demo_user
            demo_user = get_demo_user("demo@example.com")
            
            if demo_user:
                demo_user["_access_token"] = session_token
                return demo_user
            else:
                return {
                    "id": "demo_user", 
                    "email": "demo@example.com", 
                    "role": "coach",
                    "full_name": "Utilisateur Démo",
                    "profile_completed": False,
                    "_access_token": session_token
                }
        return None
    
    try:
        import os
        
        # Décoder le JWT pour récupérer l'ID utilisateur (plus robuste que auth.get_user)
        # On ne vérifie pas la signature car Supabase l'a déjà fait
        decoded_token = jwt.decode(session_token, options={"verify_signature": False})
        user_id = decoded_token.get("sub")
        
        if not user_id:
            print("❌ Token JWT invalide (pas d'ID utilisateur)")
            return None
            
        # Créer un client authentifié pour respecter les politiques RLS
        user_supabase = get_supabase_client_for_user(session_token)
        if not user_supabase:
            print("❌ Impossible de créer le client authentifié")
            return None
            
        # Charger le profil directement depuis la table profiles
        profile = get_user_profile(user_supabase, user_id)
        if profile:
            profile["_access_token"] = session_token  # Garder le token pour les futures requêtes
            print(f"✅ Utilisateur authentifié: {profile.get('email', 'N/A')}")
            return profile
        else:
            # Profil non trouvé - créer automatiquement lors de la première connexion
            print(f"⚠️ Profil manquant pour utilisateur {user_id}, création automatique")
            
            # Récupérer l'email depuis le token JWT
            user_email = decoded_token.get("email")
            if not user_email:
                print("❌ Email non trouvé dans le token")
                return None
                
            # Créer un objet utilisateur mock pour la création de profil
            mock_user = type('User', (), {
                'id': user_id,
                'email': user_email,
                'user_metadata': {}
            })()
            
            return create_profile_on_first_login(user_supabase, mock_user, session_token)
            
    except jwt.DecodeError:
        print("❌ Token JWT mal formé")
        return None
    except Exception as e:
        print(f"❌ Erreur authentification: {e}")
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
            print(f"✅ Profil créé automatiquement lors de la première connexion pour {user.email}")
            return profile
        
        return None
    except Exception as e:
        print(f"❌ Erreur création profil automatique: {e}")
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

def require_active_subscription(user = Depends(require_coach_role)):
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

# Route favicon
@app.get("/favicon.ico")
async def favicon():
    """Retourne le favicon du site."""
    from fastapi.responses import FileResponse
    return FileResponse("static/favicon.ico", media_type="image/x-icon")

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
    
    # Rediriger vers la page précédente ou l'accueil
    referer = request.headers.get("referer", "/")
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie(key=LOCALE_COOKIE_NAME, value=locale, max_age=31536000)
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
        locale = get_locale_from_request(request)
        translations = get_translations(locale)
        return templates.TemplateResponse("results.html", {
            "request": request,
            "coaches": coaches,
            "specialty": None,
            "city": "",
            "gym": gym,
            "radius_km": radius_km
        })
    
    # Géocoder la ville
    coords = geocode_city(city) if city else None
    user_lat, user_lng = coords if coords else (None, None)
    
    # Rechercher les coachs - VRAIS coaches depuis la base de données
    from utils import load_demo_users
    demo_users = load_demo_users()
    coaches = []
    
    for email, user_data in demo_users.items():
        if user_data.get("role") == "coach" and user_data.get("profile_completed"):
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
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("results.html", {
        "request": request,
        "coaches": coaches,
        "specialty": specialty,
        "city": city,
        "gym": None,
        "radius_km": radius_km
    })

# Cette route sera déplacée après les routes spécifiques coach/portal, coach/specialties, etc.

# Routes d'authentification
@app.get("/client/home", response_class=HTMLResponse)
async def client_home(request: Request, user = Depends(get_current_user)):
    """Page d'accueil pour les clients avec formulaire de recherche."""
    # Si pas d'utilisateur connecté, rediriger vers la page de connexion
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    response = templates.TemplateResponse("client_home.html", {
        "request": request, 
        "user": user
    })
    # Désactiver le cache pour éviter les problèmes de session
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/mon-compte", response_class=HTMLResponse)
async def mon_compte(request: Request, user = Depends(get_current_user)):
    """Page compte client accessible via session ou localStorage."""
    response = templates.TemplateResponse("client_home.html", {
        "request": request, 
        "user": user  # Utiliser la session si disponible
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
    """Page de recherche de salles avec Google Maps."""
    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("gyms_map.html", {
        "request": request,
        "address": address,
        "radius_km": radius_km,
        "google_maps_api_key": google_maps_api_key
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
        if user_data.get("role") == "coach" and user_data.get("profile_completed"):
            selected_gyms_data = user_data.get("selected_gyms_data", "[]")
            
            try:
                if isinstance(selected_gyms_data, str):
                    selected_gyms = json.loads(selected_gyms_data)
                else:
                    selected_gyms = selected_gyms_data if isinstance(selected_gyms_data, list) else []
            except:
                selected_gyms = []
            
            gym_match = False
            
            for gym in selected_gyms:
                if isinstance(gym, dict):
                    # Match par place_id Google Places ou ID local
                    if gym.get("place_id") == gym_id or gym.get("id") == gym_id:
                        gym_match = True
                        break
                    
                    # Match par nom de salle
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
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("partner.html", {"request": request, "t": translations, "locale": locale})

@app.get("/coach-signup", response_class=HTMLResponse)
async def coach_signup_page(request: Request):
    """Page d'inscription coach avec hero section."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_signup.html", {"request": request, "t": translations, "locale": locale})

@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request, role: str | None = None):
    """Formulaire d'inscription."""
    countries = get_countries_list()
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("signup.html", {
        "request": request, 
        "t": translations,
        "locale": locale,
        "role": role,
        "countries": countries
    })

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
async def get_gyms():
    """API pour récupérer la liste des salles de sport disponibles - MISE À JOUR avec vraies salles."""
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
            print(f"⚠️ Erreur récupération échantillon Data ES: {api_error}")
        
        # Si pas assez de salles via API, compléter avec notre base locale
        if len(sample_gyms) < 20:
            sample_gyms.extend(GYMS_DATABASE[:30])  # Ajouter jusqu'à 30 salles locales
        
        print(f"🏋️ API /gyms: {len(sample_gyms)} salles retournées ({len([g for g in sample_gyms if 'Data ES' in g.get('source', '')])} officielles)")
        
        return {"gyms": sample_gyms[:50]}  # Limiter la réponse à 50 salles max
        
    except Exception as e:
        print(f"❌ Erreur /api/gyms: {e}")
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
            # Mode démo - chercher dans le stockage persistant
            user_data = get_demo_user(email)
            if user_data:
                selected_gyms_str = user_data.get("selected_gyms", "[]")
                try:
                    selected_gyms = json.loads(selected_gyms_str) if selected_gyms_str else []
                    return {"success": True, "selected_gyms": selected_gyms}
                except:
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
                    except:
                        return {"success": True, "selected_gyms": []}
                else:
                    return {"success": True, "selected_gyms": []}
            else:
                return {"success": True, "selected_gyms": []}
                
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des salles utilisateur: {e}")
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
            # Mode démo - sauvegarder dans le stockage persistant
            user_data = get_demo_user(email)
            if user_data:
                user_data["selected_gyms"] = json.dumps(validated_gyms)
                save_demo_user(email, user_data)
                print(f"✅ Salles sauvegardées en mode démo pour {email}: {validated_gyms}")
                return {"success": True, "message": "Salles sauvegardées avec succès"}
            else:
                return {"success": False, "message": "Utilisateur non trouvé"}
        else:
            # Mode Supabase - sauvegarder dans la base de données
            response = supabase_anon.table("profiles").update({
                "selected_gyms": json.dumps(validated_gyms)
            }).eq("id", user_id).execute()
            
            if response.data:
                print(f"✅ Salles sauvegardées en Supabase pour l'utilisateur {user_id}: {validated_gyms}")
                return {"success": True, "message": "Salles sauvegardées avec succès"}
            else:
                return {"success": False, "message": "Erreur lors de la sauvegarde"}
                
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde des salles: {e}")
        return {"success": False, "message": "Erreur serveur"}

@app.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    gender: str = Form(...),
    role: str = Form(...),
    country: str = Form(...),
    coach_gender_preference: str = Form("aucune"),
    selected_gyms: str = Form("")
):
    """Inscription utilisateur avec système OTP par email."""
    # Normaliser l'email en lowercase
    email = email.lower().strip()
    
    # Récupérer la liste des pays une seule fois pour tous les cas d'erreur
    countries = get_countries_list()
    
    # Validation du mot de passe
    if not is_valid_password(password):
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Mot de passe trop faible (minimum 8 caractères, 1 lettre et 1 chiffre)",
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference
        }, status_code=400)
    
    # Validation du genre
    if gender not in ["homme", "femme"]:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Veuillez sélectionner votre genre",
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference
        }, status_code=400)
    
    # Validation du pays
    valid_countries = [c["code"] for c in countries]
    if not country or country not in valid_countries:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Veuillez sélectionner votre pays",
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference
        }, status_code=400)
    
    # Validation du rôle
    if role not in ["client", "coach"]:
        role = "client"
    
    # Générer le code OTP (6 chiffres par défaut)
    otp_code = generate_otp_code(6)
    
    if not supabase_anon:
        # Mode démo sans Supabase - stocker le code et les infos utilisateur dans le cache
        demo_otp_cache[email] = otp_code
        # Traiter et valider les salles sélectionnées pour les clients
        selected_gyms_list = []
        if role == "client":
            selected_gyms_list = validate_selected_gyms(selected_gyms)
            if selected_gyms and not selected_gyms_list:
                # L'utilisateur a fourni des données invalides
                print(f"⚠️ Salles invalides reçues pour {email}: {selected_gyms}")
                return templates.TemplateResponse("signup.html", {
                    "request": request,
                    "error": "Salles sélectionnées invalides. Veuillez réessayer.",
                    "full_name": full_name,
                    "email": email,
                    "gender": gender,
                    "role": role,
                    "coach_gender_preference": coach_gender_preference
                }, status_code=400)
        
        # Sauvegarder l'utilisateur dans le stockage persistant
        user_data = {
            "full_name": full_name,
            "gender": gender,
            "role": role,
            "country_code": country,
            "password": password.strip(),  # Normaliser le mot de passe stocké
            "coach_gender_preference": coach_gender_preference if role == "client" else None,
            "selected_gyms": selected_gyms_list if role == "client" else None
        }
        save_demo_user(email, user_data)
        
        # Garder aussi en cache mémoire pour compatibilité temporaire
        demo_user_cache[email] = user_data
        print(f"🔐 Mode démo - Code OTP généré pour {email}: {otp_code}")
        
        # Tester l'envoi d'email avec Resend même en mode démo
        email_result = send_otp_email_resend(email, otp_code, full_name)
        
        success_message = "Code de vérification envoyé à votre adresse email"
        if email_result.get("success"):
            if email_result.get("mode") == "resend":
                success_message += f" (Email ID: {email_result.get('email_id', 'N/A')})"
        
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "success": success_message
        })
    
    try:
        # NOUVEAU: Utiliser le service email natif Supabase au lieu de l'OTP manuel
        
        # Valider et traiter les salles sélectionnées avant inscription
        validated_gyms = None
        if role == "client":
            validated_gyms_list = validate_selected_gyms(selected_gyms)
            if selected_gyms and not validated_gyms_list:
                print(f"⚠️ Salles invalides reçues pour {email}: {selected_gyms}")
                return templates.TemplateResponse("signup.html", {
                    "request": request,
                    "error": "Salles sélectionnées invalides. Veuillez réessayer.",
                    "full_name": full_name,
                    "email": email,
                    "gender": gender,
                    "role": role,
                    "coach_gender_preference": coach_gender_preference
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
            # Succès - rediriger vers la page d'attente de confirmation email
            return templates.TemplateResponse("email_confirmation_sent.html", {
                "request": request,
                "email": email,
                "success": signup_result.get("message", "Email de confirmation envoyé")
            })
        else:
            # Échec inscription - afficher erreur détaillée
            error_message = signup_result.get("error", "Erreur lors de l'inscription")
            if "already registered" in error_message.lower() or "already exists" in error_message.lower():
                error_message = "Cette adresse email est déjà utilisée. Essayez de vous connecter ou utilisez une autre adresse."
            
            print(f"💥 Détails erreur inscription Supabase: {error_message}")
            
            return templates.TemplateResponse("signup.html", {
                "request": request,
                "error": error_message,
                "full_name": full_name,
                "email": email,
                "gender": gender,
                "role": role,
                "country_code": country,
                "countries": countries,
                "coach_gender_preference": coach_gender_preference
            }, status_code=400)
            
    except Exception as e:
        print(f"❌ Erreur inscription OTP: {e}")
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": "Erreur lors de l'inscription. Veuillez réessayer.",
            "full_name": full_name,
            "email": email,
            "gender": gender,
            "role": role,
            "country_code": country,
            "countries": countries,
            "coach_gender_preference": coach_gender_preference
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
        print(f"❌ Erreur renvoi confirmation: {e}")
        return {"success": False, "error": str(e)}

@app.get("/auth/email-confirmed")
async def email_confirmed_callback(request: Request):
    """Page affichée après confirmation d'email via Supabase."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("email_confirmed.html", {
        "request": request,
        "success": "Email confirmé avec succès ! Vous pouvez maintenant vous connecter."
    })

@app.post("/verify-otp")
async def verify_otp_submit(
    request: Request,
    email: str = Form(...),
    otp_code: str = Form(...)
):
    """Vérification du code OTP et activation du compte (legacy pour le mode démo)."""
    # Normaliser l'email et le code
    email = email.lower().strip()
    otp_code = otp_code.strip()
    
    # Validation du format du code
    if not otp_code.isdigit() or len(otp_code) < 4 or len(otp_code) > 6:
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": "Code invalide. Veuillez saisir un code à 4-6 chiffres."
        }, status_code=400)
    
    if not supabase_anon:
        # Mode démo - vérifier que le code correspond exactement à celui généré
        stored_code = demo_otp_cache.get(email)
        if stored_code and otp_code == stored_code:
            # Code correct - supprimer du cache et connecter
            # Récupérer les informations utilisateur depuis le stockage persistant
            user_info = get_demo_user(email) or demo_user_cache.get(email, {})
            role = user_info.get('role', 'client')
            del demo_otp_cache[email]
            
            # Rediriger selon le rôle
            if role == 'coach':
                redirect_url = "/coach/portal"
            else:
                redirect_url = "/client/home"
                
            response = RedirectResponse(url=redirect_url, status_code=303)
            # Créer un token unique pour cet utilisateur en mode démo
            import hashlib
            unique_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
            response.set_cookie(
                key="session_token",
                value=unique_token,
                httponly=True,
                secure=False,  # True en production
                samesite="lax"
            )
            return response
        else:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Code incorrect. Veuillez utiliser le code affiché en mode démo."
            }, status_code=400)
    
    try:
        # Vérifier le code OTP
        otp_valid = verify_otp_code(supabase_anon, email, otp_code)
        
        if not otp_valid:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Code incorrect ou expiré. Veuillez réessayer."
            }, status_code=400)
        
        # Code valide - récupérer les données complètes d'inscription
        pending_data = get_pending_otp_data(supabase_anon, email)
        
        if not pending_data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Données d'inscription introuvables. Veuillez recommencer l'inscription."
            }, status_code=400)
        
        # Récupérer l'user_id depuis otp_codes
        response = supabase_anon.table("otp_codes").select("user_id").eq("email", email).eq("consumed", True).order("created_at", desc=True).limit(1).execute()
        
        if not response.data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Utilisateur introuvable. Veuillez recommencer l'inscription."
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
        # Pour le mode démo, on va simplement rediriger
        
        # Rediriger selon le rôle
        if role == 'coach':
            redirect_url = "/coach/portal"
        else:
            redirect_url = "/client/home"
        
        response = RedirectResponse(url=redirect_url, status_code=303)
        
        # Cookie de session démo (en production, utiliser un vrai token Supabase)
        response.set_cookie(
            key="session_token",
            value=f"verified_{user_id}",
            httponly=True,
            secure=False,  # True en production avec HTTPS
            samesite="lax",
            max_age=3600 * 24 * 7  # 7 jours
        )
        
        return response
        
    except Exception as e:
            print(f"❌ Erreur récupération utilisateur: {e}")
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Erreur lors de la vérification du compte."
            }, status_code=500)
            
    except Exception as e:
        print(f"❌ Erreur vérification OTP: {e}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": "Erreur lors de la vérification. Veuillez réessayer."
        }, status_code=500)

@app.post("/resend-otp")
async def resend_otp_submit(
    request: Request,
    email: str = Form(...)
):
    """Renvoie un nouveau code OTP."""
    # Normaliser l'email
    email = email.lower().strip()
    
    if not supabase_anon:
        # Mode sans Supabase - générer un nouveau code, le stocker et l'envoyer par email
        new_otp_code = generate_otp_code(6)
        demo_otp_cache[email] = new_otp_code
        print(f"🔐 Nouveau code OTP pour {email}: {new_otp_code}")
        
        # Récupérer le nom de l'utilisateur si disponible
        user_data = get_demo_user(email)
        full_name = user_data.get("full_name") if user_data else None
        
        # Envoyer le code par email
        email_result = send_otp_email_resend(email, new_otp_code, full_name)
        
        if email_result.get("success"):
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "success": "Nouveau code envoyé à votre adresse email"
            })
        else:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Erreur lors de l'envoi du code. Réessayez."
            })
    
    try:
        # Récupérer les données d'inscription en attente
        pending_data = get_pending_otp_data(supabase_anon, email)
        
        if not pending_data:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Aucune demande d'inscription trouvée pour cet email."
            }, status_code=400)
        
        full_name = pending_data['full_name']
        role = pending_data['role']
        
        # Générer un nouveau code OTP
        new_otp_code = generate_otp_code(6)
        
        # Sauvegarder le nouveau code (l'ancien sera automatiquement supprimé)
        otp_stored = store_otp_code(supabase_anon, email, full_name, role, new_otp_code)
        
        if not otp_stored:
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": "Erreur lors de la génération du nouveau code."
            }, status_code=500)
        
        # Envoyer le nouveau code par email avec Resend
        email_result = send_otp_email_resend(email, new_otp_code, full_name)
        
        if email_result.get("success"):
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "success": "Nouveau code envoyé par email"
            })
        else:
            # Message d'erreur détaillé basé sur le type d'erreur
            error_details = email_result.get("error", "Erreur inconnue")
            if email_result.get("mode") == "resend":
                error_message = f"Erreur d'envoi d'email (Status {email_result.get('status_code', 'N/A')}). Vérifiez votre adresse email et réessayez."
            else:
                error_message = "Erreur de service d'email. Veuillez réessayer dans quelques minutes."
            
            print(f"💥 Détails erreur renvoi email: {error_details}")
            
            return templates.TemplateResponse("verify_otp.html", {
                "request": request,
                "email": email,
                "error": error_message
            }, status_code=500)
            
    except Exception as e:
        print(f"❌ Erreur renvoi OTP: {e}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "error": "Erreur lors du renvoi du code."
        }, status_code=500)

# API Login pour le JavaScript (accepte JSON)
@app.post("/api/login")
async def api_login(request: Request):
    """API de connexion pour JavaScript (JSON)."""
    try:
        data = await request.json()
        email = data.get("email", "").lower().strip()
        password = data.get("password", "")
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email et mot de passe requis")
        
        # Mode démo - vérifier identifiants
        demo_users_hardcoded = {
            "coach@demo.com": {"password": "demopass123", "role": "coach", "full_name": "Coach Demo"},
            "client@demo.com": {"password": "demopass123", "role": "client", "full_name": "Client Demo"}
        }
        
        user_found = None
        
        # Vérifier les comptes démo hardcodés
        demo_user = demo_users_hardcoded.get(email)
        if demo_user and demo_user["password"] == password:
            user_found = demo_user
            print(f"✅ API Login: compte démo hardcodé")
        
        # Si pas trouvé, vérifier les utilisateurs inscrits
        if not user_found:
            cached_user = get_demo_user(email)
            if cached_user:
                stored_password = cached_user.get("password", "").strip()
                if stored_password and stored_password == password.strip():
                    user_found = cached_user
                    print(f"✅ API Login: compte inscrit trouvé")
        
        if user_found:
            return {
                "success": True,
                "full_name": user_found.get("full_name", email.split("@")[0]),
                "email": email,
                "role": user_found.get("role", "client")
            }
        else:
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur API login: {e}")
        raise HTTPException(status_code=500, detail="Erreur serveur")

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, message: Optional[str] = None, password_changed: Optional[str] = None):
    """Formulaire de connexion."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "message": message,
        "password_changed": password_changed
    })

@app.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """Traitement de la connexion."""
    # Normaliser l'email en lowercase
    email = email.lower().strip()
    
    if not supabase_anon:
        # Mode démo sans Supabase - vérifier identifiants démo avec rôles
        demo_users = {
            "coach@demo.com": {"password": "demopass123", "role": "coach"},
            "client@demo.com": {"password": "demopass123", "role": "client"}
        }
        
        user_found = None
        
        # D'abord vérifier les comptes démo hardcodés
        demo_user = demo_users.get(email)
        if demo_user and demo_user["password"] == password:
            user_found = demo_user
            print(f"✅ Connexion avec compte démo hardcodé")
        
        # Si pas trouvé, vérifier les utilisateurs inscrits dans le stockage persistant
        if not user_found:
            cached_user = get_demo_user(email)
            if cached_user:
                # Normaliser les mots de passe pour la comparaison
                stored_password = cached_user.get("password", "").strip()
                submitted_password = password.strip()
                if stored_password and stored_password == submitted_password:
                    user_found = cached_user
                    print(f"✅ Connexion avec compte inscrit (stockage persistant)")
        
        if user_found:
            # Redirection selon le rôle en mode démo
            role = user_found["role"]
            if role == "coach":
                redirect_url = "/coach/portal"
            elif role == "client":
                redirect_url = "/client/home"
            else:
                redirect_url = "/coach/portal"
            
            print(f"✅ Connexion démo réussie - Redirection vers {redirect_url} (rôle: {role})")
            
            response = RedirectResponse(url=redirect_url, status_code=303)
            # Créer un token unique pour cet utilisateur en mode démo
            import hashlib
            unique_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
            response.set_cookie(
                key="session_token",
                value=unique_token,
                httponly=True,
                secure=False,  # True en production
                samesite="lax"
            )
            return response
        else:
            # Identifiants incorrects même en mode démo
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email ou mot de passe incorrect.",
                "email": email
            }, status_code=401)
    
    # Mode Supabase - utiliser le nouveau service avec vérification d'email confirmé
    result = sign_in_with_email_password(email, password)
    
    if result.get("success"):
        # Connexion réussie - récupérer le profil pour rediriger vers le bon portail
        user_id = result["user"].id
        profile_result = get_user_role(user_id)
        
        # Déterminer l'URL de redirection selon le rôle
        if profile_result.get("success"):
            user_role = profile_result.get("role")
            if user_role == "coach":
                redirect_url = "/coach/portal"
            elif user_role == "client":
                redirect_url = "/client/home"
            else:
                # Fallback en cas de rôle non reconnu
                redirect_url = "/coach/portal"
        else:
            # Fallback si impossible de récupérer le profil
            redirect_url = "/coach/portal"
        
        print(f"✅ Redirection vers {redirect_url} pour utilisateur rôle: {profile_result.get('role', 'inconnu')}")
        
        response = RedirectResponse(url=redirect_url, status_code=303)
        # Cookie HttpOnly sécurisé
        response.set_cookie(
            key="session_token",
            value=result["session"].access_token,
            httponly=True,
            secure=False,  # True en production avec HTTPS
            samesite="lax",
            max_age=3600 * 24 * 7  # 7 jours
        )
        return response
    else:
        # Gérer les différents types d'erreurs
        error_message = result.get("error", "Erreur de connexion")
        
        if result.get("mode") == "email_not_confirmed":
            # Email non confirmé - proposer de renvoyer l'email
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email non confirmé. Vérifiez votre boîte mail ou renvoyez l'email de confirmation.",
                "email": email,
                "show_resend": True
            }, status_code=401)
        elif result.get("mode") == "invalid_credentials":
            # Identifiants incorrects
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Email ou mot de passe incorrect.",
                "email": email
            }, status_code=401)
        else:
            # Autre erreur
            print(f"💥 Erreur connexion: {error_message}")
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Erreur de connexion. Veuillez réessayer.",
                "email": email
            }, status_code=401)

@app.post("/auth/resend-confirmation")
async def resend_confirmation(
    request: Request,
    email: str = Form(...)
):
    """Renvoie l'email de confirmation."""
    # Normaliser l'email en lowercase
    email = email.lower().strip()
    
    if not supabase_anon:
        # Mode démo - pas de renvoi d'email
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "error": "Mode démo - renvoi d'email non disponible"
        })
    
    success = resend_confirmation_email(supabase_anon, email)
    if success:
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "success": "Email de confirmation renvoyé ! Vérifiez votre boîte mail."
        })
    else:
        return templates.TemplateResponse("verify_email.html", {
            "request": request,
            "email": email,
            "error": "Erreur lors du renvoi de l'email. Veuillez réessayer."
        })

@app.get("/logout")
async def logout():
    """Déconnexion."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    return response

# === PASSWORD RESET ===
import secrets
from datetime import datetime, timedelta

password_reset_tokens = {}

@app.post("/api/forgot-password")
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
        
        token = secrets.token_urlsafe(32)
        expiry = datetime.now() + timedelta(hours=1)
        password_reset_tokens[token] = {
            "email": email,
            "expiry": expiry
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
              <p style="margin:0 0 16px;font-size:16px;color:#333;">Bonjour,</p>
              <p style="margin:0 0 24px;font-size:16px;color:#333;line-height:1.5;">
                Cliquez sur ce lien pour réinitialiser votre mot de passe FitMatch pour le compte <a href="mailto:{email}" style="color:#008f57;text-decoration:none;">{email}</a>.
              </p>
              <p style="margin:0 0 24px;">
                <a href="{reset_link}" style="display:inline-block;background:#008f57;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:16px;">Réinitialiser mon mot de passe</a>
              </p>
              <p style="margin:0 0 8px;font-size:14px;color:#666;">Ou copiez ce lien dans votre navigateur :</p>
              <p style="margin:0 0 24px;font-size:13px;color:#008f57;word-break:break-all;">
                <a href="{reset_link}" style="color:#008f57;">{reset_link}</a>
              </p>
              <p style="margin:0 0 16px;font-size:14px;color:#999;line-height:1.5;">
                Si vous n'avez pas demandé à réinitialiser votre mot de passe, vous pouvez ignorer cet e-mail.
              </p>
              <p style="margin:24px 0 0;font-size:14px;color:#333;">Merci,</p>
              <p style="margin:4px 0 0;font-size:14px;color:#333;font-weight:600;">Votre équipe FitMatch</p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px;background:#f9f9f9;text-align:center;">
              <p style="margin:0;font-size:12px;color:#999;">© 2024 FitMatch. Tous droits réservés.</p>
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
                    "subject": "Réinitialisez votre mot de passe pour FitMatch",
                    "html": html_content
                })
                print(f"✅ Email de réinitialisation envoyé à {email}")
            except Exception as e:
                print(f"❌ Erreur envoi email: {e}")
        else:
            print(f"⚠️ Resend non configuré ou SENDER_EMAIL manquant")
        
        return {"success": True}
        
    except Exception as e:
        print(f"❌ Erreur forgot-password: {e}")
        return {"success": True}

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    """Page de réinitialisation du mot de passe."""
    error = None
    
    if not token:
        error = "Lien invalide ou expiré."
    elif token not in password_reset_tokens:
        error = "Lien invalide ou expiré."
    else:
        token_data = password_reset_tokens[token]
        if datetime.now() > token_data["expiry"]:
            del password_reset_tokens[token]
            error = "Ce lien a expiré. Veuillez demander un nouveau lien."
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "token": token,
        "error": error
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
        
        user["password"] = new_password
        save_demo_user(email, user)
        
        del password_reset_tokens[token]
        
        session_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
        role = user.get("role", "client")
        
        print(f"✅ Mot de passe réinitialisé pour {email}")
        
        response = JSONResponse({
            "success": True, 
            "email": email,
            "role": role
        })
        
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=False,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        print(f"❌ Erreur reset-password: {e}")
        return JSONResponse({"success": False, "error": "Une erreur est survenue."})

# Espace Coach - Page de connexion/inscription dédiée aux coaches
@app.get("/coach-login", response_class=HTMLResponse)
async def coach_login_page(request: Request, tab: Optional[str] = None):
    """Page de connexion/inscription pour les coaches."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_login.html", {
        "request": request,
        "tab": tab
    })

@app.post("/coach-login")
async def coach_login_submit(
    request: Request,
    action: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    name: Optional[str] = Form(None)
):
    """Traitement de la connexion/inscription coach."""
    email = email.lower().strip()
    
    if action == "signup":
        # Inscription coach
        if not name or len(name.strip()) < 2:
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Le nom est requis (minimum 2 caractères).",
                "tab": "signup"
            }, status_code=400)
        
        if len(password) < 8:
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Le mot de passe doit contenir au moins 8 caractères.",
                "tab": "signup"
            }, status_code=400)
        
        # Vérifier si l'email existe déjà
        existing_user = get_demo_user(email)
        if existing_user:
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Un compte existe déjà avec cet email.",
                "tab": "signup"
            }, status_code=400)
        
        # Créer le compte coach avec statut "en attente de paiement"
        new_coach = {
            "email": email,
            "password": password,
            "full_name": name.strip(),
            "role": "coach",
            "verified": True,
            "profile_completed": False,
            "subscription_status": "pending_payment"
        }
        save_demo_user(email, new_coach)
        print(f"✅ Nouveau coach inscrit (en attente de paiement): {email}")
        
        # Connexion automatique après inscription - redirection vers page d'abonnement
        import hashlib
        unique_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
        response = RedirectResponse(url="/coach/subscription", status_code=303)
        response.set_cookie(
            key="session_token",
            value=unique_token,
            httponly=True,
            secure=False,
            samesite="lax"
        )
        return response
    
    else:
        # Connexion coach
        user_found = None
        
        # Vérifier les comptes demo hardcodés
        if email == "coach@demo.com" and password == "demopass123":
            user_found = {"email": email, "role": "coach", "full_name": "Coach Demo"}
        
        # Vérifier les utilisateurs inscrits
        if not user_found:
            cached_user = get_demo_user(email)
            if cached_user:
                stored_password = cached_user.get("password", "").strip()
                if stored_password and stored_password == password.strip():
                    # Vérifier que c'est bien un coach
                    if cached_user.get("role") == "coach":
                        user_found = cached_user
                    else:
                        return templates.TemplateResponse("coach_login.html", {
                            "request": request,
                            "error": "Ce compte n'est pas un compte coach. Utilisez la connexion client.",
                            "tab": "login"
                        }, status_code=401)
        
        if user_found:
            import hashlib
            unique_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
            
            # Auto-upgrade grandfathered accounts (created before OTP/subscription system)
            # Only target truly legacy records: profile_completed=true AND subscription_status is null/None/empty
            profile_completed = user_found.get("profile_completed", False)
            subscription_status = user_found.get("subscription_status")
            email_verified = user_found.get("email_verified")
            
            # Only upgrade if subscription_status is explicitly null/None/empty (not other valid states like "trialing")
            is_legacy_account = profile_completed and (subscription_status is None or subscription_status == "")
            
            if is_legacy_account:
                print(f"🔄 Auto-upgrading grandfathered coach account: {email}")
                # Update only the specific user, not the entire file
                updated_user = get_demo_user(email)
                if updated_user:
                    updated_user["subscription_status"] = "active"
                    # Only set email_verified if it's missing/null (not already set)
                    if email_verified is None or email_verified == "":
                        updated_user["email_verified"] = True
                    save_demo_user(email, updated_user)
                    user_found["subscription_status"] = "active"
                    if email_verified is None or email_verified == "":
                        user_found["email_verified"] = True
                    subscription_status = "active"
                    print(f"✅ Grandfathered coach upgraded: {email}")
            
            # Rediriger vers le portail ou la création de profil
            # L'abonnement n'est plus bloquant à la connexion
            redirect_url = "/coach/portal" if profile_completed else "/coach/profile-setup"
            
            response = RedirectResponse(url=redirect_url, status_code=303)
            response.set_cookie(
                key="session_token",
                value=unique_token,
                httponly=True,
                secure=False,
                samesite="lax"
            )
            return response
        else:
            return templates.TemplateResponse("coach_login.html", {
                "request": request,
                "error": "Email ou mot de passe incorrect.",
                "tab": "login"
            }, status_code=401)

# Routes protégées - Espace Coach
@app.get("/coach/portal", response_class=HTMLResponse)
async def coach_portal(request: Request, user = Depends(require_coach_role)):
    """Dashboard coach - avec vérification du profil complété et de l'abonnement."""
    
    # Charger les données fraîches depuis le fichier JSON
    coach_email = user.get("email")
    demo_users = load_demo_users()
    coach_data_fresh = demo_users.get(coach_email, {})
    
    # Récupérer les infos pour affichage (plus de blocage sur l'abonnement)
    subscription_status = coach_data_fresh.get("subscription_status", "")
    email_verified = coach_data_fresh.get("email_verified", False)
    print(f"🔍 Portal check: email={coach_email}, subscription_status='{subscription_status}', email_verified={email_verified}")
    
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
            print(f"❌ Erreur lors de la vérification du profil: {e}")
            # En cas d'erreur, rediriger vers l'onboarding par sécurité
            return RedirectResponse(url="/coach/profile-setup", status_code=302)
    else:
        # Mode démo - simuler un profil non complété pour les nouveaux utilisateurs
        if not user.get("profile_completed", False):
            return RedirectResponse(url="/coach/profile-setup", status_code=302)
        transformations = get_transformations_by_coach_mock(1)
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_portal.html", {
        "request": request,
        "coach": user,
        "transformations": transformations
    })

@app.post("/coach/portal")
async def coach_portal_update(
    request: Request,
    user = Depends(require_coach_role),
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
            return templates.TemplateResponse("coach_portal.html", {
                "request": request,
                "coach": user,
                "error": "Erreur lors de la mise à jour du profil."
            })
    
    return RedirectResponse(url="/coach/portal", status_code=303)

# Route onboarding coach
@app.get("/coach/profile-setup", response_class=HTMLResponse)
async def coach_profile_setup_get(request: Request, user = Depends(require_coach_role)):
    """Page d'onboarding/configuration du profil coach."""
    
    # Vérifier si l'email est vérifié
    coach_email = user.get("email")
    demo_users = load_demo_users()
    coach_data_check = demo_users.get(coach_email, {})
    if not coach_data_check.get("email_verified", False):
        return RedirectResponse(url="/coach/verify-email", status_code=303)
    
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
            print(f"❌ Erreur lors de la récupération du profil: {e}")
    else:
        # Mode démo - Charger les données depuis l'utilisateur connecté
        coach_data = user
        profile_completed = user.get("profile_completed", False)
        print(f"🔧 Mode démo - Chargement des données du profil pour {user.get('email', 'coach')}")
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_profile_setup.html", {
        "request": request,
        "coach": coach_data,
        "profile_completed": profile_completed,
        "user": user
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
    user = Depends(require_coach_role)
):
    """Traitement du formulaire d'onboarding coach."""
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    error_message = None
    success_message = None
    
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
                    # Mode démo - Stocker localement dans attached_assets
                    import os
                    os.makedirs("attached_assets/profile_photos", exist_ok=True)
                    
                    # Traiter l'image
                    original_content, thumb_content, filename = process_image_for_upload(photo_content, str(user_id))
                    
                    # Sauvegarder localement
                    local_path = f"attached_assets/profile_photos/{filename.replace('/', '_')}"
                    with open(local_path, "wb") as f:
                        f.write(original_content)
                    
                    profile_photo_url = f"/attached_assets/profile_photos/{filename.replace('/', '_')}"
                    print(f"✅ Photo sauvegardée localement: {profile_photo_url}")
                    
            except Exception as e:
                print(f"❌ Erreur lors du traitement de la photo: {e}")
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
                
                # Redirection vers le dashboard après succès
                return RedirectResponse(url="/coach/portal", status_code=303)
            else:
                error_message = "Erreur lors de la mise à jour du profil."
        else:
            # Mode démo - Simuler la mise à jour réussie du profil
            print(f"✅ Mode démo - Profil mis à jour pour {user.get('email', 'coach')} avec:")
            print(f"   - Nom: {full_name}")
            print(f"   - Ville: {city}")
            print(f"   - Spécialités: {specialties}")
            print(f"   - Salles IDs: {selected_gym_ids}")
            print(f"   - Salles data: {selected_gyms_data[:100] if selected_gyms_data else 'None'}...")
            
            # Mettre à jour l'utilisateur et sauvegarder dans le stockage persistant
            from utils import save_demo_user
            
            # CORRECTION : Récupérer l'email réel depuis le token
            import hashlib
            session_token = user.get("_access_token", "")
            user_email = "demo@example.com"  # Fallback par défaut
            
            # Si c'est un token démo, extraire l'email correspondant
            if session_token.startswith("demo_"):
                from utils import load_demo_users
                all_demo_users = load_demo_users()
                
                # Trouver l'email correspondant à ce token
                for email, user_data in all_demo_users.items():
                    expected_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
                    if session_token == expected_token:
                        user_email = email
                        print(f"✅ Email extrait du token: {user_email}")
                        break
            
            print(f"🔧 Mode démo - Sauvegarde profil pour: {user_email}")
            
            # CORRECTION : Récupérer les données existantes pour préserver le mot de passe
            existing_user = get_demo_user(user_email) or {}
            
            # Générer un slug unique pour ce coach (ou garder l'existant)
            existing_slug = existing_user.get("profile_slug")
            if existing_slug:
                profile_slug = existing_slug
            else:
                profile_slug = generate_unique_slug_for_coach(user_email, full_name)
            print(f"🔗 Slug du profil: {profile_slug}")
            
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
                # ✅ PRÉSERVER les données d'abonnement et vérification
                "subscription_status": existing_user.get("subscription_status"),
                "email_verified": existing_user.get("email_verified"),
                "stripe_customer_id": existing_user.get("stripe_customer_id"),
                "stripe_subscription_id": existing_user.get("stripe_subscription_id"),
                "subscription_period_end": existing_user.get("subscription_period_end"),
                "otp_code": existing_user.get("otp_code"),
                "otp_expiry": existing_user.get("otp_expiry")
            }
            
            print(f"🔒 Mot de passe préservé: {'✅' if updated_user['password'] else '❌'}")
            
            # Sauvegarder les modifications dans le stockage persistant
            save_demo_user(user_email, updated_user)
            print(f"✅ Données utilisateur démo sauvegardées avec profile_completed=True")
            
            # Redirection vers le dashboard après succès
            return RedirectResponse(url="/coach/portal", status_code=303)
            
    except Exception as e:
        print(f"❌ Erreur lors de la soumission du profil: {e}")
        error_message = "Une erreur s'est produite lors de la sauvegarde."
    
    # En cas d'erreur, recharger la page avec le message d'erreur
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_profile_setup.html", {
        "request": request,
        "coach": {"full_name": full_name, "bio": bio, "city": city, "instagram_url": instagram_url, "price_from": price_from, "radius_km": radius_km},
        "profile_completed": False,
        "error_message": error_message,
        "user": user
    })

@app.post("/coach/specialties")
async def coach_specialties_update(
    request: Request,
    user = Depends(require_coach_role),
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
    user = Depends(require_coach_role),
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
    
    if not coach:
        return templates.TemplateResponse("404.html", {
            "request": request,
            "message": f"Le coach '{slug}' n'a pas été trouvé. Il a peut-être changé de nom ou n'existe plus."
        }, status_code=404)
    
    # Assurer qu'il y a une photo
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    
    # S'assurer que les spécialités sont une liste
    specialties = coach.get("specialties", [])
    if isinstance(specialties, str):
        try:
            import json
            coach["specialties"] = json.loads(specialties)
        except:
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
        except:
            pass
    
    print(f"📋 Profil coach {slug}: spécialités={coach.get('specialties')}, salles={len(gyms)}")
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_profile.html", {
        "request": request,
        "coach": coach,
        "gyms": gyms,
        "slug": slug
    })

@app.get("/reserver/{slug}/book", response_class=HTMLResponse)
async def booking_by_slug(request: Request, slug: str):
    """Page de réservation avec URL propre (prénom)."""
    
    coach = find_coach_by_slug(slug)
    
    if not coach:
        return templates.TemplateResponse("404.html", {
            "request": request,
            "message": f"Le coach '{slug}' n'a pas été trouvé."
        }, status_code=404)
    
    # Assurer qu'il y a une photo
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    
    # Récupérer les salles associées
    gyms = []
    if coach.get("selected_gyms_data"):
        try:
            import json
            gyms = json.loads(coach.get("selected_gyms_data"))
        except:
            pass
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("booking.html", {
        "request": request,
        "coach": coach,
        "gyms": gyms,
        "slug": slug
    })

# ======================================
# ROUTE ABONNEMENT COACH (doit être AVANT /coach/{coach_id})
# ======================================

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
                        print(f"✅ Abonnement activé via redirect pour {coach_email}")
                    else:
                        update_coach_subscription(
                            coach_email=coach_email,
                            stripe_customer_id=customer_id,
                            subscription_status="active"
                        )
                        print(f"✅ Paiement confirmé (sans subscription_id) pour {coach_email}")
                except Exception as sub_err:
                    print(f"⚠️ Erreur récupération détails abonnement: {sub_err}")
                    # Activer quand même l'abonnement
                    update_coach_subscription(
                        coach_email=coach_email,
                        stripe_customer_id=customer_id if customer_id else "",
                        subscription_status="active"
                    )
                
        except Exception as e:
            print(f"⚠️ Erreur vérification session Stripe: {e}")
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
                print(f"✅ OTP sauvegardé pour {coach_email}")
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
                print(f"✅ Nouvelle entrée + OTP créés pour {coach_email}")
            
            # Envoyer l'email avec le code
            full_name = user.get("full_name", "Coach")
            try:
                send_otp_email_resend(coach_email, otp_code, full_name)
                print(f"📧 Code OTP envoyé à {coach_email}: {otp_code}")
            except Exception as email_err:
                print(f"⚠️ Erreur envoi email OTP: {email_err}")
            
            # Rediriger vers la page de vérification email
            return RedirectResponse(url="/coach/verify-email", status_code=303)
    
    # Charger les données fraîches depuis le fichier JSON
    demo_users = load_demo_users()
    coach_data_fresh = demo_users.get(coach_email, {})
    
    subscription_info = get_coach_subscription_info(coach_email)
    
    # Afficher la page d'abonnement (pas de redirection automatique)
    # Les coachs peuvent voir leur statut, gérer ou résilier leur abonnement
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_subscription.html", {
        "request": request,
        "coach": user,
        "subscription_info": subscription_info,
        "monthly_price": COACH_MONTHLY_PRICE / 100,
        "publishable_key": get_publishable_key()
    })

# ======================================
# ROUTE VERIFICATION EMAIL COACH
# ======================================

@app.get("/coach/verify-email", response_class=HTMLResponse)
async def coach_verify_email_page(request: Request, user = Depends(require_coach_or_pending)):
    """Page de vérification de l'email du coach après paiement."""
    coach_email = user.get("email")
    
    # Vérifier si l'email est déjà vérifié
    demo_users = load_demo_users()
    coach_data = demo_users.get(coach_email, {})
    
    if coach_data.get("email_verified", False):
        # Email déjà vérifié, rediriger vers profile-setup ou portal
        profile_completed = user.get("profile_completed", False)
        redirect_url = "/coach/portal" if profile_completed else "/coach/profile-setup"
        return RedirectResponse(url=redirect_url, status_code=303)
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("coach_verify_email.html", {
        "request": request,
        "coach": user,
        "email": coach_email
    })

@app.post("/api/coach/verify-email")
async def verify_coach_email(request: Request, user = Depends(require_coach_or_pending)):
    """Vérifie le code OTP envoyé par email."""
    try:
        data = await request.json()
        otp_code = data.get("otp_code", "").strip()
        coach_email = user.get("email")
        
        if not otp_code or len(otp_code) != 6:
            return JSONResponse({"success": False, "error": "Code invalide"}, status_code=400)
        
        demo_users = load_demo_users()
        coach_data = demo_users.get(coach_email, {})
        
        stored_otp = coach_data.get("otp_code")
        otp_expiry = coach_data.get("otp_expiry")
        
        if not stored_otp:
            return JSONResponse({"success": False, "error": "Aucun code en attente"}, status_code=400)
        
        # Vérifier l'expiration
        if otp_expiry and isinstance(otp_expiry, str):
            try:
                expiry_dt = datetime.fromisoformat(otp_expiry)
                if datetime.now() > expiry_dt:
                    return JSONResponse({"success": False, "error": "Code expiré. Demandez un nouveau code."}, status_code=400)
            except (ValueError, TypeError):
                pass  # Ignorer si format invalide
        
        # Vérifier le code
        if otp_code != stored_otp:
            return JSONResponse({"success": False, "error": "Code incorrect"}, status_code=400)
        
        # Marquer l'email comme vérifié
        demo_users[coach_email]["email_verified"] = True
        demo_users[coach_email]["otp_code"] = None
        demo_users[coach_email]["otp_expiry"] = None
        save_demo_users(demo_users)
        
        print(f"✅ Email vérifié pour {coach_email}")
        
        return JSONResponse({"success": True, "redirect": "/coach/profile-setup"})
    except Exception as e:
        print(f"❌ Erreur vérification OTP: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/coach/resend-otp")
async def resend_coach_otp(request: Request, user = Depends(require_coach_or_pending)):
    """Renvoie un nouveau code OTP par email."""
    try:
        import random
        from resend_service import send_otp_email_resend
        
        coach_email = user.get("email")
        full_name = user.get("full_name", "Coach")
        
        # Générer un nouveau code
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        otp_expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
        
        # Sauvegarder
        demo_users = load_demo_users()
        if coach_email in demo_users:
            demo_users[coach_email]["otp_code"] = otp_code
            demo_users[coach_email]["otp_expiry"] = otp_expiry
            save_demo_users(demo_users)
        
        # Envoyer l'email
        result = send_otp_email_resend(coach_email, otp_code, full_name)
        print(f"📧 Nouveau code OTP envoyé à {coach_email}: {otp_code}")
        
        return JSONResponse({"success": True, "message": "Code envoyé"})
    except Exception as e:
        print(f"❌ Erreur renvoi OTP: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

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
    
    # Si coach non trouvé dans JSON, essayer de charger depuis demo_users
    if not coach:
        user_supabase = None
        if supabase_anon:
            try:
                response = supabase_anon.table("profiles").select("*").eq("user_id", coach_id).single().execute()
                if response.data:
                    coach = response.data
            except Exception as e:
                print(f"Coach non trouvé dans Supabase: {e}")
        
        # Sinon, charger depuis demo_users
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
    
    # Assurer qu'il y a une photo (profile_photo_url ou photo, sinon défaut)
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    
    # S'assurer que les spécialités sont une liste
    specialties = coach.get("specialties", [])
    if isinstance(specialties, str):
        try:
            import json
            coach["specialties"] = json.loads(specialties)
        except:
            coach["specialties"] = [s.strip() for s in specialties.split(",") if s.strip()]
    
    # Récupérer les salles associées au coach
    gyms = []
    if coach.get("gyms"):
        # Pour les coaches du JSON
        for gym_id in coach.get("gyms", []):
            gym_data = get_gym_by_id(gym_id)
            if gym_data:
                gyms.append(gym_data)
    elif coach.get("selected_gyms_data"):
        # Pour les coaches avec selected_gyms_data (format JSON string)
        try:
            import json
            gyms_data = coach.get("selected_gyms_data")
            if isinstance(gyms_data, str) and gyms_data.strip():
                gyms = json.loads(gyms_data)
            elif isinstance(gyms_data, list):
                gyms = gyms_data
        except:
            pass
    
    print(f"📋 Profil coach {coach_id}: spécialités={coach.get('specialties')}, salles={len(gyms)}")
    
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
                print(f"Coach non trouvé dans Supabase: {e}")
        
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
    
    if not coach.get("photo"):
        coach["photo"] = coach.get("profile_photo_url", "/static/default-avatar.jpg")
    
    # Parser les données des salles si c'est une string JSON
    if coach.get("selected_gyms_data") and isinstance(coach["selected_gyms_data"], str):
        try:
            import json
            coach["gyms"] = json.loads(coach["selected_gyms_data"])
        except:
            coach["gyms"] = []
    elif not coach.get("gyms"):
        coach["gyms"] = []
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("booking.html", {
        "request": request,
        "coach": coach
    })

@app.get("/reservation", response_class=HTMLResponse)
async def reservation_page(request: Request):
    """Page de confirmation de réservation avec identification."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("reservation.html", {
        "request": request
    })

@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    """Page Mon compte avec les séances."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("account.html", {
        "request": request
    })

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
            user_slug = user_data.get("slug", "")
            if user_data.get("role") == "coach" and (
                str(user_data.get("id")) == coach_id or 
                user_data.get("email") == coach_id or 
                encoded_email == coach_id or
                user_slug == coach_id
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
        working_hours = coach_data.get("working_hours", default_hours) if coach_data else default_hours
        
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
        print(f"Erreur lors de la récupération des disponibilités: {e}")
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
        print(f"Erreur: {e}")
        return {"unavailable_days": [], "unavailable_slots": []}

@app.post("/api/coach/unavailability")
async def set_coach_unavailability(request: Request):
    """Ajoute ou supprime des indisponibilités pour un coach."""
    try:
        data = await request.json()
        coach_email = data.get("coach_email")
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
        
        # Sauvegarder
        demo_users[coach_email] = coach_data
        save_demo_users(demo_users)
        
        return {
            "success": True,
            "unavailable_days": coach_data["unavailable_days"],
            "unavailable_slots": coach_data["unavailable_slots"]
        }
        
    except Exception as e:
        print(f"Erreur: {e}")
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
        
        return coach_data.get("working_hours", default_hours)
    except Exception as e:
        print(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/coach/working-hours")
async def set_coach_working_hours(request: Request):
    """Définit les horaires de travail d'un coach."""
    try:
        data = await request.json()
        coach_email = data.get("coach_email")
        working_hours = data.get("working_hours")
        
        if not coach_email or not working_hours:
            return JSONResponse(status_code=400, content={"error": "Missing data"})
        
        demo_users = load_demo_users()
        
        if coach_email not in demo_users:
            return JSONResponse(status_code=404, content={"error": "Coach not found"})
        
        demo_users[coach_email]["working_hours"] = working_hours
        save_demo_users(demo_users)
        
        return {"success": True, "working_hours": working_hours}
        
    except Exception as e:
        print(f"Erreur: {e}")
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
        print(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/coach/session-duration")
async def set_coach_session_duration(request: Request):
    """Définit la durée de séance d'un coach."""
    try:
        data = await request.json()
        coach_email = data.get("coach_email")
        duration = data.get("duration")
        
        if not coach_email or duration not in [30, 60, 90, 120]:
            return JSONResponse(status_code=400, content={"success": False, "error": "Données invalides"})
        
        demo_users = load_demo_users()
        
        if coach_email not in demo_users:
            return JSONResponse(status_code=404, content={"success": False, "error": "Coach non trouvé"})
        
        demo_users[coach_email]["session_duration"] = duration
        save_demo_user(coach_email, demo_users[coach_email])
        
        print(f"Durée de séance mise à jour pour {coach_email}: {duration} min")
        
        return {"success": True, "duration": duration}
        
    except Exception as e:
        print(f"Erreur: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/coach/payment-mode")
async def set_coach_payment_mode(request: Request, user = Depends(require_coach_role)):
    """Definit le mode de paiement d'un coach (disabled ou required)."""
    try:
        from db_service import get_stripe_connect_info
        
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
            print(f"📋 Vérification Stripe Connect pour {coach_email}")
            print(f"   Connect Info: {connect_info}")
            if not connect_info:
                print(f"   ❌ Pas de compte Stripe Connect")
                return JSONResponse(status_code=400, content={
                    "success": False, 
                    "error": "Vous devez d'abord connecter votre compte Stripe pour activer le paiement en ligne.",
                    "need_stripe_connect": True
                })
            if not connect_info.get("charges_enabled"):
                print(f"   ❌ charges_enabled = {connect_info.get('charges_enabled')} (doit être True)")
                print(f"   Details submitted: {connect_info.get('details_submitted')}")
                return JSONResponse(status_code=400, content={
                    "success": False, 
                    "error": "Votre compte Stripe n'a pas été complètement vérifié. Veuillez attendre 1-2 jours ou vérifier votre email Stripe.",
                    "need_stripe_connect": True,
                    "charges_enabled": False,
                    "details_submitted": connect_info.get("details_submitted", False)
                })
        
        demo_users[coach_email]["payment_mode"] = payment_mode
        save_demo_user(coach_email, demo_users[coach_email])
        
        print(f"✅ Mode de paiement mis a jour pour {coach_email}: {payment_mode}")
        
        return {"success": True, "payment_mode": payment_mode}
        
    except Exception as e:
        print(f"❌ Erreur mise a jour mode paiement: {e}")
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
        print(f"Erreur récupération mode paiement: {e}")
        return {"payment_mode": "disabled"}


@app.get("/api/coach/stripe-connect/status")
async def get_stripe_connect_status(user = Depends(require_coach_role)):
    """Récupère le statut Stripe Connect d'un coach."""
    try:
        from db_service import get_stripe_connect_info
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
        print(f"Erreur statut Stripe Connect: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/coach/stripe-connect/onboard")
async def start_stripe_connect_onboarding(request: Request, user = Depends(require_coach_role)):
    """Démarre l'onboarding Stripe Connect pour un coach."""
    try:
        from db_service import get_stripe_connect_info, update_stripe_connect_status
        from stripe_connect_service import create_connect_account, create_account_link
        
        coach_email = user.get("email")
        coach_name = user.get("full_name", "Coach")
        
        host = request.headers.get("host", "localhost:5000")
        protocol = "https" if "replit" in host else "http"
        base_url = f"{protocol}://{host}"
        
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
        print(f"Erreur onboarding Stripe Connect: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/coach/stripe-connect/refresh")
async def refresh_stripe_connect_onboarding(request: Request, user = Depends(require_coach_role)):
    """Génère un nouveau lien d'onboarding si l'ancien a expiré."""
    try:
        from db_service import get_stripe_connect_info
        from stripe_connect_service import create_account_link
        
        coach_email = user.get("email")
        connect_info = get_stripe_connect_info(coach_email)
        
        if not connect_info or not connect_info.get("account_id"):
            return RedirectResponse(url="/coach/portal?error=no_account")
        
        host = request.headers.get("host", "localhost:5000")
        protocol = "https" if "replit" in host else "http"
        base_url = f"{protocol}://{host}"
        
        link_result = create_account_link(
            account_id=connect_info["account_id"],
            return_url=f"{base_url}/coach/portal?stripe_connected=1",
            refresh_url=f"{base_url}/api/coach/stripe-connect/refresh"
        )
        
        if link_result.get("success"):
            return RedirectResponse(url=link_result["url"])
        
        return RedirectResponse(url="/coach/portal?error=stripe_link")
        
    except Exception as e:
        print(f"Erreur refresh Stripe Connect: {e}")
        return RedirectResponse(url="/coach/portal?error=stripe_error")


@app.post("/api/coach/stripe-connect/sync")
async def sync_stripe_connect_status(user = Depends(require_coach_role)):
    """Synchronise le statut Stripe Connect après le retour de l'onboarding."""
    try:
        from db_service import get_stripe_connect_info, update_stripe_connect_status
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
        print(f"Erreur sync Stripe Connect: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/bookings")
async def get_bookings(coach_id: str, from_date: str = Query(..., alias="from"), to_date: str = Query(..., alias="to"), include_pending: bool = Query(False)):
    """Récupère les réservations existantes d'un coach.
    
    Args:
        include_pending: Si True, inclut les réservations en attente (pour le calendrier du coach).
                        Si False, n'inclut que les confirmées (pour le calendrier de réservation client).
    """
    # Charger depuis demo_users.json
    try:
        demo_users = load_demo_users()
        
        # Chercher le coach par ID ou slug
        coach_email = None
        for email, user_data in demo_users.items():
            encoded_email = email.replace("@", "_").replace(".", "_")
            user_slug = user_data.get("slug", "")
            if user_data.get("role") == "coach" and (
                str(user_data.get("id")) == coach_id or 
                user_data.get("email") == coach_id or 
                encoded_email == coach_id or
                user_slug == coach_id
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
        working_hours = coach_data.get("working_hours", default_hours)
        
        # Filtrer par période
        from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        filtered_bookings = []
        
        # Ajouter les réservations pending
        for booking in pending_bookings:
            booking_date = booking.get("date", "")
            booking_time = booking.get("time", "")
            if booking_date and booking_time:
                try:
                    booking_start = datetime.fromisoformat(f"{booking_date}T{booking_time}:00")
                    booking_end = booking_start + timedelta(hours=1)
                    if from_dt.date() <= booking_start.date() <= to_dt.date():
                        filtered_bookings.append({
                            "start": booking_start.isoformat(),
                            "end": booking_end.isoformat(),
                            "title": f"{booking.get('client_name', 'Client')} - En attente",
                            "status": "pending"
                        })
                except:
                    pass
        
        # Ajouter les réservations confirmées
        for booking in confirmed_bookings:
            booking_date = booking.get("date", "")
            booking_time = booking.get("time", "")
            if booking_date and booking_time:
                try:
                    booking_start = datetime.fromisoformat(f"{booking_date}T{booking_time}:00")
                    booking_end = booking_start + timedelta(hours=1)
                    if from_dt.date() <= booking_start.date() <= to_dt.date():
                        filtered_bookings.append({
                            "start": booking_start.isoformat(),
                            "end": booking_end.isoformat(),
                            "title": f"{booking.get('client_name', 'Client')} - Confirmé",
                            "status": "confirmed"
                        })
                except:
                    pass
        
        # Ajouter les jours complets indisponibles (bloquer tous les créneaux de la journée)
        for date_str in unavailable_days:
            try:
                # Parser la date (format: "2025-12-05")
                day_date = datetime.strptime(date_str, "%Y-%m-%d")
                if from_dt.replace(tzinfo=None).date() <= day_date.date() <= to_dt.replace(tzinfo=None).date():
                    # Bloquer toute la journée (10h-00h)
                    for hour in range(10, 24):
                        slot_start = day_date.replace(hour=hour, minute=0)
                        slot_end = slot_start + timedelta(hours=1)
                        filtered_bookings.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "title": "Indisponible",
                            "status": "unavailable"
                        })
            except Exception as e:
                print(f"Erreur parsing date indisponible {date_str}: {e}")
                pass
        
        # Ajouter les créneaux spécifiques indisponibles
        for slot in unavailable_slots:
            slot_date = slot.get("date", "")
            slot_time = slot.get("time", "")
            if slot_date and slot_time:
                try:
                    slot_start = datetime.fromisoformat(f"{slot_date}T{slot_time}:00")
                    slot_end = slot_start + timedelta(hours=1)
                    if from_dt.date() <= slot_start.date() <= to_dt.date():
                        filtered_bookings.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "title": "Indisponible",
                            "status": "unavailable"
                        })
                except:
                    pass
        
        return {
            "bookings": filtered_bookings,
            "working_hours": working_hours
        }
    except Exception as e:
        print(f"Erreur lors de la récupération des réservations: {e}")
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
        print(f"Erreur lors de la création de la réservation: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la création de la réservation")

# ======================================
# ENDPOINTS API COACH - GESTION DES LIEUX
# ======================================

@app.get("/api/coach/gyms")
async def get_coach_gym_locations(user = Depends(require_coach_role)):
    """Récupère les lieux de coaching d'un coach."""
    try:
        coach_id = str(user["id"])
        gym_relations = get_coach_gyms(coach_id)
        
        return {
            "success": True,
            "gyms": gym_relations
        }
        
    except Exception as e:
        print(f"Erreur récupération lieux coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des lieux",
            "gyms": []
        }

@app.post("/api/coach/gyms")
async def add_coach_gym_location(
    request: Request,
    user = Depends(require_coach_role)
):
    """
    Ajoute un lieu de coaching pour un coach.
    Accepte 2 formats :
    1. Ancien : {"query": "nom ou adresse"} -> géocodage automatique
    2. Nouveau : {"gym_data": {...}} -> salle pré-sélectionnée avec toutes les infos
    """
    try:
        coach_id = str(user["id"])
        
        # Récupérer les données JSON de la requête
        data = await request.json()
        
        gym_data = None
        
        # Format NOUVEAU : gym_data complet (salle sélectionnée depuis l'autocomplétion)
        if "gym_data" in data:
            print("🎯 NOUVEAU FORMAT: Salle pré-sélectionnée")
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
            print("🔄 ANCIEN FORMAT: Géocodage nécessaire")
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
        
        print(f"📍 Ajout salle: {gym_data['name']} à {gym_data['address']}")
        
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
        print(f"Erreur ajout lieu coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de l'ajout du lieu"
        }

@app.delete("/api/coach/gyms/{gym_id}")
async def remove_coach_gym_location(
    gym_id: str,
    user = Depends(require_coach_role)
):
    """Supprime un lieu de coaching d'un coach."""
    try:
        coach_id = str(user["id"])
        
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
        print(f"Erreur suppression lieu coach: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la suppression"
        }

# ======================================
# ENDPOINTS API CLIENT - RECHERCHE SALLES
# ======================================

@app.get("/api/coaches")
async def get_all_coaches_api(
    gym_id: Optional[str] = None,
    specialty: Optional[str] = None,
    postal_code: Optional[str] = None
):
    """
    🔥 NOUVEAU: Retourne les VRAIS coaches depuis la base de données (demo_users.json).
    
    Paramètres:
    - gym_id: Filtrer par salle (ex: "fitness-park-maurepas")
    - specialty: Filtrer par spécialité (ex: "musculation")
    - postal_code: Filtrer par code postal
    """
    try:
        coaches = []
        
        # Si filtrage par salle
        if gym_id:
            coaches = get_coaches_by_gym_id(gym_id)
        else:
            # Charger TOUS les vrais coaches
            from utils import load_demo_users
            demo_users = load_demo_users()
            
            for email, user_data in demo_users.items():
                # Ne prendre que les coaches avec profil complété
                if user_data.get("role") == "coach" and user_data.get("profile_completed"):
                    coaches.append({
                        "id": email.replace("@", "_").replace(".", "_"),
                        "email": email,
                        "full_name": user_data.get("full_name", "Coach"),
                        "bio": user_data.get("bio", ""),
                        "city": user_data.get("city", ""),
                        "specialties": user_data.get("specialties", []),
                        "price_from": user_data.get("price_from", 50),
                        "rating": 4.5,  # Valeur par défaut
                        "reviews_count": 10,  # Valeur par défaut
                        "verified": True,
                        "photo": user_data.get("photo", "/static/default-avatar.jpg"),
                        "instagram_url": user_data.get("instagram_url", ""),
                        "gyms": user_data.get("selected_gym_ids", "").split(",") if user_data.get("selected_gym_ids") else []
                    })
            
            # Filtrer par spécialité si demandé
            if specialty:
                coaches = [c for c in coaches if specialty.lower() in [s.lower() for s in c.get("specialties", [])]]
            
            # Filtrer par code postal si demandé
            if postal_code:
                # Pour chaque coach, vérifier si une de ses salles est dans ce code postal
                coaches_filtered = []
                gyms_file = os.path.join("static", "data", "gyms.json")
                if os.path.exists(gyms_file):
                    with open(gyms_file, 'r', encoding='utf-8') as f:
                        all_gyms = json.load(f)
                        gyms_in_postal = [g["id"] for g in all_gyms if g.get("postal_code") == postal_code]
                        
                        for coach in coaches:
                            if any(gym_id in coach.get("gyms", []) for gym_id in gyms_in_postal):
                                coaches_filtered.append(coach)
                        coaches = coaches_filtered
        
        return {
            "success": True,
            "count": len(coaches),
            "coaches": coaches
        }
    
    except Exception as e:
        print(f"❌ Erreur API /api/coaches: {e}")
        return {
            "success": False,
            "error": str(e),
            "coaches": []
        }

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
        
        # 🆕 Recherche par code postal
        if postal_code:
            print(f"🔍 Recherche salles par code postal: {postal_code}")
            import json
            import os
            import re
            
            # 1. Charger les salles depuis le JSON statique
            gyms_file = os.path.join("static", "data", "gyms.json")
            if os.path.exists(gyms_file):
                with open(gyms_file, 'r', encoding='utf-8') as f:
                    all_gyms = json.load(f)
                    # Filtrer par code postal
                    for gym in all_gyms:
                        if gym.get("postal_code") == postal_code:
                            # Compter les coachs dans cette salle
                            coaches_in_gym = get_coaches_by_gym_id(gym["id"])
                            gym_result = gym.copy()
                            gym_result["coach_count"] = len(coaches_in_gym)
                            results.append(gym_result)
            
            # 2. AUSSI charger les salles Google Places depuis les profils des coaches
            demo_users = load_demo_users()
            google_gyms_seen = set()
            
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
                                
                                # Éviter les doublons
                                if gym_id in google_gyms_seen:
                                    continue
                                
                                # Extraire le code postal de l'adresse Google Places
                                address = gym.get("address", "")
                                # Chercher un pattern "78310" dans l'adresse
                                cp_match = re.search(r'\b(\d{5})\b', address)
                                
                                if cp_match and cp_match.group(1) == postal_code:
                                    google_gyms_seen.add(gym_id)
                                    
                                    # Compter les coachs dans cette salle
                                    coaches_in_gym = get_coaches_by_gym_id(gym_id)
                                    
                                    gym_result = {
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
                                        "coach_count": len(coaches_in_gym)
                                    }
                                    results.append(gym_result)
                    except:
                        continue
            
            print(f"✅ {len(results)} salles trouvées pour le code postal {postal_code}")
            return {
                "success": True,
                "gyms": results,
                "count": len(results),
                "search_type": "postal_code"
            }
        
        elif q:
            # 🎯 NOUVEAU: Détection automatique des recherches par zone/arrondissement
            zone_results = search_gyms_by_zone(q)
            if zone_results:
                # Recherche par zone réussie - afficher TOUTES les salles de cette zone
                results = zone_results
            else:
                # Recherche classique par géocodage + rayon
                geocoded = geocode_address(q)
                if geocoded:
                    search_lat = geocoded["lat"]
                    search_lng = geocoded["lng"]
                    
                    # 🆕 PRIORITÉ 1: Google Places API
                    google_results = search_gyms_google_places(search_lat, search_lng, radius_km)
                    
                    # PRIORITÉ 2: Base de données locale
                    local_results = search_gyms_by_location(search_lat, search_lng, radius_km)
                    
                    # Fusionner les résultats (Google Places en priorité)
                    results = google_results + local_results
                    
                    # Dédupliquer par nom + adresse similaire
                    seen_gyms = set()
                    unique_results = []
                    for gym in results:
                        # Créer une clé unique basée sur nom + début de l'adresse
                        key = f"{gym['name'].lower()[:30]}_{gym.get('address', '')[:30].lower()}"
                        if key not in seen_gyms:
                            seen_gyms.add(key)
                            unique_results.append(gym)
                    
                    results = unique_results
                    # Trier par distance
                    results.sort(key=lambda x: x.get("distance_km", 999))
                else:
                    # Recherche par nom dans GYMS_DATABASE si géocodage échoue
                    for gym in GYMS_DATABASE:
                        if q.lower() in gym["name"].lower() or q.lower() in gym["address"].lower():
                            # Compter les coachs dans cette salle
                            coach_count = len(get_coaches_by_gym(gym["address"]))
                            gym_result = gym.copy()
                            gym_result["distance_km"] = None  # Pas de distance si recherche par nom
                            gym_result["coach_count"] = coach_count
                            results.append(gym_result)
        
        elif lat is not None and lng is not None:
            # Recherche par coordonnées
            search_lat = lat
            search_lng = lng
            
            # 🆕 Combiner Google Places + base locale
            google_results = search_gyms_google_places(search_lat, search_lng, radius_km)
            local_results = search_gyms_by_location(search_lat, search_lng, radius_km)
            
            # Fusionner et dédupliquer
            results = google_results + local_results
            seen_gyms = set()
            unique_results = []
            for gym in results:
                key = f"{gym['name'].lower()[:30]}_{gym.get('address', '')[:30].lower()}"
                if key not in seen_gyms:
                    seen_gyms.add(key)
                    unique_results.append(gym)
            
            results = unique_results
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
            "count": len(results)
        }
        
    except Exception as e:
        print(f"Erreur recherche salles: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche",
            "gyms": []
        }

@app.get("/api/gyms/worldwide-search")
async def search_gyms_worldwide(q: str):
    """
    🌍 NOUVEAU: Recherche MONDIALE de salles via Google Places API.
    Permet aux coachs et clients de chercher n'importe quelle salle dans le monde.
    Paramètres: q = nom de salle, adresse, ville, pays...
    """
    try:
        print(f"🌍 RECHERCHE MONDIALE: {q}")
        
        if len(q.strip()) < 3:
            return {
                "success": True,
                "gyms": [],
                "message": "Tapez au moins 3 caractères"
            }
        
        # Utiliser la nouvelle fonction de recherche mondiale
        results = search_gyms_worldwide_autocomplete(q)
        
        return {
            "success": True,
            "gyms": results,
            "count": len(results),
            "message": f"{len(results)} salle(s) trouvée(s) dans le monde"
        }
        
    except Exception as e:
        print(f"❌ Erreur recherche mondiale: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche mondiale",
            "gyms": []
        }

@app.get("/api/gyms/suggestions")
async def get_gym_suggestions(q: str):
    """
    ENDPOINT COACH : Recherche TOUTES les salles de France pour l'autocomplétion coach.
    Utilise l'API Data ES (7951 salles de musculation + 4125 salles collectives).
    Paramètres: q = nom partiel de salle ou ville
    """
    try:
        print(f"🎯 COACH RECHERCHE: {q}")
        
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
                        
                print(f"🏛️ API Data ES (par nom): {len(suggestions)} suggestions trouvées")
                        
            except Exception as api_error:
                print(f"⚠️ Erreur API Data ES (par nom): {api_error}")
        
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
        
        print(f"🎯 TOTAL SUGGESTIONS COACH: {len(suggestions)} salles trouvées")
        
        return {
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        print(f"Erreur suggestions coach: {e}")
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
        print(f"Erreur récupération coachs pour salle '{gym_address}': {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des coachs",
            "coaches": []
        }

@app.get("/api/gyms/{gym_id}/coaches")  
async def get_gym_coaches_by_id(gym_id: str):
    """
    Récupère tous les coachs disponibles dans une salle par ID.
    🆕 NOUVEAU: Charge depuis static/data/coaches.json + tri par vérification, note, avis.
    """
    try:
        print(f"🔍 Recherche coaches pour gym_id: {gym_id}")
        
        # 🆕 Charger depuis le JSON statique
        coaches = get_coaches_by_gym_id(gym_id)
        
        # 🆕 Trier par : vérifiés → note → nb d'avis
        coaches_sorted = sorted(
            coaches,
            key=lambda c: (
                -int(c.get("verified", False)),  # Vérifiés en premier (True=1, False=0, inverse pour desc)
                -c.get("rating", 0),  # Note décroissante
                -c.get("reviews_count", 0)  # Nombre d'avis décroissant
            )
        )
        
        # Récupérer les infos de la gym depuis le JSON
        import json, os
        gym_info = None
        gyms_file = os.path.join("static", "data", "gyms.json")
        if os.path.exists(gyms_file):
            with open(gyms_file, 'r', encoding='utf-8') as f:
                all_gyms = json.load(f)
                gym_info = next((g for g in all_gyms if g["id"] == gym_id), None)
        
        print(f"📊 Résultat pour {gym_id}: {len(coaches_sorted)} coaches trouvés")
        
        return {
            "success": True,
            "coaches": coaches_sorted,
            "count": len(coaches_sorted),
            "gym_id": gym_id,
            "gym_info": gym_info
        }
        
    except Exception as e:
        print(f"❌ Erreur récupération coachs pour gym_id '{gym_id}': {e}")
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
        print(f"🔍 Recherche coaches - gym_id: {gym_id}, gym_name: {gym_name}")
        
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
                except:
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
        
        print(f"📊 Résultat: {len(coaches_sorted)} coaches trouvés pour {gym_name or gym_id}")
        
        return {
            "success": True,
            "coaches": coaches_sorted,
            "count": len(coaches_sorted),
            "gym_id": gym_id,
            "gym_name": gym_name
        }
        
    except Exception as e:
        print(f"❌ Erreur récupération coaches: {e}")
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
        print(f"❌ Erreur récupération pays: {e}")
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
                "message": "Base de données non disponible en mode démo",
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
        print(f"❌ Erreur récupération salles mondiales: {e}")
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
                "message": "Base de données non disponible en mode démo",
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
        print(f"❌ Erreur recherche géographique salles: {e}")
        return {
            "success": False,
            "message": "Erreur lors de la recherche géographique",
            "gyms": []
        }

# Route pour la page de recherche de salles Google Maps
@app.get("/gyms/finder")
async def gym_finder_page(request: Request, user = Depends(get_current_user)):
    """Page de recherche de salles avec Google Maps integration."""
    import os
    
    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not google_maps_api_key:
        # En mode de développement, rediriger vers une page d'erreur
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Configuration Google Maps manquante. Contactez l'administrateur.",
            "user": user
        }, status_code=500)
    
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("gym_finder.html", {
        "request": request,
        "user": user,
        "google_maps_api_key": google_maps_api_key
    })

# Route pour les images uploadées (si pas d'utilisation directe de Supabase Storage)
@app.get("/images/{image_path:path}")
async def serve_image(image_path: str):
    """Servir les images uploadées."""
    # Cette route peut être utilisée pour servir des images locales
    # En production, préférer utiliser directement Supabase Storage
    pass

# ===== API ENDPOINTS POUR VÉRIFICATION EMAIL =====

class SendOTPRequest(BaseModel):
    email: str

class VerifyOTPRequest(BaseModel):
    email: str
    code: str

class SignupReservationRequest(BaseModel):
    fullName: str
    email: str
    password: str

# Stockage temporaire des codes OTP (en production, utiliser Redis ou DB)
otp_storage = {}

@app.post("/api/signup-reservation")
async def signup_reservation(request: SignupReservationRequest):
    """Inscription rapide depuis la page de réservation avec création de session."""
    try:
        email = request.email.lower().strip()
        full_name = request.fullName.strip()
        password = request.password
        
        print(f"🔐 API signup-reservation appelée pour {email} ({full_name})")
        
        # Vérifier si l'utilisateur existe déjà
        demo_users = load_demo_users()
        if email in demo_users:
            # L'utilisateur existe déjà, on met à jour le nom si différent
            existing_user = demo_users[email]
            if existing_user.get("full_name") != full_name:
                existing_user["full_name"] = full_name
                save_demo_users(demo_users)
                print(f"✅ Nom mis à jour pour {email}: {full_name}")
        else:
            # Créer un nouvel utilisateur client
            user_data = {
                "full_name": full_name,
                "gender": "homme",
                "role": "client",
                "password": password,
                "coach_gender_preference": "aucune",
                "selected_gyms": []
            }
            demo_users[email] = user_data
            save_demo_users(demo_users)
            print(f"✅ Nouvel utilisateur créé: {email} ({full_name})")
        
        # Créer un token de session pour le client
        token = f"demo_{secrets.token_hex(8)}"
        demo_token_map[token] = email
        
        print(f"🔐 Session créée pour {email} avec token {token}")
        
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
            path="/"
        )
        
        print(f"🍪 Cookie session_token défini avec token {token}")
        
        return json_response
        
    except Exception as e:
        print(f"❌ Erreur inscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send-otp-email")
async def send_otp_email(request: SendOTPRequest):
    """Envoie un code OTP à 6 chiffres par email via Resend (utilise le même service que /signup)."""
    try:
        # Générer un code à 6 chiffres
        code = str(random.randint(100000, 999999))
        
        # Utiliser le même service que /signup (resend_service.py)
        email_result = send_otp_email_resend(request.email, code, None)
        
        if not email_result.get("success"):
            raise Exception(email_result.get("error", "Erreur envoi email"))
        
        # Stocker le code avec expiration (5 minutes)
        otp_storage[request.email] = {
            "code": code,
            "expires_at": datetime.now() + timedelta(minutes=5)
        }
        
        print(f"✅ Email OTP envoyé à {request.email} avec le code {code}")
        
        return JSONResponse({
            "success": True,
            "message": f"Code envoyé à {request.email}",
            "mode": email_result.get("mode", "resend")
        })
        
    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
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
        print(f"❌ Erreur vérification OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification: {str(e)}")


# ===== CONFIRMATION DE RÉSERVATION AVEC EMAIL =====
class ConfirmBookingRequest(BaseModel):
    client_name: str
    client_email: str
    coach_name: str
    coach_email: Optional[str] = None  # Email du coach pour identification fiable
    gym_name: str
    gym_address: Optional[str] = "Adresse non renseignée"
    date: str  # format: "2025-11-28"
    time: str  # format: "14:00"
    service: str
    duration: str
    price: str
    coach_photo: Optional[str] = None


class CancelBookingRequest(BaseModel):
    client_name: str
    client_email: str
    coach_name: str
    coach_email: Optional[str] = None  # Email du coach pour identification
    gym_name: str
    gym_address: Optional[str] = "Adresse non renseignée"
    date: str  # format en français: "vendredi 28 novembre 2025"
    time: str  # format: "14:00"
    service: str
    duration: str
    price: str
    coach_photo: Optional[str] = None
    booking_url: Optional[str] = None


class CoachBookingRequest(BaseModel):
    coach_email: str
    booking_id: str
    action: str  # "confirm" ou "reject"


@app.post("/api/confirm-booking")
async def confirm_booking(request: ConfirmBookingRequest):
    """Enregistre une demande de réservation selon le mode de paiement du coach.
    - Mode 'disabled': réservation en attente, coach notifié pour accepter/refuser
    - Mode 'required': paiement Stripe requis, réservation confirmée automatiquement après paiement
    """
    try:
        from resend_service import send_coach_notification_email, send_booking_confirmation_email
        import uuid
        
        # Formater la date en français
        from datetime import datetime as dt
        try:
            date_obj = dt.strptime(request.date, "%Y-%m-%d")
            date_fr = date_obj.strftime("%A %d %B %Y").capitalize()
            # Traduire en français
            jours = {"Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi", 
                     "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche"}
            mois = {"January": "janvier", "February": "février", "March": "mars", "April": "avril",
                    "May": "mai", "June": "juin", "July": "juillet", "August": "août",
                    "September": "septembre", "October": "octobre", "November": "novembre", "December": "décembre"}
            for en, fr in jours.items():
                date_fr = date_fr.replace(en, fr)
            for en, fr in mois.items():
                date_fr = date_fr.replace(en, fr)
        except:
            date_fr = request.date
        
        print(f"📧 Confirmation réservation pour {request.client_name} ({request.client_email})")
        print(f"   Coach: {request.coach_name}, Salle: {request.gym_name}")
        print(f"   Date: {date_fr} à {request.time}")
        
        # Générer un ID unique pour la réservation
        booking_id = str(uuid.uuid4())[:8]
        
        # Sauvegarder la réservation dans demo_users.json (sous le coach correspondant)
        try:
            demo_users = load_demo_users()
            
            # Trouver le coach - priorité à l'email si fourni
            coach_email = None
            print(f"🔍 Recherche coach - email reçu: '{request.coach_email}', nom: '{request.coach_name}'")
            
            # 1. Match direct par email
            if request.coach_email and request.coach_email in demo_users:
                coach_email = request.coach_email
                print(f"✅ Coach trouvé par email direct: {coach_email}")
            
            # 2. Fallback: décoder le slug (email_avec_underscore → email@réel)
            if not coach_email and request.coach_email:
                # Essayer de décoder le slug en email
                for email in demo_users.keys():
                    encoded_email = email.replace("@", "_").replace(".", "_")
                    if encoded_email == request.coach_email:
                        if demo_users[email].get("role") == "coach":
                            coach_email = email
                            print(f"✅ Coach trouvé par slug décodé: {coach_email}")
                            break
            
            # 3. Fallback: recherche par nom normalisé (strip + lower)
            if not coach_email:
                normalized_coach_name = request.coach_name.strip().lower()
                for email, user_data in demo_users.items():
                    if user_data.get("role") == "coach":
                        stored_name = user_data.get("full_name", "").strip().lower()
                        if stored_name == normalized_coach_name:
                            coach_email = email
                            print(f"✅ Coach trouvé par nom normalisé: {coach_email}")
                            break
            
            if not coach_email:
                print(f"⚠️ Coach non trouvé - email: {request.coach_email}, nom: {request.coach_name}")
                return JSONResponse({
                    "success": False,
                    "message": "Coach non trouvé",
                    "error": "coach_not_found"
                }, status_code=404)
            
            # Vérifier le mode de paiement du coach
            coach_data = demo_users[coach_email]
            payment_mode = coach_data.get("payment_mode", "disabled")
            print(f"💳 Mode de paiement du coach: {payment_mode}")
            
            # Créer l'objet réservation
            new_booking = {
                "id": booking_id,
                "client_name": request.client_name,
                "client_email": request.client_email,
                "gym_name": request.gym_name,
                "gym_address": request.gym_address or "",
                "date": request.date,
                "time": request.time,
                "service": request.service,
                "duration": request.duration,
                "price": request.price,
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
                
                print(f"💳 Réservation {booking_id} en attente de paiement")
                
                # Créer une session Stripe Checkout pour le paiement de la séance
                if STRIPE_AVAILABLE:
                    try:
                        from db_service import get_stripe_connect_info
                        from stripe_connect_service import create_session_payment_checkout
                        
                        # Vérifier que le coach a un compte Stripe Connect actif
                        connect_info = get_stripe_connect_info(coach_email)
                        
                        if not connect_info or not connect_info.get("charges_enabled"):
                            print(f"❌ Coach {coach_email} n'a pas de compte Stripe Connect actif")
                            return JSONResponse({
                                "success": False,
                                "message": "Le coach n'a pas configuré son compte bancaire pour recevoir les paiements",
                                "error": "connect_not_configured"
                            }, status_code=400)
                        
                        coach_connect_account_id = connect_info.get("account_id")
                        
                        # Prix en centimes
                        price_cents = int(float(request.price)) * 100
                        
                        # Construire les URLs de retour
                        base_url = os.environ.get('REPLIT_DEV_DOMAIN', 'https://fitmatch.replit.app')
                        if not base_url.startswith('http'):
                            base_url = f"https://{base_url}"
                        
                        # Créer le checkout avec transfer_data vers le coach
                        checkout_result = create_session_payment_checkout(
                            coach_account_id=coach_connect_account_id,
                            coach_email=coach_email,
                            client_email=request.client_email,
                            client_name=request.client_name,
                            amount_cents=price_cents,
                            service_name=f"Séance avec {request.coach_name} - {request.service} - {request.duration} min @ {request.gym_name}",
                            booking_id=booking_id,
                            success_url=f"{base_url}/booking-success?booking_id={booking_id}&session_id={{CHECKOUT_SESSION_ID}}",
                            cancel_url=f"{base_url}/booking-cancelled?booking_id={booking_id}"
                        )
                        
                        if not checkout_result.get("success"):
                            print(f"❌ Erreur création checkout: {checkout_result.get('error')}")
                            return JSONResponse({
                                "success": False,
                                "message": "Erreur lors de la création du paiement",
                                "error": checkout_result.get("error")
                            }, status_code=500)
                        
                        print(f"✅ Session Stripe Connect créée: {checkout_result.get('session_id')}")
                        print(f"   💸 L'argent ira directement au coach ({coach_connect_account_id})")
                        
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
                        print(f"❌ Erreur Stripe: {stripe_error}")
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
                
                print(f"✅ Réservation {booking_id} sauvegardée pour coach {coach_email}")
                
                # Envoyer notification au coach
                coach_notification = send_coach_notification_email(
                    to_email=coach_email,
                    coach_name=coach_data.get("full_name", "Coach"),
                    client_name=request.client_name,
                    client_email=request.client_email,
                    gym_name=request.gym_name,
                    gym_address=request.gym_address or "",
                    date_str=date_fr,
                    time_str=request.time,
                    service_name=request.service,
                    duration=f"{request.duration} min",
                    price=f"{request.price}€",
                    booking_id=booking_id
                )
                print(f"📧 Notification coach: {coach_notification}")
                
                print(f"📋 Réservation en attente de confirmation du coach")
                
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
            print(f"⚠️ Erreur sauvegarde réservation: {save_error}")
            return JSONResponse({
                "success": False,
                "message": "Erreur lors de la sauvegarde de la réservation",
                "error": str(save_error)
            }, status_code=500)
            
    except Exception as e:
        print(f"❌ Erreur confirmation réservation: {e}")
        return JSONResponse({
            "success": False,
            "message": "Erreur lors de la réservation",
            "email_sent": False,
            "error": str(e)
        })


@app.post("/api/cancel-booking")
async def cancel_booking(request: CancelBookingRequest):
    """Annule une réservation et envoie l'email d'annulation au client ET au coach."""
    try:
        from resend_service import send_cancellation_email, send_cancellation_to_coach_email
        
        print(f"📧 Annulation réservation pour {request.client_name} ({request.client_email})")
        print(f"   Coach: {request.coach_name}, Salle: {request.gym_name}")
        print(f"   Date: {request.date} à {request.time}")
        
        # Supprimer la réservation du serveur (demo_users.json)
        demo_users = load_demo_users()
        booking_removed = False
        found_coach_email = None
        found_coach_name = None
        
        # Chercher le coach par email ou nom
        for coach_email, coach_data in demo_users.items():
            if coach_data.get("role") != "coach":
                continue
            
            # Vérifier si c'est le bon coach
            coach_name = coach_data.get("full_name", "").lower().strip()
            if request.coach_email and coach_email.lower() == request.coach_email.lower():
                pass  # Match par email
            elif request.coach_name and coach_name == request.coach_name.lower().strip():
                pass  # Match par nom
            else:
                continue
            
            # Sauvegarder l'email du coach pour la notification
            found_coach_email = coach_email
            found_coach_name = coach_data.get("full_name", request.coach_name)
            
            # Supprimer des pending_bookings
            pending = coach_data.get("pending_bookings", [])
            new_pending = [b for b in pending if not (
                b.get("client_email", "").lower() == request.client_email.lower() and
                b.get("time") == request.time
            )]
            if len(new_pending) < len(pending):
                coach_data["pending_bookings"] = new_pending
                booking_removed = True
                print(f"✅ Réservation supprimée des pending_bookings du coach {coach_email}")
            
            # Supprimer des confirmed_bookings
            confirmed = coach_data.get("confirmed_bookings", [])
            new_confirmed = [b for b in confirmed if not (
                b.get("client_email", "").lower() == request.client_email.lower() and
                b.get("time") == request.time
            )]
            if len(new_confirmed) < len(confirmed):
                coach_data["confirmed_bookings"] = new_confirmed
                booking_removed = True
                print(f"✅ Réservation supprimée des confirmed_bookings du coach {coach_email}")
            
            if booking_removed:
                break
        
        # Sauvegarder les modifications
        if booking_removed:
            save_demo_users(demo_users)
            print(f"✅ Fichier demo_users.json mis à jour")
        
        # Envoyer l'email d'annulation AU COACH
        coach_notified = False
        if found_coach_email:
            coach_result = send_cancellation_to_coach_email(
                to_email=found_coach_email,
                coach_name=found_coach_name or request.coach_name,
                client_name=request.client_name,
                client_email=request.client_email,
                gym_name=request.gym_name,
                gym_address=request.gym_address or "Adresse non renseignée",
                date_str=request.date,
                time_str=request.time,
                service_name=request.service,
                duration=request.duration,
                price=request.price
            )
            coach_notified = coach_result.get("success", False)
            if coach_notified:
                print(f"✅ Email d'annulation envoyé au coach {found_coach_email}")
            else:
                print(f"⚠️ Erreur envoi email au coach: {coach_result.get('error')}")
        
        # Envoyer l'email d'annulation AU CLIENT
        result = send_cancellation_email(
            to_email=request.client_email,
            client_name=request.client_name,
            coach_name=request.coach_name,
            gym_name=request.gym_name,
            gym_address=request.gym_address or "Adresse non renseignée",
            date_str=request.date,
            time_str=request.time,
            service_name=request.service,
            duration=request.duration,
            price=request.price,
            coach_photo=request.coach_photo,
            booking_url=request.booking_url
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
            print(f"⚠️ Email client non envoyé mais réservation annulée: {result.get('error')}")
            return JSONResponse({
                "success": True,
                "message": "Réservation annulée (email client non envoyé)",
                "email_sent": False,
                "coach_notified": coach_notified,
                "booking_removed": booking_removed,
                "error": result.get("error")
            })
            
    except Exception as e:
        print(f"❌ Erreur annulation réservation: {e}")
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
async def get_coach_bookings(coach_email: str):
    """Récupère les réservations en attente et confirmées d'un coach."""
    try:
        demo_users = load_demo_users()
        
        if coach_email not in demo_users:
            return JSONResponse({"success": False, "error": "Coach non trouvé"}, status_code=404)
        
        coach_data = demo_users[coach_email]
        
        pending_bookings = coach_data.get("pending_bookings", [])
        confirmed_bookings = coach_data.get("confirmed_bookings", [])
        rejected_bookings = coach_data.get("rejected_bookings", [])
        
        return JSONResponse({
            "success": True,
            "pending": pending_bookings,
            "confirmed": confirmed_bookings,
            "rejected": rejected_bookings
        })
        
    except Exception as e:
        print(f"❌ Erreur récupération réservations coach: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/booking/{booking_id}")
async def get_booking_by_id(booking_id: str):
    """Récupère les détails d'un booking par son ID."""
    try:
        demo_users = load_demo_users()
        
        # Parcourir tous les coachs pour trouver le booking
        for coach_email, coach_data in demo_users.items():
            if coach_data.get("role") != "coach":
                continue
            
            # Chercher dans pending, confirmed et rejected
            for booking_list in ["pending_bookings", "confirmed_bookings", "rejected_bookings"]:
                bookings = coach_data.get(booking_list, [])
                for booking in bookings:
                    if booking.get("id") == booking_id:
                        # Ajouter l'email du coach au booking
                        booking_with_coach = booking.copy()
                        booking_with_coach["coach_email"] = coach_email
                        booking_with_coach["coach_name"] = coach_data.get("full_name", "Coach")
                        return JSONResponse({
                            "success": True,
                            "booking": booking_with_coach
                        })
        
        return JSONResponse({
            "success": False,
            "error": "Booking non trouvé"
        }, status_code=404)
        
    except Exception as e:
        print(f"❌ Erreur récupération booking: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/client/bookings")
async def get_client_bookings(client_email: str):
    """Récupère toutes les réservations d'un client depuis tous les coachs."""
    try:
        demo_users = load_demo_users()
        client_bookings = []
        
        # Parcourir tous les coachs pour trouver les réservations du client
        for coach_email, coach_data in demo_users.items():
            if coach_data.get("role") != "coach":
                continue
            
            coach_name = coach_data.get("full_name", "Coach")
            
            # Chercher dans pending et confirmed (pas rejected car annulées)
            for booking_list in ["pending_bookings", "confirmed_bookings"]:
                bookings = coach_data.get(booking_list, [])
                for booking in bookings:
                    if booking.get("client_email", "").lower() == client_email.lower():
                        booking_with_coach = booking.copy()
                        booking_with_coach["coach_email"] = coach_email
                        booking_with_coach["coach_name"] = coach_name
                        client_bookings.append(booking_with_coach)
        
        return JSONResponse({
            "success": True,
            "bookings": client_bookings
        })
        
    except Exception as e:
        print(f"❌ Erreur récupération bookings client: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.post("/api/coach/bookings/respond")
async def respond_to_booking(request: CoachBookingRequest):
    """Le coach confirme ou refuse une réservation."""
    try:
        import json
        demo_users = load_demo_users()
        
        if request.coach_email not in demo_users:
            return JSONResponse({"success": False, "error": "Coach non trouvé"}, status_code=404)
        
        coach_data = demo_users[request.coach_email]
        pending_bookings = coach_data.get("pending_bookings", [])
        
        # Trouver la réservation
        booking_to_update = None
        booking_index = -1
        for i, booking in enumerate(pending_bookings):
            if booking.get("id") == request.booking_id:
                booking_to_update = booking
                booking_index = i
                break
        
        if not booking_to_update:
            return JSONResponse({"success": False, "error": "Réservation non trouvée"}, status_code=404)
        
        # Retirer de pending
        pending_bookings.pop(booking_index)
        
        # Ajouter à la bonne liste selon l'action
        if request.action == "confirm":
            booking_to_update["status"] = "confirmed"
            booking_to_update["confirmed_at"] = datetime.now().isoformat()
            if "confirmed_bookings" not in coach_data:
                coach_data["confirmed_bookings"] = []
            coach_data["confirmed_bookings"].append(booking_to_update)
            action_label = "confirmée"
        elif request.action == "reject":
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
        save_demo_user(request.coach_email, coach_data)
        
        print(f"✅ Réservation {request.booking_id} {action_label} par {request.coach_email}")
        
        # Envoyer email au client pour l'informer
        email_sent = False
        email_error_msg = None
        
        # Vérifier que les données client sont présentes
        client_email = booking_to_update.get("client_email")
        client_name = booking_to_update.get("client_name", "Client")
        
        if not client_email:
            print(f"⚠️ Email client manquant pour la réservation {request.booking_id}")
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
            except:
                date_fr = booking_to_update.get("date", "Date non spécifiée")
            
            coach_name = coach_data.get("full_name", "Coach")
            
            if request.action == "confirm":
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
                        reservation_id=request.booking_id
                    )
                    email_sent = email_result.get("success", False)
                    if not email_sent:
                        email_error_msg = email_result.get("error", "Erreur inconnue")
                    print(f"📧 Email confirmation client: {email_result}")
                    
                    # Programmer les rappels (24h avant + 2h avant)
                    schedule_booking_reminders(booking_to_update, coach_name)
                    
                except Exception as email_error:
                    email_error_msg = str(email_error)
                    print(f"⚠️ Erreur envoi email confirmation: {email_error}")
            
            elif request.action == "reject":
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
                        price=f"{booking_to_update.get('price', '40')}€"
                    )
                    email_sent = email_result.get("success", False)
                    if not email_sent:
                        email_error_msg = email_result.get("error", "Erreur inconnue")
                    print(f"📧 Email rejet client: {email_result}")
                except Exception as email_error:
                    email_error_msg = str(email_error)
                    print(f"⚠️ Erreur envoi email rejet: {email_error}")
        
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
        print(f"❌ Erreur réponse réservation: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


class DeleteBookingRequest(BaseModel):
    coach_email: str
    booking_id: str

@app.post("/api/coach/bookings/delete")
async def delete_booking(request: DeleteBookingRequest):
    """Le coach supprime une réservation (pending ou confirmed)."""
    try:
        import json
        demo_users = load_demo_users()
        
        if request.coach_email not in demo_users:
            return JSONResponse({"success": False, "error": "Coach non trouvé"}, status_code=404)
        
        coach_data = demo_users[request.coach_email]
        booking_found = False
        deleted_booking = None
        was_confirmed = False
        
        # Chercher dans pending_bookings
        pending_bookings = coach_data.get("pending_bookings", [])
        for i, booking in enumerate(pending_bookings):
            if booking.get("id") == request.booking_id:
                deleted_booking = pending_bookings.pop(i)
                coach_data["pending_bookings"] = pending_bookings
                booking_found = True
                was_confirmed = False
                break
        
        # Chercher dans confirmed_bookings si pas trouvé
        if not booking_found:
            confirmed_bookings = coach_data.get("confirmed_bookings", [])
            for i, booking in enumerate(confirmed_bookings):
                if booking.get("id") == request.booking_id:
                    deleted_booking = confirmed_bookings.pop(i)
                    coach_data["confirmed_bookings"] = confirmed_bookings
                    booking_found = True
                    was_confirmed = True
                    break
        
        if not booking_found:
            return JSONResponse({"success": False, "error": "Réservation non trouvée"}, status_code=404)
        
        # Sauvegarder
        with open("demo_users.json", "w", encoding="utf-8") as f:
            json.dump(demo_users, f, ensure_ascii=False, indent=2)
        
        print(f"🗑️ Réservation {request.booking_id} supprimée par {request.coach_email}")
        
        # Annuler les rappels programmés pour cette réservation
        cancel_booking_reminders(request.booking_id)
        
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
                        except:
                            pass
                    
                    print(f"📧 Envoi email annulation au client {client_name} ({client_email})")
                    print(f"   Coach: {coach_name}, Date: {formatted_date} à {time_str}")
                    
                    email_result = send_coach_cancelled_email(
                        client_email=client_email,
                        client_name=client_name,
                        coach_name=coach_name,
                        gym_name=gym_name,
                        date=f"{formatted_date} à {time_str}"
                    )
                    email_sent = email_result.get("success", False)
                    print(f"📧 Email annulation client: {email_result}")
                except Exception as email_error:
                    print(f"⚠️ Erreur envoi email annulation: {email_error}")
        
        return JSONResponse({
            "success": True,
            "message": "Séance supprimée",
            "email_sent": email_sent
        })
        
    except Exception as e:
        print(f"❌ Erreur suppression réservation: {e}")
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
    client_email: str
    coach_email: str
    sender_role: str  # "client" ou "coach"
    sender_name: str
    message: str

@app.post("/api/messages/send")
async def send_message(request: SendMessageRequest):
    """Envoie un message dans une conversation."""
    try:
        messages = load_messages()
        conv_id = get_conversation_id(request.client_email, request.coach_email, request.booking_id)
        
        if conv_id not in messages:
            messages[conv_id] = {
                "booking_id": request.booking_id,
                "client_email": request.client_email,
                "coach_email": request.coach_email,
                "messages": []
            }
        
        new_message = {
            "id": str(uuid.uuid4())[:8],
            "sender_role": request.sender_role,
            "sender_name": request.sender_name,
            "message": request.message,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        
        messages[conv_id]["messages"].append(new_message)
        save_messages(messages)
        
        return JSONResponse({
            "success": True,
            "message": new_message
        })
    except Exception as e:
        print(f"❌ Erreur envoi message: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/messages/{booking_id}")
async def get_messages(booking_id: str, client_email: str = None, coach_email: str = None):
    """Récupère les messages d'une conversation."""
    try:
        messages = load_messages()
        
        # Chercher la conversation
        for conv_id, conv in messages.items():
            if conv.get("booking_id") == booking_id:
                if client_email and conv.get("client_email") != client_email:
                    continue
                if coach_email and conv.get("coach_email") != coach_email:
                    continue
                return JSONResponse({
                    "success": True,
                    "conversation": conv
                })
        
        return JSONResponse({
            "success": True,
            "conversation": {"messages": []}
        })
    except Exception as e:
        print(f"❌ Erreur récupération messages: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/conversations")
async def get_conversations(email: str, role: str):
    """Récupère toutes les conversations d'un utilisateur."""
    try:
        messages = load_messages()
        user_conversations = []
        
        for conv_id, conv in messages.items():
            if role == "client" and conv.get("client_email") == email:
                user_conversations.append(conv)
            elif role == "coach" and conv.get("coach_email") == email:
                user_conversations.append(conv)
        
        return JSONResponse({
            "success": True,
            "conversations": user_conversations
        })
    except Exception as e:
        print(f"❌ Erreur récupération conversations: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/messages/mark-read")
async def mark_messages_read(booking_id: str, reader_role: str):
    """Marque les messages d'une conversation comme lus."""
    try:
        messages = load_messages()
        
        for conv_id, conv in messages.items():
            if conv.get("booking_id") == booking_id:
                for msg in conv.get("messages", []):
                    if msg.get("sender_role") != reader_role:
                        msg["read"] = True
                save_messages(messages)
                break
        
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/conversation/{booking_id}", response_class=HTMLResponse)
async def conversation_page(request: Request, booking_id: str):
    """Page de conversation pour client ou coach."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("conversation.html", {
        "request": request,
        "booking_id": booking_id
    })


# ============================================
# SYSTÈME DE RAPPELS - ENDPOINTS & BACKGROUND TASK
# ============================================

@app.get("/api/reminders/process")
async def api_process_reminders():
    """
    Endpoint pour déclencher manuellement le traitement des rappels.
    Peut être appelé par un cron job externe ou manuellement.
    """
    try:
        sent_count = process_due_reminders()
        return JSONResponse({
            "success": True,
            "reminders_sent": sent_count,
            "message": f"{sent_count} rappel(s) envoyé(s)"
        })
    except Exception as e:
        print(f"❌ Erreur API process reminders: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

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

def reminder_checker_thread():
    """Thread qui vérifie les rappels toutes les 5 minutes."""
    print("🔔 Démarrage du thread de vérification des rappels...")
    while True:
        try:
            sent = process_due_reminders()
            if sent > 0:
                print(f"🔔 {sent} rappel(s) envoyé(s) automatiquement")
        except Exception as e:
            print(f"⚠️ Erreur thread rappels: {e}")
        
        # Attendre 5 minutes avant la prochaine vérification
        time.sleep(300)

# Démarrer le thread de vérification au lancement de l'application
reminder_thread = threading.Thread(target=reminder_checker_thread, daemon=True)
reminder_thread.start()

# ============================================

# ============================================
# STRIPE - ABONNEMENTS COACHS (API Endpoints)
# ============================================

@app.post("/api/stripe/create-checkout-session")
async def api_create_checkout_session(request: Request, user = Depends(require_coach_or_pending)):
    """Crée une session Checkout Stripe pour l'abonnement (accessible même sans abonnement actif)."""
    try:
        coach_email = user.get("email")
        coach_name = user.get("full_name", user.get("name", "Coach"))
        coach_id = user.get("id", coach_email)
        
        # Créer ou récupérer le customer Stripe
        customer = create_or_get_customer(coach_email, coach_name, coach_id)
        
        # Sauvegarder le customer_id
        update_coach_subscription(coach_email, stripe_customer_id=customer.id)
        
        # Construire les URLs de retour avec session_id pour vérification
        base_url = str(request.base_url).rstrip("/")
        success_url = f"{base_url}/coach/subscription?success=true&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/coach/subscription?cancelled=true"
        
        # Créer la session checkout
        session = create_checkout_session(
            customer_id=customer.id,
            success_url=success_url,
            cancel_url=cancel_url,
            coach_email=coach_email
        )
        
        return JSONResponse({"url": session.url})
    except Exception as e:
        print(f"❌ Erreur création checkout session: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/stripe/create-portal-session")
async def api_create_portal_session(request: Request, user = Depends(require_coach_role)):
    """Crée une session du portail de facturation Stripe."""
    try:
        coach_email = user.get("email")
        subscription_info = get_coach_subscription_info(coach_email)
        
        if not subscription_info or not subscription_info.get("stripe_customer_id"):
            return JSONResponse({"error": "Aucun abonnement trouvé"}, status_code=404)
        
        base_url = str(request.base_url).rstrip("/")
        return_url = f"{base_url}/coach/subscription"
        
        session = create_portal_session(
            customer_id=subscription_info["stripe_customer_id"],
            return_url=return_url
        )
        
        return JSONResponse({"url": session.url})
    except Exception as e:
        print(f"❌ Erreur création portal session: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """
    Webhook Stripe pour gérer les événements d'abonnement.
    Met à jour le statut des abonnements des coachs.
    """
    import stripe
    from stripe_service import init_stripe
    
    init_stripe()
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = json.loads(payload)
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        print(f"📩 Webhook Stripe reçu: {event_type}")
        
        if event_type == "checkout.session.completed":
            metadata = data.get("metadata", {})
            booking_type = metadata.get("booking_type")
            
            # PAIEMENT DE SÉANCE (mode paiement obligatoire)
            if booking_type == "session_payment":
                booking_id = metadata.get("booking_id")
                coach_email = metadata.get("coach_email")
                client_email = metadata.get("client_email")
                
                print(f"💳 Paiement séance réussi - booking_id: {booking_id}, coach: {coach_email}")
                
                if coach_email and booking_id:
                    try:
                        from resend_service import send_booking_confirmation_email
                        
                        demo_users = load_demo_users()
                        if coach_email in demo_users:
                            coach_data = demo_users[coach_email]
                            pending = coach_data.get("pending_bookings", [])
                            
                            # Trouver et déplacer la réservation vers confirmed_bookings
                            booking_to_confirm = None
                            for i, booking in enumerate(pending):
                                if booking.get("id") == booking_id:
                                    booking_to_confirm = pending.pop(i)
                                    break
                            
                            if booking_to_confirm:
                                booking_to_confirm["status"] = "confirmed"
                                booking_to_confirm["payment_status"] = "paid"
                                booking_to_confirm["confirmed_at"] = datetime.now().isoformat()
                                
                                if "confirmed_bookings" not in coach_data:
                                    coach_data["confirmed_bookings"] = []
                                coach_data["confirmed_bookings"].append(booking_to_confirm)
                                coach_data["pending_bookings"] = pending
                                
                                save_demo_user(coach_email, coach_data)
                                print(f"✅ Réservation {booking_id} confirmée après paiement")
                                
                                # Programmer les rappels
                                schedule_booking_reminders(booking_to_confirm, coach_data.get("full_name", "Coach"))
                                
                                # Envoyer emails de confirmation
                                try:
                                    from datetime import datetime as dt
                                    date_obj = dt.strptime(booking_to_confirm.get("date"), "%Y-%m-%d")
                                    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
                                    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
                                    date_fr = f"{jours[date_obj.weekday()]} {date_obj.day} {mois[date_obj.month - 1]} {date_obj.year}"
                                    
                                    send_booking_confirmation_email(
                                        to_email=booking_to_confirm.get("client_email"),
                                        client_name=booking_to_confirm.get("client_name"),
                                        coach_name=coach_data.get("full_name", "Coach"),
                                        gym_name=booking_to_confirm.get("gym_name"),
                                        gym_address=booking_to_confirm.get("gym_address", ""),
                                        date_str=date_fr,
                                        time_str=booking_to_confirm.get("time"),
                                        service_name=booking_to_confirm.get("service"),
                                        duration=f"{booking_to_confirm.get('duration')} min",
                                        price=f"{booking_to_confirm.get('price')}€",
                                        booking_id=booking_id
                                    )
                                    print(f"📧 Email confirmation envoyé au client")
                                except Exception as email_error:
                                    print(f"⚠️ Erreur email confirmation: {email_error}")
                    except Exception as booking_error:
                        print(f"❌ Erreur confirmation réservation après paiement: {booking_error}")
                
                return JSONResponse({"received": True})
            
            # PAIEMENT ABONNEMENT COACH (flux existant)
            coach_email = data.get("metadata", {}).get("coach_email")
            subscription_id = data.get("subscription")
            customer_id = data.get("customer")
            
            print(f"📩 checkout.session.completed - coach_email: {coach_email}, subscription_id: {subscription_id}")
            
            if coach_email and subscription_id:
                try:
                    # Récupérer les infos de l'abonnement
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    period_end = datetime.fromtimestamp(subscription.current_period_end).isoformat()
                    
                    update_coach_subscription(
                        coach_email=coach_email,
                        stripe_customer_id=customer_id,
                        stripe_subscription_id=subscription_id,
                        subscription_status="active",
                        current_period_end=period_end
                    )
                    print(f"✅ Abonnement activé pour {coach_email}")
                except Exception as sub_error:
                    print(f"❌ Erreur récupération subscription: {sub_error}")
            elif coach_email:
                # Si pas de subscription_id mais coach_email, activer quand même
                update_coach_subscription(
                    coach_email=coach_email,
                    stripe_customer_id=customer_id,
                    subscription_status="active"
                )
                print(f"✅ Abonnement activé (sans sub ID) pour {coach_email}")
        
        elif event_type == "customer.subscription.updated":
            # Mise à jour de l'abonnement
            subscription_id = data.get("id")
            status = data.get("status")
            coach_email = data.get("metadata", {}).get("coach_email")
            
            if coach_email:
                period_end = datetime.fromtimestamp(data.get("current_period_end", 0)).isoformat()
                update_coach_subscription(
                    coach_email=coach_email,
                    subscription_status=status,
                    current_period_end=period_end
                )
                print(f"🔄 Abonnement mis à jour pour {coach_email}: {status}")
        
        elif event_type == "customer.subscription.deleted":
            # Abonnement annulé
            coach_email = data.get("metadata", {}).get("coach_email")
            
            if coach_email:
                update_coach_subscription(
                    coach_email=coach_email,
                    subscription_status="cancelled"
                )
                print(f"🚫 Abonnement annulé pour {coach_email}")
        
        elif event_type == "invoice.payment_failed":
            # Paiement échoué
            subscription_id = data.get("subscription")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                coach_email = subscription.metadata.get("coach_email")
                
                if coach_email:
                    update_coach_subscription(
                        coach_email=coach_email,
                        subscription_status="past_due"
                    )
                    print(f"⚠️ Paiement échoué pour {coach_email}")
        
        elif event_type == "account.updated":
            # Mise à jour du compte Stripe Connect d'un coach
            account_id = data.get("id")
            account_email = data.get("email")
            details_submitted = data.get("details_submitted", False)
            charges_enabled = data.get("charges_enabled", False)
            payouts_enabled = data.get("payouts_enabled", False)
            
            print(f"🔄 Compte Connect mis à jour: {account_id}")
            print(f"   Email: {account_email}, Charges: {charges_enabled}, Payouts: {payouts_enabled}")
            
            from db_service import update_stripe_connect_status, find_coach_by_stripe_connect_account
            
            try:
                # Chercher le coach par account_id dans la base de données PostgreSQL
                coach_found = find_coach_by_stripe_connect_account(account_id)
                
                if coach_found:
                    # Déterminer le statut
                    if charges_enabled and payouts_enabled:
                        status = "active"
                    elif details_submitted:
                        status = "pending"
                    else:
                        status = "incomplete"
                    
                    update_stripe_connect_status(
                        email=coach_found,
                        account_id=account_id,
                        status=status,
                        charges_enabled=charges_enabled,
                        payouts_enabled=payouts_enabled,
                        details_submitted=details_submitted
                    )
                    print(f"✅ Statut Stripe Connect synchronisé pour {coach_found}: {status}")
                else:
                    print(f"⚠️ Coach non trouvé pour account_id: {account_id}")
                    
            except Exception as connect_error:
                print(f"❌ Erreur synchronisation compte Connect: {connect_error}")
        
        return JSONResponse({"received": True})
    
    except Exception as e:
        print(f"❌ Erreur webhook Stripe: {e}")
        return JSONResponse({"error": str(e)}, status_code=400)

@app.get("/api/coach/subscription-status")
async def api_coach_subscription_status(request: Request, user = Depends(require_coach_role)):
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
    return templates.TemplateResponse("booking_success.html", {
        "request": request,
        "booking_id": booking_id,
        "session_id": session_id
    })

@app.get("/booking-cancelled", response_class=HTMLResponse)
async def booking_cancelled_page(request: Request, booking_id: str = None):
    """Page affichée si le paiement est annulé."""
    locale = get_locale_from_request(request)
    translations = get_translations(locale)
    return templates.TemplateResponse("booking_cancelled.html", {
        "request": request,
        "booking_id": booking_id
    })

# ============================================


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)