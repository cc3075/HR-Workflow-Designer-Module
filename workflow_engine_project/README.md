
# Minimal Workflow / Graph Engine (FastAPI)

This project is a **small agent workflow engine**, inspired by frameworks like LangGraph.
It is intentionally simple and focuses on:

- Clean Python structure
- State passing between nodes
- Simple edges, branching and looping
- HTTP APIs using FastAPI

It implements the assignment requirements and includes a **Code Review Mini-Agent** workflow.

---

## Project Structure

```text
workflow_engine_project/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI application + API routes
│   └── engine/
│       ├── __init__.py
│       ├── graph_engine.py   # Core graph engine
│       ├── models.py         # Pydantic models (requests / responses)
│       └── tools.py          # Tool registry + Code Review example tools
├── README.md
└── requirements.txt
```

---

## How to Run the Project

### 1. Create and activate a virtual environment (recommended)

```bash
cd workflow_engine_project

# Python 3.10+ recommended
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the FastAPI app with Uvicorn

```bash
uvicorn app.main:app --reload
```

By default, Uvicorn listens on `http://127.0.0.1:8000`.

### 4. Open the interactive API docs

Visit:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

From there you can call all endpoints without writing any extra client code.

---

## Available API Endpoints

### `POST /graph/create`

Create a new workflow graph.

**Request body example:**

```json
{
  "name": "my_simple_graph",
  "start_node_id": "step1",
  "nodes": [
    { "id": "step1", "tool_name": "extract_functions" },
    { "id": "step2", "tool_name": "quality_gate" }
  ],
  "edges": {
    "step1": "step2",
    "step2": null
  }
}
```

**Response:**

```json
{
  "graph_id": "generated-uuid"
}
```

> Note: On startup we already register a built‑in graph called `"code_review"`.
> Its actual `graph_id` is a UUID that you can see in the `/` root endpoint or in `/docs`.

---

### `POST /graph/run`

Run an existing graph from a given initial state.

**Example: Run the built‑in `code_review` graph**

1. First, start the server.
2. Open `http://127.0.0.1:8000/` – you will see the available `graph_id`s.
3. Copy the UUID corresponding to the `code_review` graph.
4. Call `POST /graph/run` from Swagger UI with a body similar to:

```json
{
  "graph_id": "PUT-YOUR-GRAPH-ID-HERE",
  "initial_state": {
    "code": "def add(a, b):\\n    return a + b\\n\\nprint(add(1, 2))",
    "threshold": 0.8
  },
  "max_steps": 20
}
```

**Response (simplified):**

```json
{
  "run_id": "run-uuid",
  "final_state": {
    "code": "...",
    "threshold": 0.8,
    "functions": ["add"],
    "complexity": {"add": 3},
    "issues": ["Debug prints found; consider using a logger."],
    "suggestions": [
      "Ensure 'add' has a clear docstring explaining inputs and outputs.",
      "Address issue: Debug prints found; consider using a logger."
    ],
    "quality_score": 0.85,
    "metadata": {
      "num_functions": 1,
      "complex_functions": []
    }
  },
  "log": [
    {
      "step_index": 0,
      "node_id": "extract_functions",
      "tool_name": "extract_functions",
      "input_state": { "...": "..." },
      "output_state": { "...": "..." }
    },
    ...
  ]
}
```

---

### `GET /graph/state/{run_id}`

Fetch the stored state and log for a specific run.

**Example:**

```bash
GET /graph/state/2e246d7d-...-...
```

**Response:**

```json
{
  "run_id": "2e246d7d-...-...",
  "graph_id": "graph-uuid",
  "status": "completed",
  "current_node_id": null,
  "state": { "...": "..." },
  "log": [ /* same log as run response */ ],
  "error": null
}
```

Even though the engine runs synchronously in this assignment,
the endpoint still works for *completed* runs and is structured
so it can later support streaming / async execution.

---

## What the Engine Supports

1. **Nodes**
   - Each node is a Python function (a "tool") that receives a shared `state: Dict[str, Any]`
     and returns a new state.
   - Nodes are registered in a `ToolRegistry`.

2. **State**
   - A simple dictionary flowing between nodes.
   - You can store anything JSON‑serialisable in it.

3. **Edges**
   - Simple mapping: `edges: { "node_id": "next_node_id", ... }`
   - `null` (or `None`) marks a terminal node.

4. **Branching & Looping (via `_next_node`)**
   - A node can set `state["_next_node"] = "some_other_node_id"` to override the default edge.
   - This allows:
     - **Branching:** choose different next nodes based on current state.
     - **Looping:** jump back to a previous node creating a loop.
   - The engine enforces a `max_steps` limit to avoid infinite loops.

5. **In-memory storage**
   - Graphs and run records are stored in memory (`dict`s).
   - This keeps the implementation small and focused for the assignment.

---

## Example Workflow Implemented (Option A: Code Review Mini-Agent)

The built‑in `code_review` workflow does:

1. `extract_functions`
2. `check_complexity`
3. `detect_basic_issues`
4. `suggest_improvements`
5. `quality_gate` (loops until `quality_score >= threshold`)

All logic is pure Python and fully rule‑based – **no ML is used**, as required.

---

## If I Had More Time, I Would Improve

- Add persistence via SQLite (SQLModel / SQLAlchemy) instead of in‑memory storage.
- Implement true **async execution** and background tasks for long‑running nodes.
- Provide a WebSocket endpoint to stream the run log step‑by‑step to a UI.
- Add richer branching logic (e.g. condition expressions or DSL instead of `_next_node`).
- Add authentication and multi‑user support for graphs and runs.
- Write unit tests for the engine and the example workflow.

---
