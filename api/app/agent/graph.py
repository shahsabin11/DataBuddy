"""
LangGraph skeleton for the human-in-the-loop analysis workflow.

Nodes stop at decision points (chart type, method, destructive clean).
Compute tools will call E2B; they are stubbed here so the scaffold boots
without API keys.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.logging import get_logger

logger = get_logger(__name__)


def recommend_next_step(state: AgentState) -> dict[str, Any]:
    """Placeholder recommender. Real version calls Claude with tool schemas."""
    logger.info(
        "agent_recommend",
        project_id=state.get("project_id"),
        phase=state.get("phase"),
    )
    return {
        "phase": "awaiting_decision",
        "pending_decision": (
            "Confirm variables and choose a chart type or analysis method. "
            "See docs/analytics-spec.md and docs/collaboration-model.md."
        ),
    }


def await_student_decision(state: AgentState) -> dict[str, Any]:
    """
    Interrupt-style pause. In production this node ends the model turn;
    the next student message resumes from a Postgres checkpoint.
    """
    logger.info(
        "agent_awaiting_decision",
        pending=state.get("pending_decision"),
    )
    return {"phase": "awaiting_decision"}


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("recommend", recommend_next_step)
    graph.add_node("await_decision", await_student_decision)
    graph.set_entry_point("recommend")
    graph.add_edge("recommend", "await_decision")
    graph.add_edge("await_decision", END)
    return graph.compile()
