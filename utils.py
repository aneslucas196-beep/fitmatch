import os
import math
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
        anon_key = os.getenv("SUPABASE_KEY")  # Clé publique/anon
        
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
    client = get_supabase_anon_client()
    if client and access_token:
        try:
            # Utiliser la méthode correcte pour définir le token
            client.auth.set_auth(access_token)
            return client
        except Exception as e:
            print(f"Erreur authentification client: {e}")
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
def sign_up_user(supabase_client, email: str, password: str, full_name: str, role: str = "client") -> Optional[Dict]:
    """Inscription d'un nouvel utilisateur."""
    try:
        auth_response = supabase_client.auth.sign_up({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            # Créer le profil utilisateur
            profile_data = {
                "id": auth_response.user.id,
                "role": role,
                "full_name": full_name,
                "email": email
            }
            
            supabase_client.table("profiles").insert(profile_data).execute()
            return {"user": auth_response.user, "session": auth_response.session}
        return None
    except Exception as e:
        print(f"Erreur inscription: {e}")
        return None

def sign_in_user(supabase_client, email: str, password: str) -> Optional[Dict]:
    """Connexion d'un utilisateur."""
    try:
        auth_response = supabase_client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if auth_response.user:
            return {"user": auth_response.user, "session": auth_response.session}
        return None
    except Exception as e:
        print(f"Erreur connexion: {e}")
        return None

def get_user_profile(supabase_client, user_id: str) -> Optional[Dict]:
    """Récupère le profil d'un utilisateur."""
    try:
        response = supabase_client.table("profiles").select("*").eq("id", user_id).single().execute()
        return response.data
    except Exception as e:
        print(f"Erreur récupération profil: {e}")
        return None

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