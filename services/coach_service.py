"""
Service métier pour la gestion des coaches.
Centralise la logique de récupération et filtrage des coaches.
"""
import json
import os
from typing import Dict, List, Optional, Any


def get_coaches_list(
    load_users_fn,
    get_coaches_by_gym_id_fn,
    gym_id: Optional[str] = None,
    specialty: Optional[str] = None,
    postal_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retourne la liste des coaches avec filtres optionnels.
    
    Args:
        load_users_fn: Fonction pour charger les utilisateurs
        get_coaches_by_gym_id_fn: Fonction pour récupérer les coaches d'une salle
        gym_id: Filtrer par salle
        specialty: Filtrer par spécialité
        postal_code: Filtrer par code postal
    
    Returns:
        Liste des coaches (dicts)
    """
    if gym_id:
        return get_coaches_by_gym_id_fn(gym_id)
    
    demo_users = load_users_fn()
    coaches: List[Dict[str, Any]] = []
    
    for email, user_data in demo_users.items():
        subscription_status = user_data.get("subscription_status", "")
        is_blocked = subscription_status in ["blocked", "cancelled", "past_due"]
        if (
            user_data.get("role") == "coach"
            and user_data.get("profile_completed")
            and not is_blocked
        ):
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
                "instagram_url": user_data.get("instagram_url", ""),
                "gyms": (
                    user_data.get("selected_gym_ids", "").split(",")
                    if user_data.get("selected_gym_ids")
                    else []
                ),
            })
    
    if specialty:
        coaches = [
            c
            for c in coaches
            if specialty.lower() in [s.lower() for s in c.get("specialties", [])]
        ]
    
    if postal_code:
        gyms_file = os.path.join("static", "data", "gyms.json")
        if os.path.exists(gyms_file):
            with open(gyms_file, "r", encoding="utf-8") as f:
                all_gyms = json.load(f)
                gyms_in_postal = [g["id"] for g in all_gyms if g.get("postal_code") == postal_code]
                coaches = [
                    c
                    for c in coaches
                    if any(gid in c.get("gyms", []) for gid in gyms_in_postal)
                ]
    
    return coaches
