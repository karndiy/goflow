from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_200_with_expected_shape():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "database" in body
    assert "redis" in body
