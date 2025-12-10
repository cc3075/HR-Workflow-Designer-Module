
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4
from copy import deepcopy

from .models import (
    GraphCreateRequest,
    ExecutionStep,
    GraphStateResponse,
)
from .tools import ToolRegistry


@dataclass
class Graph:
    """
    Simple in-memory representation of a workflow graph.
    """
    id: str
    name: str
    start_node_id: str
    nodes: Dict[str, str]  # node_id -> tool_name
    edges: Dict[str, Optional[str]]  # node_id -> next_node_id (or None)


@dataclass
class RunRecord:
    """
    A single run of a graph stored in memory.
    """
    id: str
    graph_id: str
    state: Dict[str, Any]
    current_node_id: Optional[str]
    log: List[ExecutionStep]
    status: str
    error: Optional[str] = None


class GraphEngine:
    """
    Minimal graph engine that:
      * keeps graphs and run records in memory
      * executes nodes sequentially
      * supports simple loops and branching via the state["_next_node"] convention
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry
        self.graphs: Dict[str, Graph] = {}
        self.runs: Dict[str, RunRecord] = {}

    # ---------- Graph Management ----------

    def create_graph(self, req: GraphCreateRequest) -> str:
        """
        Register a new graph in memory.
        """
        # Basic validation
        node_ids = {n.id for n in req.nodes}
        if req.start_node_id not in node_ids:
            raise ValueError("start_node_id must be one of the node IDs")

        for src, dst in req.edges.items():
            if src not in node_ids:
                raise ValueError(f"Edge source '{src}' is not a valid node id")
            if dst is not None and dst not in node_ids:
                raise ValueError(f"Edge target '{dst}' is not a valid node id")

        graph_id = str(uuid4())
        nodes = {n.id: n.tool_name for n in req.nodes}
        edges = req.edges

        graph = Graph(
            id=graph_id,
            name=req.name,
            start_node_id=req.start_node_id,
            nodes=nodes,
            edges=edges,
        )
        self.graphs[graph_id] = graph
        return graph_id

    # ---------- Execution ----------

    def run_graph(
        self,
        graph_id: str,
        initial_state: Dict[str, Any],
        max_steps: int = 50,
    ) -> Tuple[str, Dict[str, Any], List[ExecutionStep]]:
        """
        Execute a graph from start to finish synchronously.
        Returns (run_id, final_state, execution_log).
        """
        if graph_id not in self.graphs:
            raise KeyError(graph_id)

        graph = self.graphs[graph_id]
        run_id = str(uuid4())
        state: Dict[str, Any] = deepcopy(initial_state)
        log: List[ExecutionStep] = []

        run_record = RunRecord(
            id=run_id,
            graph_id=graph_id,
            state=deepcopy(state),
            current_node_id=graph.start_node_id,
            log=[],
            status="running",
        )
        self.runs[run_id] = run_record

        current_node_id: Optional[str] = graph.start_node_id
        step_index = 0

        try:
            for step_index in range(max_steps):
                if current_node_id is None:
                    break

                tool_name = graph.nodes[current_node_id]
                tool_fn = self.tool_registry.get(tool_name)

                # Make defensive copies so the log is easier to inspect
                input_state = deepcopy(state)
                output_state = tool_fn(deepcopy(state))

                # Either return a new state dict or mutate in place and return None
                if output_state is None:
                    output_state = state
                state = output_state

                step = ExecutionStep(
                    step_index=step_index,
                    node_id=current_node_id,
                    tool_name=tool_name,
                    input_state=input_state,
                    output_state=deepcopy(state),
                )
                log.append(step)

                # Branching / looping convention:
                # If the tool sets state["_next_node"], use that and then delete the key.
                # Otherwise fall back to the static edges mapping.
                next_node_id: Optional[str]
                if "_next_node" in state:
                    next_node_id = state.pop("_next_node")
                else:
                    next_node_id = graph.edges.get(current_node_id)

                current_node_id = next_node_id

                # Update run record after each step (for potential future async / streaming)
                run_record.state = deepcopy(state)
                run_record.current_node_id = current_node_id
                run_record.log = log.copy()

            else:
                # Loop exhausted without hitting a terminal node
                raise ValueError(
                    f"Max steps ({max_steps}) reached. "
                    "Your graph likely has an infinite loop."
                )

            run_record.status = "completed"
        except Exception as exc:  # Catch-all to mark the run as failed
            run_record.status = "failed"
            run_record.error = str(exc)
            raise

        return run_id, state, log

    # ---------- Introspection ----------

    def get_run_state(self, run_id: str) -> GraphStateResponse:
        if run_id not in self.runs:
            raise KeyError(run_id)

        r = self.runs[run_id]
        return GraphStateResponse(
            run_id=r.id,
            graph_id=r.graph_id,
            status=r.status,  # type: ignore[arg-type]
            current_node_id=r.current_node_id,
            state=r.state,
            log=r.log,
            error=r.error,
        )
