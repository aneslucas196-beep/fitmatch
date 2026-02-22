"""
Handler Vercel sans FastAPI pour GET /api/reminders_process.
Utilise BaseHTTPRequestHandler (natif Vercel Python).
"""
import json
import traceback
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from main import process_due_reminders
            result = process_due_reminders()
            body = {"status": "ok", "result": result}
            payload = json.dumps(body, default=str)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))
        except Exception as e:
            body = {
                "status": "error",
                "error": str(e),
                "trace": traceback.format_exc(),
            }
            payload = json.dumps(body, default=str)
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))
