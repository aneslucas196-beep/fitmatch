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
        if location and location.latitude is not None and location.longitude is not None:
            return (float(location.latitude), float(location.longitude))
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

def get_supabase_client():
    """
    Initialise le client Supabase si les variables d'environnement sont présentes.
    Retourne None si les credentials ne sont pas disponibles.
    """
    try:
        from supabase import create_client, Client
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")  # Utiliser SUPABASE_KEY au lieu de SUPABASE_ANON_KEY
        
        if url and key:
            # Valider l'URL avant de créer le client
            if url.startswith("https://") and ".supabase.co" in url:
                return create_client(url, key)
            else:
                print(f"⚠️ URL Supabase invalide: {url}")
                return None
        return None
    except Exception as e:
        print(f"⚠️ Erreur lors de l'initialisation Supabase: {e}")
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

# Fonctions Supabase (futures implémentations)
def search_coaches_supabase(supabase_client, specialty: Optional[str] = None, 
                           user_lat: Optional[float] = None, user_lng: Optional[float] = None, 
                           radius_km: int = 50) -> List[Dict]:
    """
    Recherche de coachs via Supabase (à implémenter).
    """
    # TODO: Implémenter la recherche Supabase
    return search_coaches_mock(specialty, user_lat, user_lng, radius_km)

def get_coach_by_id_supabase(supabase_client, coach_id: int) -> Optional[Dict]:
    """
    Récupération d'un coach via Supabase (à implémenter).
    """
    # TODO: Implémenter la récupération Supabase
    return get_coach_by_id_mock(coach_id)

def get_transformations_by_coach_supabase(supabase_client, coach_id: int) -> List[Dict]:
    """
    Récupération des transformations via Supabase (à implémenter).
    """
    # TODO: Implémenter la récupération Supabase
    return get_transformations_by_coach_mock(coach_id)