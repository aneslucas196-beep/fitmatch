from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/")
@app.get("/api/reminders_process")
def run():
    try:
        from main import process_due_reminders
        result = process_due_reminders()
        return {"status": "ok", "result": result}
    except Exception as e:
        return JSONResponse(
            {"status": "error", "error": str(e)},
            status_code=500,
        )
