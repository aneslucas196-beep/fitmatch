from fastapi import FastAPI
from fastapi.responses import JSONResponse
import traceback

app = FastAPI()

@app.get("/api/reminders_process")
async def reminders_process():
    try:
        from main import process_due_reminders
        result = process_due_reminders()

        return JSONResponse({
            "status": "ok",
            "result": result
        })

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "trace": traceback.format_exc()
        }, status_code=500)
