"""
BARA Backend – API Path Normalization.

Provides utilities to normalize and compare API paths for mismatch detection.
"""
from __future__ import annotations
import re

# Match FastAPI-style path parameters: {id}, {user_id}, {slug}
_PATH_PARAM_RE = re.compile(r"\{[^}]+\}")

# Match what looks like a pure numeric segment (likely a concrete ID)
_NUMERIC_SEGMENT_RE = re.compile(r"^\d+$")

# Match UUID-like segment
_UUID_SEGMENT_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def normalize_path(path: str) -> str:
    """
    Return a canonical form of *path* suitable for comparison.

    Rules applied:
    1. Strip leading/trailing whitespace.
    2. Ensure the path starts with '/'.
    3. Remove trailing slash (except for root '/').
    4. Replace path-parameter placeholders ({id}, {user_id} …) with `:param`.
    5. Replace pure-numeric segments and UUID segments with `:param`
       (so frontend `/api/users/123` matches backend `/api/users/{id}`).
    """
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Replace {param} style (FastAPI / Spring / C#)
    path = _PATH_PARAM_RE.sub(":param", path)

    # Replace [param] style (Next.js / Nuxt)
    path = re.sub(r"\[[^\]]+\]", ":param", path)

    # Replace :paramName style (Express.js / REST)
    path = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", ":param", path)

    # Replace numeric / UUID segments
    segments = path.split("/")
    normalized = []
    for seg in segments:
        if _NUMERIC_SEGMENT_RE.match(seg) or _UUID_SEGMENT_RE.match(seg):
            normalized.append(":param")
        else:
            normalized.append(seg)

    return "/".join(normalized)


def paths_match(path_a: str, path_b: str) -> bool:
    """Return True if both paths normalize to the same canonical form."""
    return normalize_path(path_a) == normalize_path(path_b)
