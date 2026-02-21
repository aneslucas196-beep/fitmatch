from fastapi import FastAPI

app = FastAPI()


@app.get("/api/reminders_process")
async def reminders_process():
    try:
        from main import process_due_reminders
        result = process_due_reminders()
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}
