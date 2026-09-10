"""
SAFEGUARD AI - API Smoke Test
Tests that all major API routes return valid responses.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="module")
def client():
    # Patch the RAG pipeline initialization to avoid slow model load in tests
    with patch('backend.rag.pipeline.rag_pipeline') as mock_rag:
        mock_rag._initialized = True
        mock_rag._embedding_service.mode = "tfidf"
        mock_rag._flat_chunks = [
            {
                "chunk_id": "test_chunk_1",
                "doc_id": "TEST-001",
                "title": "Test Safety Standard",
                "source": "TEST",
                "section": "1.1",
                "topic": "guards",
                "content": "Machine guards shall protect operators from moving parts.",
                "machine_categories": ["cnc_machine"],
            }
        ]
        from backend.api.main import app
        # Don't run lifespan for tests
        app.router.lifespan_handler = None
        yield TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


def test_facility_summary(client):
    r = client.get("/api/v1/facility/summary")
    assert r.status_code == 200
    data = r.json()
    assert "total_machines" in data
    assert data["total_machines"] == 5
    assert "facility_safety_score" in data


def test_current_telemetry(client):
    r = client.get("/api/v1/machines/current")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    for mid in ["M-001", "M-002", "M-003", "M-004", "M-005"]:
        assert mid in data
        assert "risk_score" in data[mid]
        assert 0 <= data[mid]["risk_score"] <= 100


def test_machine_not_found(client):
    r = client.get("/api/v1/machines/M-999/current")
    assert r.status_code == 404


def test_risk_overview(client):
    r = client.get("/api/v1/risk/overview")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 5
    for item in data:
        assert "risk_score" in item
        assert "risk_level" in item


def test_alerts_endpoint(client):
    r = client.get("/api/v1/alerts")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_whatif_simulation(client):
    r = client.post("/api/v1/whatif/simulate", json={
        "machine_id": "M-001",
        "temperature": 85.0,  # above 75°C threshold
        "guard_status": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert "risk_score" in data
    assert data["risk_score"] > 0  # should detect temperature + guard issues
    assert "risk_factors" in data
    assert len(data["risk_factors"]) > 0


def test_whatif_normal_operation(client):
    r = client.post("/api/v1/whatif/simulate", json={
        "machine_id": "M-001",
        "temperature": 42.0,
        "vibration": 1.8,
        "guard_status": True,
    })
    assert r.status_code == 200
    data = r.json()
    # Normal operation should have low/zero risk from these params
    assert "risk_score" in data
    assert "risk_level" in data


def test_whatif_invalid_machine(client):
    r = client.post("/api/v1/whatif/simulate", json={
        "machine_id": "M-999",
    })
    assert r.status_code == 404


def test_simulation_scenario(client):
    r = client.post("/api/v1/simulation/scenario", json={
        "machine_id": "M-001",
        "scenario": "degrading",
        "degradation": 0.5,
    })
    assert r.status_code == 200
    assert "message" in r.json()


def test_simulation_invalid_scenario(client):
    r = client.post("/api/v1/simulation/scenario", json={
        "machine_id": "M-001",
        "scenario": "invalid_scenario_xyz",
    })
    assert r.status_code == 400


def test_ibm_status(client):
    r = client.get("/api/v1/ibm/status")
    assert r.status_code == 200
    data = r.json()
    assert "watsonx" in data
    assert "langflow" in data
    assert "rag" in data
