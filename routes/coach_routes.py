"""
Routes API pour les coaches.
"""
from typing import Optional
from fastapi import Query
from fastapi.responses import JSONResponse


def register_coach_routes(app, deps: dict):
    """Enregistre les routes coaches sur l'app."""
    load_demo_users = deps["load_demo_users"]
    get_coaches_by_gym_id = deps["get_coaches_by_gym_id"]
    log = deps.get("log")

    from services.coach_service import get_coaches_list

    @app.get("/api/coaches")
    async def get_all_coaches_api(
        gym_id: Optional[str] = None,
        specialty: Optional[str] = None,
        postal_code: Optional[str] = None,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        """
        Retourne les coaches (pagination: limit, offset).
        Filtres: gym_id, specialty, postal_code.
        """
        try:
            coaches = get_coaches_list(
                load_users_fn=load_demo_users,
                get_coaches_by_gym_id_fn=get_coaches_by_gym_id,
                gym_id=gym_id,
                specialty=specialty,
                postal_code=postal_code,
            )
            total = len(coaches)
            coaches_page = coaches[offset : offset + limit]
            return {
                "success": True,
                "count": len(coaches_page),
                "total": total,
                "limit": limit,
                "offset": offset,
                "coaches": coaches_page,
            }
        except Exception as e:
            if log:
                log.error(f"Erreur API /api/coaches: {e}")
            return {
                "success": False,
                "error": str(e),
                "coaches": [],
            }
