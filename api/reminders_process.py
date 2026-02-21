from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/reminders_process")
async def reminders_process():
    return JSONResponse({"status": "ok"})
