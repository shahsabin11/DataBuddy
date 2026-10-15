"""Smoke tests for the health endpoint and agent graph scaffold."""

from fastapi.testclient import TestClient

from app.agent.graph import build_agent_graph
from app.main import create_app


def test_health_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "databuddy-api"


def test_agent_graph_compiles() -> None:
    graph = build_agent_graph()
    result = graph.invoke(
        {
            "messages": [],
            "institution_id": "inst-1",
            "user_id": "user-1",
            "project_id": "proj-1",
            "pending_decision": None,
            "last_tool_result": None,
            "phase": "profile",
        }
    )
    assert result["phase"] == "awaiting_decision"
    assert result["pending_decision"]
