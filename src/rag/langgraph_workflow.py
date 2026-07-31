"""LangGraph execution wrapper around the framework-independent RAG contract."""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from typing import Any, Mapping, Sequence, TypedDict
from uuid import uuid4

from .langsmith_observability import langsmith_status
from .models import TravelConditions
from .orchestrator import RagOrchestrator, create_rag_orchestrator


class RagGraphState(TypedDict, total=False):
    message: str
    history: list[dict[str, str]]
    current_conditions: dict[str, Any]
    selected_options: dict[str, Any]
    avoid_content_ids: list[int]
    previous_result: dict[str, Any]
    result: dict[str, Any]
    status: str
    graph_path: list[str]
    thread_id: str


class LangGraphRagWorkflow:
    """Run the existing plain-Python RAG through an observable state graph."""

    def __init__(
        self,
        orchestrator: RagOrchestrator,
        *,
        memory_enabled: bool | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.memory_enabled = (
            _env_bool("LANGGRAPH_MEMORY_ENABLED", True)
            if memory_enabled is None
            else bool(memory_enabled)
        )
        self._checkpointer = self._create_checkpointer()
        self.graph = self._compile_graph()

    @property
    def llm(self):
        """Preserve the existing usage-inspection contract used by tests/UI."""

        return self.orchestrator.llm

    @property
    def condition_service(self):
        """Preserve the condition-only evaluation contract."""

        return self.orchestrator.condition_service

    def run(
        self,
        *,
        message: str = "",
        history: Sequence[Mapping[str, str]] = (),
        current_conditions: Mapping[str, Any] | TravelConditions | None = None,
        selected_options: Mapping[str, Any] | None = None,
        avoid_content_ids: Sequence[int] = (),
        thread_id: str | None = None,
        trace_metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_thread_id = thread_id or str(uuid4())
        conditions_payload = (
            current_conditions.to_dict()
            if isinstance(current_conditions, TravelConditions)
            else dict(current_conditions or {})
        )
        state: RagGraphState = {
            "message": message,
            "history": [dict(item) for item in history],
            "current_conditions": conditions_payload,
            "selected_options": dict(selected_options or {}),
            "avoid_content_ids": [int(value) for value in avoid_content_ids],
            "thread_id": resolved_thread_id,
            "graph_path": [],
        }
        metadata = {
            "rag_engine": "langgraph",
            "workflow_version": "rag-graph-v1",
            **dict(trace_metadata or {}),
        }
        config: dict[str, Any] = {
            "run_name": "SKN28 Jeju Travel RAG",
            "tags": ["rag", "jeju", "langgraph"],
            "metadata": metadata,
        }
        if self.memory_enabled:
            config["configurable"] = {"thread_id": resolved_thread_id}

        final_state = self.graph.invoke(state, config=config)
        result = deepcopy(dict(final_state.get("result") or {}))
        result_meta = dict(result.get("meta") or {})
        result_meta["langgraph"] = {
            "enabled": True,
            "workflow_version": "rag-graph-v1",
            "thread_id": resolved_thread_id,
            "memory_enabled": self.memory_enabled,
            "path": list(final_state.get("graph_path") or ()),
        }
        result_meta["langsmith"] = langsmith_status().to_dict()
        result["meta"] = result_meta
        return result

    def revise(
        self,
        *,
        previous_result: Mapping[str, Any],
        message: str,
    ) -> dict[str, Any]:
        """Keep targeted itinerary revision compatible with the old contract."""

        result = self.orchestrator.revise(
            previous_result=previous_result,
            message=message,
        )
        result_meta = dict(result.get("meta") or {})
        result_meta["langgraph"] = {
            "enabled": True,
            "workflow_version": "rag-graph-v1",
            "path": ["targeted_revision"],
        }
        result_meta["langsmith"] = langsmith_status().to_dict()
        result["meta"] = result_meta
        return result

    def create_initial_itinerary(
        self,
        *,
        duration_days: int,
        party_size: int,
        local_transport: str,
        travel_style: str,
    ) -> dict[str, Any]:
        """Expose the guided four-input initial generation contract."""

        return self.orchestrator.create_initial_itinerary(
            duration_days=duration_days,
            party_size=party_size,
            local_transport=local_transport,
            travel_style=travel_style,
        )

    def continue_itinerary(
        self,
        *,
        previous_result: Mapping[str, Any],
        message: str,
        history: Sequence[Mapping[str, str]] = (),
    ) -> dict[str, Any]:
        """Expose post-generation natural-language itinerary revision."""

        result = self.orchestrator.continue_itinerary(
            previous_result=previous_result,
            message=message,
            history=history,
        )
        result_meta = dict(result.get("meta") or {})
        result_meta["langgraph"] = {
            "enabled": True,
            "workflow_version": "rag-graph-v1",
            "path": ["natural_language_revision"],
        }
        result_meta["langsmith"] = langsmith_status().to_dict()
        result["meta"] = result_meta
        return result

    def get_state(self, thread_id: str):
        """Inspect a conversation checkpoint when in-memory persistence is on."""

        if not self.memory_enabled:
            raise RuntimeError("LANGGRAPH_MEMORY_ENABLED is false")
        return self.graph.get_state(
            {"configurable": {"thread_id": str(thread_id)}}
        )

    def _create_checkpointer(self):
        if not self.memory_enabled:
            return None
        try:
            from langgraph.checkpoint.memory import InMemorySaver
        except ImportError as exc:
            raise RuntimeError(
                "langgraph is not installed; run: pip install -r requirements.txt"
            ) from exc
        return InMemorySaver()

    def _compile_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "langgraph is not installed; run: pip install -r requirements.txt"
            ) from exc

        builder = StateGraph(RagGraphState)
        builder.add_node("prepare_input", self._prepare_input)
        builder.add_node("execute_rag", self._execute_rag)
        builder.add_node("request_clarification", self._request_clarification)
        builder.add_node("finalize_result", self._finalize_result)
        builder.add_edge(START, "prepare_input")
        builder.add_edge("prepare_input", "execute_rag")
        builder.add_conditional_edges(
            "execute_rag",
            self._route_after_execution,
            {
                "clarification": "request_clarification",
                "final": "finalize_result",
            },
        )
        builder.add_edge("request_clarification", END)
        builder.add_edge("finalize_result", END)
        return builder.compile(checkpointer=self._checkpointer)

    @staticmethod
    def _prepare_input(state: RagGraphState) -> RagGraphState:
        previous = state.get("result") or state.get("previous_result") or {}
        current = dict(state.get("current_conditions") or {})
        if not current and isinstance(previous, Mapping):
            prior_conditions = previous.get("conditions")
            if isinstance(prior_conditions, Mapping):
                current = dict(prior_conditions)
        return {
            "current_conditions": current,
            "graph_path": [*state.get("graph_path", []), "prepare_input"],
        }

    def _execute_rag(self, state: RagGraphState) -> RagGraphState:
        result = self.orchestrator.run(
            message=str(state.get("message") or ""),
            history=state.get("history") or (),
            current_conditions=state.get("current_conditions") or None,
            selected_options=state.get("selected_options") or None,
            avoid_content_ids=state.get("avoid_content_ids") or (),
        )
        return {
            "result": result,
            "status": str(result.get("status") or "unknown"),
            "graph_path": [*state.get("graph_path", []), "execute_rag"],
        }

    @staticmethod
    def _route_after_execution(state: RagGraphState) -> str:
        return (
            "clarification"
            if state.get("status") == "clarification_required"
            else "final"
        )

    @staticmethod
    def _request_clarification(state: RagGraphState) -> RagGraphState:
        return {
            "graph_path": [
                *state.get("graph_path", []),
                "request_clarification",
            ]
        }

    @staticmethod
    def _finalize_result(state: RagGraphState) -> RagGraphState:
        return {
            "graph_path": [*state.get("graph_path", []), "finalize_result"]
        }


def create_langgraph_rag_workflow(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
    memory_enabled: bool | None = None,
) -> LangGraphRagWorkflow:
    """Build the default RAG and expose it through a compiled LangGraph."""

    orchestrator = create_rag_orchestrator(
        project_root=project_root,
        env_file=env_file,
    )
    return LangGraphRagWorkflow(
        orchestrator,
        memory_enabled=memory_enabled,
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
