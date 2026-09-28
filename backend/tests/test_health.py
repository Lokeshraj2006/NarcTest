"""Smoke test — the app starts and /health responds."""


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "FieldProof"
    assert "version" in data


def test_openapi_lists_fieldproof_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for p in ["/kits", "/tests", "/tests/{test_id}", "/verify/{test_id}", "/v/{test_id}",
              "/reviews/pending", "/verify/pubkey"]:
        assert p in paths
    assert not any(p.startswith(("/scan", "/inspections", "/violations", "/rules")) for p in paths)
