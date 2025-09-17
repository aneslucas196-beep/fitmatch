import os
import math
import random
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Géocodeur global
geolocator = Nominatim(user_agent="coach_fitness_app")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcule la distance Haversine entre deux points géographiques en kilomètres.
    """
    # Rayon de la Terre en kilomètres
    R = 6371.0
    
    # Conversion en radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Différences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Formule Haversine
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    """
    Géocode une ville ou un code postal français.
    Retourne (latitude, longitude) ou None si échec.
    """
    try:
        # Ajouter "France" pour améliorer la précision
        location = geolocator.geocode(f"{city}, France")
        if location:
            lat = getattr(location, 'latitude', None)
            lng = getattr(location, 'longitude', None)
            if lat is not None and lng is not None:
                return (float(lat), float(lng))
        return None
    except (GeocoderTimedOut, GeocoderServiceError, Exception):
        return None

# Données mock pour les tests
MOCK_COACHES = [
    {
        "id": 1,
        "role": "coach",
        "full_name": "Marie Dubois",
        "city": "Élancourt",
        "lat": 48.7863,
        "lng": 2.0592,
        "instagram_url": "https://instagram.com/marie_fit",
        "bio": "Coach diplômée avec 8 ans d'expérience. Spécialisée dans la transformation physique et le coaching nutritionnel. Passionnée par l'accompagnement personnalisé.",
        "radius_km": 25,
        "price_from": 60,
        "specialties": ["musculation", "nutrition", "cardio"]
    },
    {
        "id": 2,
        "role": "coach",
        "full_name": "Thomas Martin",
        "city": "Plaisir",
        "lat": 48.8244,
        "lng": 1.9486,
        "instagram_url": "https://instagram.com/thomas_crossfit",
        "bio": "Ancien athlète de haut niveau reconverti en coach CrossFit. Expert en préparation physique et développement de la force. Méthodes d'entraînement innovantes.",
        "radius_km": 30,
        "price_from": 75,
        "specialties": ["crossfit", "musculation", "cardio"]
    }
]

MOCK_TRANSFORMATIONS = [
    {
        "id": 1,
        "coach_id": 1,
        "title": "Transformation Marie - Client A",
        "description": "Perte de 15kg en 4 mois avec programme personnalisé",
        "duration_weeks": 16,
        "consent": True
    },
    {
        "id": 2,
        "coach_id": 1,
        "title": "Préparation compétition",
        "description": "Préparation physique pour compétition de fitness",
        "duration_weeks": 12,
        "consent": True
    },
    {
        "id": 3,
        "coach_id": 2,
        "title": "Challenge CrossFit",
        "description": "Initiation et progression en CrossFit",
        "duration_weeks": 8,
        "consent": True
    }
]

def get_supabase_anon_client():
    """
    Crée un client Supabase anonyme (respecte RLS).
    """
    try:
        from supabase import create_client, Client
        
        url = os.getenv("SUPABASE_URL")
        # Essayer SUPABASE_KEY d'abord, puis SUPABASE_ANON_KEY en fallback
        anon_key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        
        # Supabase désactivé temporairement - problème de configuration détecté
        print("🔧 Mode démo forcé - problème table otp_codes dans Supabase")
        return None
        
        if url and anon_key:
            # Valider l'URL
            if url.startswith("https://") and ".supabase.co" in url:
                return create_client(url, anon_key)
            else:
                print(f"⚠️ URL Supabase invalide: {url}")
                return None
        return None
    except Exception as e:
        print(f"⚠️ Erreur lors de l'initialisation Supabase: {e}")
        return None

def get_supabase_client_for_user(access_token: str):
    """
    Crée un client Supabase avec authentification utilisateur (respecte RLS).
    """
    from supabase import create_client
    import os
    
    # Validation des paramètres
    if not access_token or not isinstance(access_token, str) or len(access_token.strip()) == 0:
        print("❌ Token d'accès invalide ou manquant")
        return None
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ Configuration Supabase manquante (URL ou KEY)")
        return None
    
    # Validation de l'URL Supabase
    if not url.startswith("https://") or ".supabase.co" not in url:
        print(f"❌ URL Supabase invalide: {url}")
        return None
        
    try:
        # Créer un nouveau client avec le token utilisateur
        client = create_client(url, key)
        
        # Validation du token avant de l'utiliser
        if access_token and len(access_token) > 20:  # JWT minimal length check
            # Définir le token d'authentification pour respecter les politiques RLS
            client.postgrest.auth(access_token)
            print(f"✅ Client authentifié créé avec succès")
            return client
        else:
            print(f"❌ Format de token d'accès invalide")
            return None
    except Exception as e:
        print(f"❌ Erreur création client authentifié: {e}")
        return None

def search_coaches_mock(specialty: Optional[str] = None, 
                       user_lat: Optional[float] = None, 
                       user_lng: Optional[float] = None, 
                       radius_km: int = 50) -> List[Dict]:
    """
    Version mock de la recherche de coachs.
    """
    coaches = []
    
    for coach in MOCK_COACHES:
        # Filtrer par spécialité si spécifiée
        if specialty and specialty not in coach["specialties"]:
            continue
            
        # Calculer la distance si coordonnées fournies
        if user_lat is not None and user_lng is not None:
            distance = haversine_distance(user_lat, user_lng, coach["lat"], coach["lng"])
            if distance > radius_km:
                continue
            coach_copy = coach.copy()
            coach_copy["distance"] = distance
        else:
            coach_copy = coach.copy()
            coach_copy["distance"] = 0
            
        coaches.append(coach_copy)
    
    # Trier par distance
    coaches.sort(key=lambda x: x["distance"])
    return coaches

def get_coach_by_id_mock(coach_id: int) -> Optional[Dict]:
    """
    Version mock pour récupérer un coach par ID.
    """
    for coach in MOCK_COACHES:
        if coach["id"] == coach_id:
            return coach.copy()
    return None

def get_transformations_by_coach_mock(coach_id: int) -> List[Dict]:
    """
    Version mock pour récupérer les transformations d'un coach.
    """
    return [t for t in MOCK_TRANSFORMATIONS if t["coach_id"] == coach_id]

# Fonctions Supabase - Authentification
def create_user_profile_on_confirmation(supabase_client, user_id: str, email: str, full_name: str, role: str, gender: Optional[str] = None, coach_gender_preference: Optional[str] = None, selected_gyms: Optional[str] = None) -> bool:
    """Crée le profil utilisateur après confirmation d'email (appelé par webhook ou trigger)."""
    try:
        # Normaliser l'email
        normalized_email = email.lower().strip()
        
        # Créer le profil dans la table profiles
        profile_data = {
            "id": user_id,
            "role": role,
            "full_name": full_name,
            "email": normalized_email,
            "gender": gender,
            "coach_gender_preference": coach_gender_preference if role == "client" else None,
            "selected_gyms": selected_gyms if role == "client" else None
        }
        
        response = supabase_client.table("profiles").insert(profile_data).execute()
        if response.data:
            print(f"✅ Profil créé pour {normalized_email} avec le rôle {role}")
            return True
        else:
            print(f"❌ Échec création profil pour {normalized_email}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur création profil: {e}")
        return False

def sign_in_user(supabase_client, email: str, password: str) -> Optional[Dict]:
    """Connexion d'un utilisateur."""
    try:
        # Normaliser l'email en lowercase
        normalized_email = email.lower().strip()
        
        auth_response = supabase_client.auth.sign_in_with_password({
            "email": normalized_email,
            "password": password
        })
        
        if auth_response.user:
            return {"user": auth_response.user, "session": auth_response.session}
        return None
    except Exception as e:
        print(f"Erreur connexion: {e}")
        # Retourner l'erreur pour permettre la détection d'email non confirmé
        return {"error": str(e)}

def resend_confirmation_email(supabase_client, email: str) -> bool:
    """Renvoie l'email de confirmation pour un compte."""
    try:
        # Normaliser l'email en lowercase
        normalized_email = email.lower().strip()
        
        result = supabase_client.auth.resend({
            "type": "signup",
            "email": normalized_email
        })
        
        return True
    except Exception as e:
        print(f"Erreur renvoi email: {e}")
        return False

def get_user_profile(supabase_client, user_id: str) -> Optional[Dict]:
    """Récupère le profil d'un utilisateur."""
    try:
        response = supabase_client.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception as e:
        print(f"Erreur récupération profil: {e}")
        return None

# === Fonctions OTP ===

def generate_otp_code(length: int = 6) -> str:
    """Génère un code OTP aléatoire de 4 à 6 chiffres."""
    if length < 4 or length > 6:
        length = 6
    
    # Générer un code numérique sécurisé
    code = ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    
    # S'assurer qu'il ne commence pas par 0
    if code[0] == '0':
        code = str(secrets.randbelow(9) + 1) + code[1:]
    
    return code

def hash_otp_code(code: str) -> str:
    """Hash un code OTP avec SHA-256."""
    return hashlib.sha256(code.encode('utf-8')).hexdigest()

def store_otp_code_for_user(supabase_client, email: str, user_id: str, code: str, expiration_minutes: int = 10) -> bool:
    """Sauvegarde un code OTP hashé en base avec expiration pour un utilisateur."""
    try:
        # Normaliser l'email
        normalized_email = email.lower().strip()
        
        # Calculer l'expiration
        expires_at = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        
        # Hasher le code avec SHA-256
        code_hash = hash_otp_code(code)
        
        # Supprimer les anciens codes non utilisés pour cet email
        supabase_client.table("otp_codes").delete().eq("email", normalized_email).eq("consumed", False).execute()
        
        # Insérer le nouveau code hashé avec user_id
        otp_data = {
            "email": normalized_email,
            "user_id": user_id,
            "code_hash": code_hash,
            "expires_at": expires_at.isoformat(),
            "consumed": False
        }
        
        response = supabase_client.table("otp_codes").insert(otp_data).execute()
        
        if response.data:
            print(f"✅ Code OTP hashé sauvegardé pour {normalized_email}")
            return True
        else:
            print(f"❌ Échec sauvegarde OTP pour {normalized_email}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur sauvegarde OTP: {e}")
        return False

def store_otp_code(supabase_client, email: str, full_name: str, role: str, code: str, expiration_minutes: int = 10) -> bool:
    """Sauvegarde un code OTP hashé en base avec expiration (version legacy)."""
    try:
        # Normaliser l'email
        normalized_email = email.lower().strip()
        
        # Calculer l'expiration
        expires_at = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        
        # Vérifier que le rôle est valide
        if role not in ['client', 'coach']:
            role = 'client'
        
        # Hasher le code avec SHA-256
        code_hash = hash_otp_code(code)
        
        # Supprimer les anciens codes non utilisés pour cet email
        supabase_client.table("otp_codes").delete().eq("email", normalized_email).eq("consumed", False).execute()
        
        # Insérer le nouveau code hashé
        otp_data = {
            "email": normalized_email,
            "code_hash": code_hash,
            "expires_at": expires_at.isoformat(),
            "consumed": False
        }
        
        response = supabase_client.table("otp_codes").insert(otp_data).execute()
        
        if response.data:
            print(f"✅ Code OTP hashé sauvegardé pour {normalized_email}")
            return True
        else:
            print(f"❌ Échec sauvegarde OTP pour {normalized_email}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur sauvegarde OTP: {e}")
        return False

def verify_otp_code(supabase_client, email: str, code: str) -> bool:
    """Vérifie un code OTP et le marque comme consommé si valide."""
    try:
        # Normaliser l'email
        normalized_email = email.lower().strip()
        
        # Hasher le code fourni pour la comparaison
        code_hash = hash_otp_code(code)
        
        # Rechercher le code OTP valide non consommé et non expiré
        current_time = datetime.utcnow().isoformat()
        response = supabase_client.table("otp_codes").select("*").eq("email", normalized_email).eq("code_hash", code_hash).eq("consumed", False).gt("expires_at", current_time).order("created_at", desc=True).limit(1).execute()
        
        if not response.data:
            print(f"❌ Code OTP introuvable ou expiré pour {normalized_email}")
            return False
        
        otp_record = response.data[0]
        
        # Marquer le code comme consommé
        supabase_client.table("otp_codes").update({"consumed": True}).eq("id", otp_record['id']).execute()
        
        print(f"✅ Code OTP vérifié avec succès pour {normalized_email}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur vérification OTP: {e}")
        return False

def cleanup_expired_otp_codes(supabase_client) -> int:
    """Nettoie les codes OTP expirés et retourne le nombre supprimé."""
    try:
        # Supprimer tous les codes expirés
        current_time = datetime.utcnow().isoformat()
        response = supabase_client.table("otp_codes").delete().lt("expires_at", current_time).execute()
        
        deleted_count = len(response.data) if response.data else 0
        if deleted_count > 0:
            print(f"🧹 {deleted_count} codes OTP expirés supprimés")
        
        return deleted_count
        
    except Exception as e:
        print(f"❌ Erreur nettoyage codes OTP: {e}")
        return 0

def get_pending_otp_data(supabase_client, email: str) -> Optional[Dict]:
    """Récupère les données OTP en attente pour un email."""
    try:
        # Normaliser l'email
        normalized_email = email.lower().strip()
        
        # Rechercher le dernier OTP non consommé et non expiré
        current_time = datetime.utcnow().isoformat()
        response = supabase_client.table("pending_registrations").select("*").eq("email", normalized_email).gt("expires_at", current_time).order("created_at", desc=True).limit(1).execute()
        
        if response.data:
            return response.data[0]
        return None
        
    except Exception as e:
        print(f"❌ Erreur récupération données OTP: {e}")
        return None

def store_pending_registration(supabase_client, email: str, full_name: str, password: str, role: str, gender: Optional[str] = None, coach_gender_preference: Optional[str] = None, selected_gyms: Optional[str] = None, expiration_minutes: int = 10) -> bool:
    """Stocke les données d'inscription en attente de vérification OTP."""
    try:
        # Normaliser l'email
        normalized_email = email.lower().strip()
        
        # Calculer l'expiration
        expires_at = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        
        # Vérifier que le rôle est valide
        if role not in ['client', 'coach']:
            role = 'client'
        
        # Supprimer les anciennes données en attente pour cet email
        supabase_client.table("pending_registrations").delete().eq("email", normalized_email).execute()
        
        # Insérer les nouvelles données
        pending_data = {
            "email": normalized_email,
            "full_name": full_name,
            "password": password,
            "role": role,
            "gender": gender,
            "coach_gender_preference": coach_gender_preference if role == "client" else None,
            "selected_gyms": selected_gyms if role == "client" else None,
            "expires_at": expires_at.isoformat()
        }
        
        response = supabase_client.table("pending_registrations").insert(pending_data).execute()
        
        if response.data:
            print(f"✅ Données d'inscription en attente sauvegardées pour {normalized_email}")
            return True
        else:
            print(f"❌ Échec sauvegarde données en attente pour {normalized_email}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur sauvegarde données en attente: {e}")
        return False

def create_user_account_with_otp(supabase_client, email: str, password: str, full_name: str, role: str) -> Dict:
    """Crée un compte utilisateur et son profil après vérification OTP."""
    try:
        # Normaliser l'email
        normalized_email = email.lower().strip()
        
        # Créer l'utilisateur avec Supabase Auth
        auth_response = supabase_client.auth.sign_up({
            "email": normalized_email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name,
                    "role": role
                }
            }
        })
        
        if auth_response.user:
            # Créer le profil utilisateur
            profile_created = create_user_profile_on_confirmation(
                supabase_client, 
                auth_response.user.id, 
                normalized_email, 
                full_name, 
                role
            )
            
            if profile_created:
                print(f"✅ Compte créé avec succès pour {normalized_email}")
                return {
                    "success": True,
                    "user": auth_response.user,
                    "session": auth_response.session
                }
            else:
                print(f"⚠️ Utilisateur créé mais échec création profil pour {normalized_email}")
                return {
                    "success": True,
                    "user": auth_response.user,
                    "session": auth_response.session,
                    "warning": "Profil non créé"
                }
        else:
            print(f"❌ Échec création utilisateur pour {normalized_email}")
            return {"success": False, "error": "Échec création compte"}
            
    except Exception as e:
        print(f"❌ Erreur création compte: {e}")
        return {"success": False, "error": str(e)}

# Fonctions Supabase - Coaches
def search_coaches_supabase(supabase_client, specialty: Optional[str] = None, 
                           user_lat: Optional[float] = None, user_lng: Optional[float] = None, 
                           radius_km: int = 50) -> List[Dict]:
    """Recherche de coachs via Supabase."""
    try:
        # Récupérer tous les coaches avec leurs spécialités
        query = supabase_client.table("profiles").select(
            "*, coach_specialties(specialty)"
        ).eq("role", "coach")
        
        response = query.execute()
        coaches = response.data
        
        result = []
        for coach in coaches:
            # Filtrer par spécialité si demandée
            coach_specialties = [s["specialty"] for s in coach.get("coach_specialties", [])]
            
            if specialty and specialty not in coach_specialties:
                continue
            
            # Calculer la distance si coordonnées fournies
            if user_lat is not None and user_lng is not None and coach.get("lat") and coach.get("lng"):
                distance = haversine_distance(user_lat, user_lng, coach["lat"], coach["lng"])
                if distance > radius_km:
                    continue
                coach["distance"] = distance
            else:
                coach["distance"] = 0
            
            coach["specialties"] = coach_specialties
            result.append(coach)
        
        # Trier par distance
        result.sort(key=lambda x: x["distance"])
        return result
    except Exception as e:
        print(f"Erreur recherche coaches: {e}")
        return search_coaches_mock(specialty, user_lat, user_lng, radius_km)

def get_coach_by_id_supabase(supabase_client, coach_id: str) -> Optional[Dict]:
    """Récupération d'un coach via Supabase."""
    try:
        response = supabase_client.table("profiles").select(
            "*, coach_specialties(specialty)"
        ).eq("id", coach_id).eq("role", "coach").single().execute()
        
        coach = response.data
        if coach:
            coach["specialties"] = [s["specialty"] for s in coach.get("coach_specialties", [])]
        return coach
    except Exception as e:
        print(f"Erreur récupération coach: {e}")
        try:
            return get_coach_by_id_mock(int(coach_id))
        except (ValueError, TypeError):
            return None

def get_transformations_by_coach_supabase(supabase_client, coach_id: str) -> List[Dict]:
    """Récupération des transformations via Supabase."""
    try:
        response = supabase_client.table("transformations").select("*").eq("coach_id", coach_id).execute()
        return response.data
    except Exception as e:
        print(f"Erreur récupération transformations: {e}")
        try:
            return get_transformations_by_coach_mock(int(coach_id))
        except (ValueError, TypeError):
            return []

# Fonctions Supabase - Gestion des profils coaches
def update_coach_profile(supabase_client, coach_id: str, profile_data: Dict) -> bool:
    """Met à jour le profil d'un coach."""
    try:
        # Géocoder la ville si fournie
        if profile_data.get("city"):
            coords = geocode_city(profile_data["city"])
            if coords:
                profile_data["lat"], profile_data["lng"] = coords
        
        supabase_client.table("profiles").update(profile_data).eq("id", coach_id).execute()
        return True
    except Exception as e:
        print(f"Erreur mise à jour profil: {e}")
        return False

def update_coach_specialties(supabase_client, coach_id: str, specialties: List[str]) -> bool:
    """Met à jour les spécialités d'un coach."""
    try:
        # Supprimer les anciennes spécialités
        supabase_client.table("coach_specialties").delete().eq("coach_id", coach_id).execute()
        
        # Ajouter les nouvelles
        if specialties:
            specialty_data = [{"coach_id": coach_id, "specialty": s} for s in specialties]
            supabase_client.table("coach_specialties").insert(specialty_data).execute()
        
        return True
    except Exception as e:
        print(f"Erreur mise à jour spécialités: {e}")
        return False

def add_transformation(supabase_client, coach_id: str, transformation_data: Dict) -> Optional[Dict]:
    """Ajoute une transformation."""
    try:
        transformation_data["coach_id"] = coach_id
        response = supabase_client.table("transformations").insert(transformation_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"Erreur ajout transformation: {e}")
        return None

def upload_transformation_images(supabase_client, transformation_id: str, before_file, after_file) -> Tuple[Optional[str], Optional[str]]:
    """Upload les images avant/après vers le bucket transformations."""
    try:
        before_url = None
        after_url = None
        
        if before_file:
            before_path = f"{transformation_id}/before.jpg"
            # Upload avec options (upsert pour remplacer si existe)
            supabase_client.storage.from_("transformations").upload(
                before_path, before_file, file_options={"content-type": "image/jpeg", "upsert": True}
            )
            # Récupérer l'URL publique correctement
            url_response = supabase_client.storage.from_("transformations").get_public_url(before_path)
            before_url = url_response.get("data", {}).get("publicUrl") if hasattr(url_response, 'get') else str(url_response)
        
        if after_file:
            after_path = f"{transformation_id}/after.jpg"
            supabase_client.storage.from_("transformations").upload(
                after_path, after_file, file_options={"content-type": "image/jpeg", "upsert": True}
            )
            url_response = supabase_client.storage.from_("transformations").get_public_url(after_path)
            after_url = url_response.get("data", {}).get("publicUrl") if hasattr(url_response, 'get') else str(url_response)
        
        return before_url, after_url
    except Exception as e:
        print(f"Erreur upload images: {e}")
        return None, None

# ======================================
# SYSTÈME COACH ↔ SALLE ↔ CLIENT
# ======================================

# Structure pour les relations coach-salle (stockage temporaire en attendant la DB)
COACH_GYMS = []

# Mapping unifié gym_id -> Set[coach_id] pour performances optimisées
COACH_GYMS_BY_ID = {}

# Données de test - Simuler qu'un coach demo a ajouté une salle
def init_test_data():
    """Initialise des données de test pour valider le système coach ↔ gym."""
    global COACH_GYMS, COACH_GYMS_BY_ID
    
    # Simuler qu'un coach (ID=1, Marie Dubois) a ajouté une salle de test
    if not COACH_GYMS:  # Éviter de dupliquer si déjà initialisé
        test_gym_data = {
            "name": "Salle Test Demo",
            "address": "123 Rue de Test, 78000 Versailles, France",
            "lat": 48.8014,
            "lng": 2.1301
        }
        
        # Ajouter la relation directement (comme si add_coach_gym avait été appelée)
        relation = {
            "id": 1,
            "gym_id": "coach_gym_1",
            "coach_id": "1",  # ID du coach Marie Dubois dans MOCK_COACHES
            "gym_data": test_gym_data,
            "created_at": "2025-09-17T17:00:00Z"
        }
        
        COACH_GYMS.append(relation)
        
        # Ajouter dans le mapping unifié
        if "coach_gym_1" not in COACH_GYMS_BY_ID:
            COACH_GYMS_BY_ID["coach_gym_1"] = set()
        COACH_GYMS_BY_ID["coach_gym_1"].add("1")
        
        print("✅ Données de test initialisées: coach 1 -> gym coach_gym_1")

# Initialiser les données de test au démarrage
init_test_data()

def geocode_address(query: str) -> Optional[Dict]:
    """
    Service de géocodage unifié pour convertir adresse en coordonnées GPS.
    Retourne: {"name": str, "address": str, "lat": float, "lng": float, "place_id": str?}
    """
    try:
        # Ajouter "France" pour améliorer la précision des résultats
        location = geolocator.geocode(f"{query}, France")
        if location:
            lat = getattr(location, 'latitude', None)
            lng = getattr(location, 'longitude', None)
            address = getattr(location, 'address', query)
            if lat is not None and lng is not None:
                return {
                    "name": query,
                    "address": address,
                    "lat": float(lat),
                    "lng": float(lng),
                    "place_id": None  # Nominatim n'a pas de place_id comme Google
                }
        return None
    except (GeocoderTimedOut, GeocoderServiceError, Exception) as e:
        print(f"Erreur géocodage pour '{query}': {e}")
        return None

def get_coach_gyms(coach_id: str) -> List[Dict]:
    """Récupère les salles où exerce un coach."""
    return [
        relation for relation in COACH_GYMS 
        if relation["coach_id"] == coach_id
    ]

def add_coach_gym(coach_id: str, gym_data: Dict) -> bool:
    """
    Ajoute une relation coach-salle.
    gym_data: {"name": str, "address": str, "lat": float, "lng": float}
    """
    try:
        # Vérifier si la relation existe déjà
        existing = any(
            relation["coach_id"] == coach_id and 
            relation["gym_data"]["address"] == gym_data["address"]
            for relation in COACH_GYMS
        )
        
        if existing:
            return False  # Relation déjà existante
        
        # Générer l'ID pour cette gym (sera utilisé comme gym_id)
        relation_id = len(COACH_GYMS) + 1
        gym_id = f"coach_gym_{relation_id}"
        
        # Ajouter la nouvelle relation
        relation = {
            "id": relation_id,
            "gym_id": gym_id,  # Stocker le gym_id directement
            "coach_id": coach_id,
            "gym_data": gym_data,
            "created_at": datetime.now().isoformat()
        }
        
        COACH_GYMS.append(relation)
        
        # Mettre à jour le mapping gym_id -> coaches
        if gym_id not in COACH_GYMS_BY_ID:
            COACH_GYMS_BY_ID[gym_id] = set()
        COACH_GYMS_BY_ID[gym_id].add(coach_id)
        
        print(f"✅ Relation ajoutée: coach {coach_id} -> gym {gym_id}")
        return True
        
    except Exception as e:
        print(f"Erreur ajout coach-gym: {e}")
        return False

def remove_coach_gym(coach_id: str, relation_id: str) -> bool:
    """Supprime une relation coach-salle."""
    try:
        global COACH_GYMS
        initial_count = len(COACH_GYMS)
        
        # Trouver la relation à supprimer pour récupérer le gym_id
        relation_to_remove = None
        for relation in COACH_GYMS:
            if relation["coach_id"] == coach_id and str(relation["id"]) == str(relation_id):
                relation_to_remove = relation
                break
        
        if relation_to_remove:
            gym_id = relation_to_remove.get("gym_id", f"coach_gym_{relation_to_remove['id']}")
            
            # Supprimer de COACH_GYMS
            COACH_GYMS = [
                relation for relation in COACH_GYMS
                if not (relation["coach_id"] == coach_id and str(relation["id"]) == str(relation_id))
            ]
            
            # Mettre à jour COACH_GYMS_BY_ID
            if gym_id in COACH_GYMS_BY_ID:
                COACH_GYMS_BY_ID[gym_id].discard(coach_id)
                # Supprimer la clé si plus de coaches
                if not COACH_GYMS_BY_ID[gym_id]:
                    del COACH_GYMS_BY_ID[gym_id]
            
            print(f"✅ Relation supprimée: coach {coach_id} -> gym {gym_id}")
            return len(COACH_GYMS) < initial_count
        
        return False
        
    except Exception as e:
        print(f"Erreur suppression coach-gym: {e}")
        return False

def search_gyms_by_location(lat: float, lng: float, radius_km: int = 25) -> List[Dict]:
    """
    Recherche les salles dans un rayon donné.
    Combine GYMS_DATABASE + salles ajoutées par les coachs.
    """
    try:
        from main import GYMS_DATABASE  # Import depuis main.py
        
        results = []
        
        # Rechercher dans GYMS_DATABASE
        for gym in GYMS_DATABASE:
            distance = haversine_distance(lat, lng, gym["lat"], gym["lng"])
            if distance <= radius_km:
                # Calculer coach_count pour cette gym statique
                # Chercher les coaches qui ont ajouté cette salle (par adresse)
                gym_id = gym["id"]
                coach_count = 0
                
                # Compter dans COACH_GYMS_BY_ID si la gym existe
                if gym_id in COACH_GYMS_BY_ID:
                    coach_count += len(COACH_GYMS_BY_ID[gym_id])
                
                # Compter aussi les coaches qui ont ajouté cette même adresse
                for relation in COACH_GYMS:
                    if relation["gym_data"]["address"] == gym["address"]:
                        coach_count += 1
                
                gym_result = gym.copy()
                gym_result["distance_km"] = round(distance, 1)
                gym_result["coach_count"] = coach_count
                results.append(gym_result)
        
        # Rechercher dans les salles ajoutées par les coachs
        for relation in COACH_GYMS:
            gym_data = relation["gym_data"]
            distance = haversine_distance(lat, lng, gym_data["lat"], gym_data["lng"])
            if distance <= radius_km:
                # Éviter les doublons avec GYMS_DATABASE
                if not any(existing["address"] == gym_data["address"] for existing in results):
                    gym_id = relation.get("gym_id", f"coach_gym_{relation['id']}")
                    
                    # Utiliser COACH_GYMS_BY_ID pour compter efficacement
                    coach_count = len(COACH_GYMS_BY_ID.get(gym_id, set()))
                    
                    gym_result = {
                        "id": gym_id,
                        "name": gym_data["name"],
                        "address": gym_data["address"],
                        "lat": gym_data["lat"],
                        "lng": gym_data["lng"],
                        "chain": "Salle personnalisée",
                        "distance_km": round(distance, 1),
                        "coach_count": coach_count
                    }
                    results.append(gym_result)
        
        # Trier par distance
        results.sort(key=lambda x: x["distance_km"])
        return results
        
    except Exception as e:
        print(f"Erreur recherche salles: {e}")
        return []

def get_coaches_by_gym(gym_id: str) -> List[Dict]:
    """Récupère tous les coachs exerçant dans une salle donnée par gym_id."""
    try:
        coach_ids = set()
        
        # 1. Chercher dans COACH_GYMS_BY_ID (gym_id dynamiques: coach_gym_X)
        if gym_id in COACH_GYMS_BY_ID:
            coach_ids.update(COACH_GYMS_BY_ID[gym_id])
            print(f"✅ Trouvé {len(coach_ids)} coaches dans COACH_GYMS_BY_ID pour gym {gym_id}")
        
        # 2. Pour les gyms statiques, chercher aussi par adresse dans COACH_GYMS
        # (compatibilité avec gyms ajoutées avant le nouveau système)
        try:
            from main import GYMS_DATABASE
            gym_static = next((g for g in GYMS_DATABASE if g["id"] == gym_id), None)
            if gym_static:
                # Chercher les coaches qui ont ajouté cette même adresse
                for relation in COACH_GYMS:
                    if relation["gym_data"]["address"] == gym_static["address"]:
                        coach_ids.add(relation["coach_id"])
                        print(f"✅ Coach {relation['coach_id']} trouvé par adresse pour gym statique {gym_id}")
        except ImportError:
            pass
        
        # 3. Récupérer les infos détaillées des coachs depuis MOCK_COACHES
        coaches = []
        for coach_id in coach_ids:
            coach = next((c for c in MOCK_COACHES if str(c["id"]) == str(coach_id)), None)
            if coach:
                coaches.append(coach)
                print(f"✅ Détails coach récupérés: {coach['full_name']} (ID: {coach_id})")
            else:
                print(f"⚠️ Coach ID {coach_id} non trouvé dans MOCK_COACHES")
        
        print(f"📊 Résultat final pour gym {gym_id}: {len(coaches)} coaches trouvés")
        return coaches
        
    except Exception as e:
        print(f"❌ Erreur récupération coachs pour gym {gym_id}: {e}")
        return []