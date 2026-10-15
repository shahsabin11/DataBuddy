"""Shared agent state. Checkpoints will persist this in Postgres later."""

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Minimal graph state for the clean → chart/test → report workflow."""

    messages: Annotated[list, add_messages]
    institution_id: str
    user_id: str
    project_id: str
    # Set when the graph must stop for a student decision.
    pending_decision: str | None
    # Last sandbox tool result (tables / plot keys), never invented by the model.
    last_tool_result: dict | None
    phase: Literal[
        "profile",
        "clean",
        "explore",
        "recommend",
        "awaiting_decision",
        "run",
        "report",
        "done",
    ]
