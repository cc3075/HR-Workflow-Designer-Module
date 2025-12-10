
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


# ---------- Graph Definition Models ----------


class NodeDefinition(BaseModel):
    """
    A node in the workflow graph.

    Each node is tied to a tool name, which is looked up in the ToolRegistry.
    """
    id: str = Field(..., description="Unique ID of the node in the graph")
    tool_name: str = Field(..., description="Name of the tool function to invoke")


class GraphCreateRequest(BaseModel):
    """
    Request body for POST /graph/create.
    """
    name: str = Field(..., description="Human friendly name of the graph")
    start_node_id: str = Field(..., description="ID of the first node to run")
    nodes: List[NodeDefinition]
    edges: Dict[str, Optional[str]] = Field(
        ...,
        description="Mapping from node_id -> next_node_id (use null for terminal nodes)",
    )


class GraphCreateResponse(BaseModel):
    graph_id: str


class GraphRunRequest(BaseModel):
    """
    Request body for POST /graph/run.
    """
    graph_id: str
    initial_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary JSON-serialisable state passed into the workflow",
    )
    max_steps: int = Field(
        default=50,
        description="Safety limit to avoid infinite loops",
        ge=1,
        le=1000,
    )


class ExecutionStep(BaseModel):
    """
    A single node execution in the log.
    """
    step_index: int
    node_id: str
    tool_name: str
    input_state: Dict[str, Any]
    output_state: Dict[str, Any]


class GraphRunResponse(BaseModel):
    """
    Response from POST /graph/run.
    """
    run_id: str
    final_state: Dict[str, Any]
    log: List[ExecutionStep]


# ---------- Run State Query Model ----------


class GraphStateResponse(BaseModel):
    """
    Response from GET /graph/state/{run_id}.
    """
    run_id: str
    graph_id: str
    status: Literal["running", "completed", "failed"]
    current_node_id: Optional[str]
    state: Dict[str, Any]
    log: List[ExecutionStep]
    error: Optional[str] = None
