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
# Also detect shorthand properties: { username, email } (no colon)
_SHORTHAND_FIELD_RE = re.compile(r"""\b(\w+)\s*[,}]""")

# Known non-body option keys to skip when parsing fetch options object
_FETCH_OPTION_KEYS = {
    "method", "headers", "body", "mode", "credentials", "cache",
    "redirect", "referrer", "referrerPolicy", "integrity", "keepalive",
    "signal", "Content-Type", "Authorization", "Accept",
}

# Extract inline body object: body: { key: val, ... }
_INLINE_BODY_RE = re.compile(r"""body\s*:\s*(?:JSON\.stringify\s*\(\s*)?\{([^}]*)\}""", re.DOTALL)

# Extract query params from URL ?key=val&key2=val2
_QUERY_RE = re.compile(r"""\?([^'"` ]+)""")
_QUERY_PARAM_RE = re.compile(r"""(\w+)=""")

# Extract response field usage: data.field or response.field
_RESP_FIELD_RE = re.compile(r"""(?:data|response|res|result)\s*\.\s*(\w+)""")


def _strip_quotes(s: str) -> str:
    return s.strip("'\"`")


# Replace template literal interpolations ${...} with :param
_TEMPLATE_EXPR_RE = re.compile(r"\$\{[^}]*\}")


def _extract_url_and_query(raw_url: str):
    """Return (path_without_query, [query_param_names])."""
    url = _strip_quotes(raw_url)
    # Normalize template literal expressions to :param
    url = _TEMPLATE_EXPR_RE.sub(":param", url)
    if "?" in url:
        path, qs = url.split("?", 1)
        params = _QUERY_PARAM_RE.findall(qs)
    else:
        path = url
        params = []
    return path.rstrip("/") or "/", params


def _extract_body_fields(body_text: str) -> List[str]:
    """Extract field names from a request body (JSON.stringify or inline object).

    For fetch() opts strings, look specifically inside body: {...} to avoid
    picking up option keys like 'method', 'headers', etc.
    """
    # 1. Try JSON.stringify({...}) anywhere in the text
    m = _BODY_FIELDS_RE.search(body_text)
    if m:
        inner = m.group(1)
        colon_fields = [f for f in _FIELD_NAME_RE.findall(inner)
                        if f not in _FETCH_OPTION_KEYS]
        if colon_fields:
            return colon_fields
        # Shorthand syntax: JSON.stringify({ username, email })
        return [f for f in _SHORTHAND_FIELD_RE.findall(inner)
                if f not in _FETCH_OPTION_KEYS]

    # 2. Try body: { ... } inline object (for fetch opts)
    bm = _INLINE_BODY_RE.search(body_text)
    if bm:
        return [f for f in _FIELD_NAME_RE.findall(bm.group(1))
                if f not in _FETCH_OPTION_KEYS]

    # 3. If the whole text looks like a plain object (axios body), parse it
    #    but skip known fetch option keys
    if body_text.strip().startswith("{"):
        return [f for f in _FIELD_NAME_RE.findall(body_text)
                if f not in _FETCH_OPTION_KEYS]

    return []


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

        # Body fields – search the full fetch call span so nested braces are included
        fetch_span = source[m.start():m.end() + 20]
        body_fields = _extract_body_fields(fetch_span) if opts else []

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
