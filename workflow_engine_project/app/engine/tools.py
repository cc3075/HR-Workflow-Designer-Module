
from __future__ import annotations

from typing import Any, Callable, Dict, List
from dataclasses import dataclass
import statistics


ToolFn = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class Tool:
    name: str
    fn: ToolFn
    description: str = ""


class ToolRegistry:
    """
    Very small tool registry. Maps string names to Python callables.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, fn: ToolFn, description: str = "") -> None:
        self._tools[name] = Tool(name=name, fn=fn, description=description)

    def get(self, name: str) -> ToolFn:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name].fn

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())


# ---------- Example: Code Review Mini-Agent (Option A) ----------


def extract_functions_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Very small 'parser': we treat any line starting with 'def ' as a function.
    """
    code = state.get("code", "")
    lines = code.splitlines()
    functions: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def ") and "(" in stripped:
            # function name is between "def " and "("
            name = stripped[4 : stripped.index("(")].strip()
            if name:
                functions.append(name)

    state["functions"] = functions
    state.setdefault("metadata", {})["num_functions"] = len(functions)
    return state


def check_complexity_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fake complexity metric: function name length + a small penalty
    for functions with underscores (pretend that's 'cyclomatic complexity').
    """
    functions: List[str] = state.get("functions", [])
    complexities: Dict[str, int] = {}

    for fn_name in functions:
        penalty = fn_name.count("_")
        complexities[fn_name] = len(fn_name) + penalty

    state["complexity"] = complexities
    return state


def detect_basic_issues_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rule-based 'lint' check on the raw source code.
    """
    code = state.get("code", "")
    issues: List[str] = []

    if "\t" in code:
        issues.append("Tabs found; prefer spaces for indentation.")
    if "print(" in code:
        issues.append("Debug prints found; consider using a logger.")
    if "TODO" in code:
        issues.append("TODO comments found; make sure they are resolved.")
    if len(code.splitlines()) > 200:
        issues.append("File is quite long; consider splitting into modules.")

    state["issues"] = issues
    return state


def suggest_improvements_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate naive suggestions based on complexity and issues.
    """
    complexities: Dict[str, int] = state.get("complexity", {})
    issues: List[str] = state.get("issues", [])
    suggestions: List[str] = state.get("suggestions", [])

    # Complexity based suggestions
    for fn_name, score in complexities.items():
        if score > 15:
            suggestions.append(
                f"Function '{fn_name}' looks complex (score={score}). "
                "Consider refactoring into smaller helpers."
            )

    # Issue based suggestions
    for issue in issues:
        suggestions.append(f"Address issue: {issue}")

    # Generic suggestion to add docstrings
    functions: List[str] = state.get("functions", [])
    for fn_name in functions:
        suggestions.append(
            f"Ensure '{fn_name}' has a clear docstring explaining inputs and outputs."
        )

    state["suggestions"] = suggestions
    return state


def quality_gate_tool(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a simple quality score and decide whether to loop.

    - Start from base 1.0
    - Subtract 0.1 for each 'complex' function (complexity > 15)
    - Subtract 0.15 for each issue
    - Clamp between 0 and 1

    If quality_score < threshold (default 0.8), we loop back by setting
    state["_next_node"] = "suggest_improvements".
    Otherwise we end the workflow.
    """
    complexities: Dict[str, int] = state.get("complexity", {})
    issues: List[str] = state.get("issues", [])
    threshold: float = float(state.get("threshold", 0.8))

    complex_functions = [name for name, score in complexities.items() if score > 15]

    base_score = 1.0
    penalty_complex = 0.1 * len(complex_functions)
    penalty_issues = 0.15 * len(issues)

    quality_score = base_score - penalty_complex - penalty_issues
    quality_score = max(0.0, min(1.0, quality_score))

    state["quality_score"] = round(quality_score, 3)
    state["metadata"] = state.get("metadata", {})
    state["metadata"]["complex_functions"] = complex_functions

    if quality_score < threshold:
        # Ask graph engine to loop back to suggestions node
        state["_next_node"] = "suggest_improvements"
    else:
        state["_next_node"] = None

    return state


def register_code_review_tools_and_graph(engine, registry: ToolRegistry) -> str:
    """
    Register the tools and an example graph for the 'Code Review Mini-Agent'.

    The resulting graph roughly does:
        extract_functions -> check_complexity -> detect_basic_issues ->
        suggest_improvements -> quality_gate -> (loop back or stop)
    """
    # 1) Register tools
    registry.register(
        "extract_functions",
        extract_functions_tool,
        description="Extract function names from Python source code.",
    )
    registry.register(
        "check_complexity",
        check_complexity_tool,
        description="Compute a toy complexity metric for each function.",
    )
    registry.register(
        "detect_basic_issues",
        detect_basic_issues_tool,
        description="Detect simple style issues in the source code.",
    )
    registry.register(
        "suggest_improvements",
        suggest_improvements_tool,
        description="Generate naive suggestions to improve the code.",
    )
    registry.register(
        "quality_gate",
        quality_gate_tool,
        description="Compute a quality score and decide whether to loop.",
    )

    # 2) Define graph using the engine's request model
    from .models import NodeDefinition, GraphCreateRequest

    nodes = [
        NodeDefinition(id="extract_functions", tool_name="extract_functions"),
        NodeDefinition(id="check_complexity", tool_name="check_complexity"),
        NodeDefinition(id="detect_basic_issues", tool_name="detect_basic_issues"),
        NodeDefinition(id="suggest_improvements", tool_name="suggest_improvements"),
        NodeDefinition(id="quality_gate", tool_name="quality_gate"),
    ]

    # Basic linear flow; 'quality_gate' decides whether to loop back
    edges = {
        "extract_functions": "check_complexity",
        "check_complexity": "detect_basic_issues",
        "detect_basic_issues": "suggest_improvements",
        "suggest_improvements": "quality_gate",
        "quality_gate": None,  # terminal unless quality_gate overrides using _next_node
    }

    req = GraphCreateRequest(
        name="code_review",
        start_node_id="extract_functions",
        nodes=nodes,
        edges=edges,
    )

    graph_id = engine.create_graph(req)
    return graph_id
