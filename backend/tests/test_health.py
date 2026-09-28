"""
Smoke test — verifies the FastAPI app starts and the health endpoint responds.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """GET /health returns 200 with app metadata."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "app" in data


def test_openapi_docs_accessible():
    """Swagger UI JSON schema is reachable."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()
