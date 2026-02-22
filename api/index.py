import os
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse

app = FastAPI()


def _check_cron_secret(request: Request, secret: str | None) -> None:
    """Lève 401 si CRON_SECRET est défini et non fourni (Bearer ou query)."""
    cron_secret = os.environ.get("CRON_SECRET")
    if not cron_secret:
        return
    auth = request.headers.get("Authorization") if request else None
    bearer = auth.split(" ", 1)[1] if auth and auth.startswith("Bearer ") else None
    if (secret or bearer) != cron_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _run_reminders():
    from main import process_due_reminders
    return process_due_reminders()


@app.get("/reminders_process")
async def reminders_process(
    request: Request,
    secret: str | None = Query(None, alias="secret"),
):
    _check_cron_secret(request, secret)
    try:
        result = _run_reminders()
        return {"status": "ok", "result": result}
    except Exception as e:
        return JSONResponse(
            {"status": "error", "error": str(e)},
            status_code=500,
        )


@app.get("/reminders/process")
async def reminders_process_slash(
    request: Request,
    secret: str | None = Query(None, alias="secret"),
):
    _check_cron_secret(request, secret)
    try:
        result = _run_reminders()
        return {"status": "ok", "result": result}
    except Exception as e:
        return JSONResponse(
            {"status": "error", "error": str(e)},
            status_code=500,
        )
