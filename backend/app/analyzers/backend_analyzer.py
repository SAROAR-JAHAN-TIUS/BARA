"""
BARA Backend – Backend (FastAPI) Analyzer.

Extracts route definitions from Python source files.
"""
from __future__ import annotations
import re
import os
import ast
from typing import List, Optional, Dict

from app.models.analysis import ApiEndpoint

# ---------------------------------------------------------------------------
# Regex patterns for decorator-based route detection
# ---------------------------------------------------------------------------

# Matches: @app.get("/path"), @router.post("/path"), @api_router.put(...)
_ROUTE_DECORATOR_RE = re.compile(
    r"""@\w+\s*\.\s*(?P<method>get|post|put|patch|delete)\s*\(\s*"""
    r"""(?P<path>['"][^'"]+['"])""",
    re.IGNORECASE,
)

# Pydantic model field: field_name: Type (= default)?
_PYDANTIC_FIELD_RE = re.compile(r"""^\s{4,}(\w+)\s*:\s*\w""", re.MULTILINE)

# Class definition
_CLASS_DEF_RE = re.compile(r"""^class\s+(\w+)\s*\(""", re.MULTILINE)


def _line_number(source: str, pos: int) -> int:
    return source[:pos].count("\n") + 1


def _extract_pydantic_models(source: str) -> Dict[str, List[str]]:
    """
    Parse the source file and extract Pydantic model class → field names.
    Uses AST for reliability.
    """
    models: Dict[str, List[str]] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return models

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Only consider classes that inherit from BaseModel / something
        fields: List[str] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append(item.target.id)
        if fields:
            models[node.name] = fields
    return models


def _infer_fields_from_function(source: str, func_start_pos: int) -> List[str]:
    """
    Look at the function signature right after a route decorator and
    extract Pydantic model parameter types.
    """
    # Find function signature from func_start_pos
    snippet = source[func_start_pos : func_start_pos + 600]
    # Look for `def func_name(... body: ModelName ...)`
    sig_match = re.search(r"""def\s+\w+\s*\(([^)]*)\)""", snippet, re.DOTALL)
    if not sig_match:
        return []
    sig = sig_match.group(1)
    # Extract `param: ModelName` pairs where param is not common FastAPI params
    param_re = re.compile(r"""(\w+)\s*:\s*(\w+)""")
    skip_types = {
        "str", "int", "float", "bool", "list", "dict", "Optional",
        "Response", "Request", "Session", "HTTPException",
        "BackgroundTasks", "Depends",
    }
    model_params = []
    for pm in param_re.finditer(sig):
        pname, ptype = pm.group(1), pm.group(2)
        if pname in ("self", "cls"):
            continue
        if ptype not in skip_types:
            model_params.append(ptype)
    return model_params


def analyze_backend_file(filepath: str, source: str) -> List[ApiEndpoint]:
    """Parse *source* (Python) and return all detected route endpoints."""
    endpoints: List[ApiEndpoint] = []
    pydantic_models = _extract_pydantic_models(source)

    # Find all route decorators
    for m in _ROUTE_DECORATOR_RE.finditer(source):
        method = m.group("method").upper()
        raw_path = m.group("path").strip("'\"")
        line_no = _line_number(source, m.start())

        # Normalize path
        path = raw_path.rstrip("/") or "/"

        # Find what Pydantic model(s) the handler uses
        request_model: Optional[str] = None
        request_fields: List[str] = []
        response_model: Optional[str] = None
        response_fields: List[str] = []

        # Look ahead for the function definition
        model_params = _infer_fields_from_function(source, m.end())
        if model_params:
            # First model param is assumed to be the request body
            request_model = model_params[0]
            request_fields = pydantic_models.get(request_model, [])

        # Look for response_model= in the decorator
        resp_m = re.search(r"""response_model\s*=\s*(\w+)""", source[m.start():m.end() + 200])
        if resp_m:
            response_model = resp_m.group(1)
            response_fields = pydantic_models.get(response_model, [])

        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                request_model=request_model,
                request_fields=request_fields,
                response_model=response_model,
                response_fields=response_fields,
                source_file=filepath,
                line_number=line_no,
            )
        )

    return endpoints


def analyze_backend_files(project_root: str, backend_files: List[str]) -> List[ApiEndpoint]:
    """Analyze all backend files and return aggregated endpoints."""
    all_endpoints: List[ApiEndpoint] = []
    for rel_path in backend_files:
        full_path = os.path.join(project_root, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            eps = analyze_backend_file(rel_path, source)
            all_endpoints.extend(eps)
        except OSError:
            pass
    return all_endpoints
