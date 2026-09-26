"""
BARA Backend – Frontend Analyzer.

Extracts API calls (fetch / axios) from JS/TS source files.
"""
from __future__ import annotations
import re
import os
from typing import List

from app.models.analysis import ApiCall

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# fetch("/api/path") or fetch('/api/path')
# fetch(`/api/path`)
_FETCH_RE = re.compile(
    r"""fetch\s*\(\s*(?P<url>['"`][^'"`]+['"`])"""
    r"""(?:\s*,\s*\{(?P<opts>[^}]*(?:\{[^}]*\}[^}]*)*)\})?\s*\)""",
    re.DOTALL,
)

# axios.METHOD("url") or axios.METHOD('url') or axios.METHOD(`url`)
_AXIOS_RE = re.compile(
    r"""axios\s*\.\s*(?P<method>get|post|put|patch|delete)\s*\(\s*"""
    r"""(?P<url>['"`][^'"`]+['"`])"""
    r"""(?:\s*,\s*(?P<body>\{[^}]*(?:\{[^}]*\}[^}]*)*\}))?\s*\)""",
    re.DOTALL | re.IGNORECASE,
)

# Extract method from fetch options object
_METHOD_RE = re.compile(r"""method\s*:\s*['"`](?P<method>[A-Z]+)['"`]""", re.IGNORECASE)

# Extract body fields from JSON.stringify({...})
_BODY_FIELDS_RE = re.compile(r"""JSON\.stringify\s*\(\s*\{([^}]*)\}""")
_FIELD_NAME_RE = re.compile(r"""['"]?(\w+)['"]?\s*:""")

# Extract query params from URL ?key=val&key2=val2
_QUERY_RE = re.compile(r"""\?([^'"` ]+)""")
_QUERY_PARAM_RE = re.compile(r"""(\w+)=""")

# Extract response field usage: data.field or response.field
_RESP_FIELD_RE = re.compile(r"""(?:data|response|res|result)\s*\.\s*(\w+)""")


def _strip_quotes(s: str) -> str:
    return s.strip("'\"`")


def _extract_url_and_query(raw_url: str):
    """Return (path_without_query, [query_param_names])."""
    url = _strip_quotes(raw_url)
    if "?" in url:
        path, qs = url.split("?", 1)
        params = _QUERY_PARAM_RE.findall(qs)
    else:
        path = url
        params = []
    return path.rstrip("/") or "/", params


def _extract_body_fields(body_text: str) -> List[str]:
    """Extract field names from an object literal or JSON.stringify call."""
    fields: List[str] = []
    # Look inside JSON.stringify({...})
    m = _BODY_FIELDS_RE.search(body_text)
    if m:
        fields = _FIELD_NAME_RE.findall(m.group(1))
    else:
        # Try direct object literal
        fields = _FIELD_NAME_RE.findall(body_text)
    return fields


def _line_number(source: str, pos: int) -> int:
    return source[:pos].count("\n") + 1


def analyze_frontend_file(filepath: str, source: str) -> List[ApiCall]:
    """Parse *source* (JS/TS) and return all detected API calls."""
    calls: List[ApiCall] = []

    # --- fetch() ---
    for m in _FETCH_RE.finditer(source):
        raw_url = m.group("url")
        opts = m.group("opts") or ""
        path, query_params = _extract_url_and_query(raw_url)

        # Determine method
        mm = _METHOD_RE.search(opts)
        method = mm.group("method").upper() if mm else "GET"

        # Body fields
        body_fields = _extract_body_fields(opts) if opts else []

        # Response fields (scan nearby context – up to 10 lines ahead)
        end = m.end()
        nearby = source[end : end + 500]
        resp_fields = list(dict.fromkeys(_RESP_FIELD_RE.findall(nearby)))

        calls.append(
            ApiCall(
                method=method,
                path=path,
                query_params=query_params,
                body_fields=body_fields,
                response_fields=resp_fields,
                source_file=filepath,
                line_number=_line_number(source, m.start()),
            )
        )

    # --- axios.METHOD() ---
    for m in _AXIOS_RE.finditer(source):
        raw_method = m.group("method").upper()
        raw_url = m.group("url")
        body_text = m.group("body") or ""
        path, query_params = _extract_url_and_query(raw_url)
        body_fields = _extract_body_fields(body_text)

        end = m.end()
        nearby = source[end : end + 500]
        resp_fields = list(dict.fromkeys(_RESP_FIELD_RE.findall(nearby)))

        calls.append(
            ApiCall(
                method=raw_method,
                path=path,
                query_params=query_params,
                body_fields=body_fields,
                response_fields=resp_fields,
                source_file=filepath,
                line_number=_line_number(source, m.start()),
            )
        )

    return calls


def analyze_frontend_files(project_root: str, frontend_files: List[str]) -> List[ApiCall]:
    """Analyze all frontend files and return aggregated API calls."""
    all_calls: List[ApiCall] = []
    for rel_path in frontend_files:
        full_path = os.path.join(project_root, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            calls = analyze_frontend_file(rel_path, source)
            all_calls.extend(calls)
        except OSError:
            pass  # Unreadable files are silently skipped
    return all_calls
