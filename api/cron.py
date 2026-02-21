from fastapi import APIRouter, Request, HTTPException, Query
import os
from typing import Optional

router = APIRouter()


@router.get("/api/cron")
async def cron_job(request: Request, secret: Optional[str] = Query(None)):
    """Endpoint appelé par le cron Vercel toutes les 10 min. Sécurisé par CRON_SECRET (header Bearer ou query ?secret=)."""
    cron_secret = os.environ.get("CRON_SECRET")
    if cron_secret:
        auth = request.headers.get("authorization")
        bearer_ok = auth == f"Bearer {cron_secret}"
        query_ok = secret == cron_secret
        if not (bearer_ok or query_ok):
            raise HTTPException(status_code=401, detail="Unauthorized")

    print("Cron job executed successfully")
    return {"status": "ok"}
