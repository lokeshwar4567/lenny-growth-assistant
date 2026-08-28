from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["provider"] == "ollama"


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "Lenny Growth Assistant"


def test_create_session():
    response = client.post("/api/sessions")

    assert response.status_code == 200

    data = response.json()

    assert "session_id" in data
