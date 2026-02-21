from main import app

def handler(request):
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.get("/api/reminders/process")
    return response.json()
