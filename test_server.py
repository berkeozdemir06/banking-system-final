from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
try:
    response = client.post("/api/agent/ingest/kap", json={"ticker": "TRENJ"})
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.json())
except Exception as e:
    print("EXCEPTION:", e)
