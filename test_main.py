from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200

def test_market_watch():
    response = client.get("/market/watch")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)

def test_login_invalid():
    response = client.post("/auth/login", json={"username": "error", "password": "wrong"})
    assert response.status_code == 404
