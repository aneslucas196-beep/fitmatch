from fastapi import FastAPI, Request, Form, HTTPException, Depends, File, UploadFile, Cookie, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
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
    search_gyms_by_zone,
    get_coaches_by_gym,
    # Géolocalisation et pays
    get_countries_list,
    get_country_name
)

from resend_service import send_otp_email_resend
from supabase_auth_service import signup_with_supabase_email_confirmation, resend_email_confirmation, sign_in_with_email_password, get_user_role

app = FastAPI()

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

# Client Supabase anonyme (si disponible)
supabase_anon = get_supabase_anon_client()

# Cache en mémoire pour les codes OTP en mode démo (email -> code)
demo_otp_cache = {}
demo_user_cache = {}

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
    {"id": "neoness_defense", "name": "Neoness La Défense", "chain": "Neoness", "lat": 48.8922, "lng": 2.2359, "address": "CNIT, 92800 Puteaux", "city": "Puteaux"},
    {"id": "cmg_neuilly", "name": "CMG Sports Club One Neuilly", "chain": "CMG Sports Club", "lat": 48.8846, "lng": 2.2686, "address": "12 rue Madeleine Michelis, 92200 Neuilly-sur-Seine", "city": "Neuilly-sur-Seine"},
    {"id": "fitness_park_boulogne", "name": "Fitness Park Boulogne", "chain": "Fitness Park", "lat": 48.8392, "lng": 2.2402, "address": "133 route de la Reine, 92100 Boulogne-Billancourt", "city": "Boulogne-Billancourt"},
    {"id": "keep_cool_issy", "name": "Keep Cool Issy-les-Moulineaux", "chain": "Keep Cool", "lat": 48.8267, "lng": 2.2725, "address": "2 rue Rouget de Lisle, 92130 Issy-les-Moulineaux", "city": "Issy-les-Moulineaux"},

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
            from utils import load_demo_users
            import hashlib
            
            # Charger tous les utilisateurs démo
            all_demo_users = load_demo_users()
            
            # Trouver l'utilisateur correspondant à ce token
            for email, user_data in all_demo_users.items():
                expected_token = f"demo_{hashlib.md5(email.encode()).hexdigest()[:16]}"
                if session_token == expected_token:
                    # Utilisateur trouvé
                    user_data["_access_token"] = session_token
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

# Routes publiques
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Page d'accueil avec formulaire de recherche."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/search", response_class=HTMLResponse)
async def search_coaches(
    request: Request,
    specialty: Optional[str] = None,
    city: str = "",
    radius_km: int = 25
):
    """Recherche de coachs avec géolocalisation."""
    
    # Géocoder la ville
    coords = geocode_city(city) if city else None
    user_lat, user_lng = coords if coords else (None, None)
    
    # Rechercher les coachs
    if supabase_anon:
        coaches = search_coaches_supabase(supabase_anon, specialty, user_lat, user_lng, radius_km)
    else:
        coaches = search_coaches_mock(specialty, user_lat, user_lng, radius_km)
    
    return templates.TemplateResponse("results.html", {
        "request": request,
        "coaches": coaches,
        "specialty": specialty,
        "city": city,
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
    
    return templates.TemplateResponse("client_home.html", {
        "request": request, 
        "user": user
    })

@app.get("/gyms/search", response_class=HTMLResponse)
async def gym_search_page(request: Request):
    """Page de recherche de salles de sport avec géolocalisation."""
    return templates.TemplateResponse("gym_search.html", {"request": request})

@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request, role: str | None = None):
    """Formulaire d'inscription."""
    countries = get_countries_list()
    return templates.TemplateResponse("signup.html", {
        "request": request, 
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
        # Mode démo - générer un nouveau code et le stocker
        new_otp_code = generate_otp_code(6)
        demo_otp_cache[email] = new_otp_code
        print(f"🔐 Mode démo - Nouveau code OTP pour {email}: {new_otp_code}")
        return templates.TemplateResponse("verify_otp.html", {
            "request": request,
            "email": email,
            "demo_code": new_otp_code,
            "success": "Nouveau code généré en mode démo"
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

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, message: Optional[str] = None):
    """Formulaire de connexion."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "message": message
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

# Routes protégées - Espace Coach
@app.get("/coach/portal", response_class=HTMLResponse)
async def coach_portal(request: Request, user = Depends(require_coach_role)):
    """Dashboard coach - avec vérification du profil complété."""
    
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
    user = Depends(require_coach_role)
):
    """Traitement du formulaire d'onboarding coach."""
    
    user_supabase = get_supabase_client_for_user(user.get("_access_token"))
    error_message = None
    success_message = None
    
    try:
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
            print(f"   - Salles: {selected_gym_ids}")
            
            # Mettre à jour l'utilisateur et sauvegarder dans le stockage persistant
            from utils import save_demo_user
            updated_user = {
                "id": user.get("id", user.get("email", "demo_user")),  # Utiliser email comme ID si pas d'ID
                "email": user["email"],
                "role": user["role"],
                "profile_completed": True,
                "full_name": full_name,
                "bio": bio,
                "city": city,
                "instagram_url": instagram_url,
                "price_from": price_from,
                "radius_km": radius_km
            }
            
            # Sauvegarder les modifications dans le stockage persistant
            save_demo_user(user["email"], updated_user)
            print(f"✅ Données utilisateur démo sauvegardées avec profile_completed=True")
            
            # Redirection vers le dashboard après succès
            return RedirectResponse(url="/coach/portal", status_code=303)
            
    except Exception as e:
        print(f"❌ Erreur lors de la soumission du profil: {e}")
        error_message = "Une erreur s'est produite lors de la sauvegarde."
    
    # En cas d'erreur, recharger la page avec le message d'erreur
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

# Route pour profil de coach - définie APRÈS /coach/portal pour éviter les conflits
@app.get("/coach/{coach_id}", response_class=HTMLResponse)
async def coach_profile(request: Request, coach_id: str):
    """Affichage du profil d'un coach."""
    
    # Récupérer le coach
    if supabase_anon:
        coach = get_coach_by_id_supabase(supabase_anon, coach_id)
        transformations = get_transformations_by_coach_supabase(supabase_anon, coach_id)
    else:
        # Convertir en int pour les données mock si nécessaire
        try:
            coach_id_int = int(coach_id)
            coach = get_coach_by_id_mock(coach_id_int)
            transformations = get_transformations_by_coach_mock(coach_id_int)
        except ValueError:
            coach = None
            transformations = []
    
    if not coach:
        raise HTTPException(status_code=404, detail="Coach non trouvé")
    
    return templates.TemplateResponse("coach.html", {
        "request": request,
        "coach": coach,
        "transformations": transformations
    })

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

@app.get("/api/gyms/search")
async def search_gyms_by_location_api(
    q: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: int = 25
):
    """
    Recherche de salles par localisation ou nom.
    Paramètres: q (nom/adresse) OU lat,lng + radius_km
    """
    try:
        results = []
        
        if q:
            # 🎯 NOUVEAU: Détection automatique des recherches par zone/arrondissement
            zone_results = search_gyms_by_zone(q)
            if zone_results:
                # Recherche par zone réussie - afficher TOUTES les salles de cette zone
                results = zone_results
            else:
                # Recherche classique par géocodage + rayon
                geocoded = geocode_address(q)
                if geocoded:
                    results = search_gyms_by_location(
                        geocoded["lat"], 
                        geocoded["lng"], 
                        radius_km
                    )
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
            results = search_gyms_by_location(lat, lng, radius_km)
        
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

@app.get("/api/gyms/suggestions")
async def get_gym_suggestions(q: str):
    """
    NOUVEAU ENDPOINT COACH : Recherche TOUTES les salles de France pour l'autocomplétion coach.
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
    Fonctionne avec gym_id statiques (GYMS_DATABASE) et dynamiques (coach_gym_X).
    """
    try:
        print(f"🔍 Recherche coaches pour gym_id: {gym_id}")
        
        # Utiliser directement le nouveau système unifié basé sur gym_id
        coaches = get_coaches_by_gym(gym_id)
        
        # Récupérer les infos de la gym si disponible (optionnel)
        gym_info = None
        gym = next((g for g in GYMS_DATABASE if g["id"] == gym_id), None)
        if gym:
            gym_info = gym
        
        print(f"📊 Résultat pour {gym_id}: {len(coaches)} coaches trouvés")
        
        return {
            "success": True,
            "coaches": coaches,
            "count": len(coaches),
            "gym_id": gym_id,
            "gym_info": gym_info  # Infos de la gym si statique, sinon None
        }
        
    except Exception as e:
        print(f"❌ Erreur récupération coachs pour gym_id '{gym_id}': {e}")
        return {
            "success": False,
            "message": "Erreur lors de la récupération des coachs",
            "coaches": [],
            "gym_id": gym_id
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

# Route pour les images uploadées (si pas d'utilisation directe de Supabase Storage)
@app.get("/images/{image_path:path}")
async def serve_image(image_path: str):
    """Servir les images uploadées."""
    # Cette route peut être utilisée pour servir des images locales
    # En production, préférer utiliser directement Supabase Storage
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)