
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict, List
from uuid import uuid4

from .engine.models import (
    GraphCreateRequest,
    GraphRunRequest,
    GraphStateResponse,
    GraphCreateResponse,
    GraphRunResponse,
)
from .engine.graph_engine import GraphEngine
from .engine.tools import ToolRegistry, register_code_review_tools_and_graph


app = FastAPI(title="Minimal Workflow / Graph Engine", version="0.1.0")

# Basic CORS to make life easier if you ever add a frontend later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global in‑memory singletons (simple for an assignment) ---

tool_registry = ToolRegistry()
graph_engine = GraphEngine(tool_registry=tool_registry)

# Register built‑in tools and an example graph on startup
@app.on_event("startup")
def startup_event() -> None:
    register_code_review_tools_and_graph(graph_engine, tool_registry)


# --------- API ROUTES ---------


@app.post("/graph/create", response_model=GraphCreateResponse)
def create_graph(payload: GraphCreateRequest) -> GraphCreateResponse:
    \"""
    Create a new workflow graph from a simple JSON description.
    \"""
    try:
        graph_id = graph_engine.create_graph(payload)
        return GraphCreateResponse(graph_id=graph_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/graph/run", response_model=GraphRunResponse)
def run_graph(payload: GraphRunRequest) -> GraphRunResponse:
    \"""
    Run a previously created graph from a given initial state.
    This executes synchronously until completion (or until max_steps is hit).
    \"""
    try:
        run_id, final_state, log = graph_engine.run_graph(
            graph_id=payload.graph_id,
            initial_state=payload.initial_state,
            max_steps=payload.max_steps,
        )
        return GraphRunResponse(run_id=run_id, final_state=final_state, log=log)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Graph with id '{payload.graph_id}' not found",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/graph/state/{run_id}", response_model=GraphStateResponse)
def get_graph_state(run_id: str) -> GraphStateResponse:
    \"""
    Return the current state and execution log for a (possibly completed) run.
    \"""
    try:
        run_state = graph_engine.get_run_state(run_id)
        return run_state
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Run with id '{run_id}' not found",
        )


@app.get("/")
def root() -> Dict[str, Any]:
    \"""
    Convenience root endpoint.
    \"""
    return {
        "message": "Workflow Engine is running",
        "docs": "/docs",
        "example_graph_id_hint": "On startup, an example 'code_review' graph is registered. Use /graph/run with that ID.",
        "available_graph_ids": list(graph_engine.graphs.keys()),
    }
