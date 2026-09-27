"""
BARA Backend – Modern Frontend API Call Analyzer.

Extracts API calls from:
- fetch()
- axios, axios.get/post/put/delete, custom client instances (api, client, request, etc.)
- XMLHttpRequest
- React Query / TanStack Query (useQuery, useMutation)
- SWR (useSWR)
- GraphQL / Apollo Client
- Helper functions and custom API services
"""
from __future__ import annotations
import re
import os
from typing import List, Optional, Tuple

from app.models.analysis import ApiCall

# ─────────────────────────────────────────────────────────────────────────────
# Regex Patterns
# ─────────────────────────────────────────────────────────────────────────────

# fetch("/api/path") or fetch('/api/path', opts)
_FETCH_RE = re.compile(
    r"""\bfetch\s*\(\s*(?P<url>['"`][^'"`]+['"`])"""
    r"""(?:\s*,\s*\{(?P<opts>[^}]*(?:\{[^}]*\}[^}]*)*)\})?\s*\)""",
    re.DOTALL,
)

# axios.METHOD("url") or client.METHOD("url")
_AXIOS_RE = re.compile(
    r"""\b(?P<client>axios|api|client|http|request|instance|service|authService|userService)\s*\.\s*"""
    r"""(?P<method>get|post|put|patch|delete)\s*\(\s*"""
    r"""(?P<url>['"`][^'"`]+['"`])"""
    r"""(?:\s*,\s*(?P<body>\{[^}]*(?:\{[^}]*\}[^}]*)*\}))?\s*\)""",
    re.DOTALL | re.IGNORECASE,
)

# axios({ method: 'post', url: '/api/path' })
_AXIOS_CONFIG_RE = re.compile(
    r"""\baxios\s*\(\s*\{(?P<config>[^}]+)\}\s*\)""",
    re.DOTALL | re.IGNORECASE,
)

# XMLHttpRequest: xhr.open("GET", "/api/path")
_XHR_RE = re.compile(
    r"""\b\w+\.open\s*\(\s*['"`](?P<method>GET|POST|PUT|DELETE|PATCH)['"`]\s*,\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# SWR: useSWR('/api/user', fetcher)
_SWR_RE = re.compile(
    r"""\buseSWR\s*(?:<[^>]+>)?\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
)

# TanStack / React Query: useQuery({ queryKey: ['/api/user'], ... }) or useQuery(['/api/user'], ...)
_REACT_QUERY_RE = re.compile(
    r"""\buseQuery\s*(?:<[^>]+>)?\s*\(\s*\{[^}]*queryKey\s*:\s*\[[^\]]*?(?P<url>['"`]/[^'"`]+['"`])""",
    re.DOTALL,
)
_REACT_QUERY_KEY_RE = re.compile(
    r"""\buseQuery\s*(?:<[^>]+>)?\s*\(\s*\[[^\]]*?(?P<url>['"`]/[^'"`]+['"`])""",
)

# Ky: ky.get('/api/users')
_KY_RE = re.compile(
    r"""\bky\s*\.\s*(?P<method>get|post|put|patch|delete)\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# Got: got.get('/api/users') or got('/api/users')
_GOT_RE = re.compile(
    r"""\bgot\s*(?:\.\s*(?P<method>get|post|put|patch|delete))?\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# SuperAgent: superagent.get('/api/users')
_SUPERAGENT_RE = re.compile(
    r"""\b(?:superagent|request)\s*\.\s*(?P<method>get|post|put|patch|delete)\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# WebSocket: new WebSocket('ws://...')
_WS_RE = re.compile(
    r"""\bnew\s+WebSocket\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# Socket.IO: io('http://...') or io('/ws')
_SOCKETIO_RE = re.compile(
    r"""\b(?:io|socketio)\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# EventSource: new EventSource('/sse')
_EVENTSOURCE_RE = re.compile(
    r"""\bnew\s+EventSource\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# GraphQL / Apollo / graphql-request: gql`query { ... }` or useQuery(GET_USERS)
_GQL_TAG_RE = re.compile(
    r"""(?:gql|graphql)\s*`(?P<gql>[^`]+)`""",
    re.DOTALL,
)
_GQL_REQ_RE = re.compile(
    r"""\b(?:request|graphqlClient\.request)\s*\(\s*(?P<url>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

# Method from options
_METHOD_RE = re.compile(r"""method\s*:\s*['"`](?P<method>[A-Z]+)['"`]""", re.IGNORECASE)
_URL_IN_CONFIG_RE = re.compile(r"""url\s*:\s*(?P<url>['"`][^'"`]+['"`])""", re.IGNORECASE)

# Body extraction
_BODY_FIELDS_RE = re.compile(r"""JSON\.stringify\s*\(\s*\{([^}]*)\}""")
_INLINE_BODY_RE = re.compile(r"""body\s*:\s*(?:JSON\.stringify\s*\(\s*)?\{([^}]*)\}""", re.DOTALL)
_FETCH_OPTION_KEYS = {
    "method", "headers", "body", "mode", "credentials", "cache",
    "redirect", "referrer", "referrerPolicy", "integrity", "keepalive",
    "signal", "Content-Type", "Authorization", "Accept",
}

# Query params
_QUERY_PARAM_RE = re.compile(r"""(\w+)=""")
_RESP_FIELD_RE = re.compile(r"""(?:data|response|res|result)\s*\.\s*(\w+)""")
_TEMPLATE_EXPR_RE = re.compile(r"\$\{[^}]*\}")


def _strip_quotes(s: str) -> str:
    return s.strip("'\"`")


def _line_number(source: str, pos: int) -> int:
    return source[:pos].count("\n") + 1


def _get_evidence(source: str, line_no: int) -> str:
    lines = source.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


def _find_calling_context(source: str, pos: int) -> Optional[str]:
    """Find the enclosing function, hook, or component name."""
    snippet = source[max(0, pos - 500) : pos]
    matches = list(
        re.finditer(
            r"""(?:(?:export\s+)?(?:default\s+)?(?:function|class)\s+(?P<name>[A-Za-z0-9_]+)|"""
            r"""(?:const|let|var)\s+(?P<vname>[A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>)""",
            snippet,
        )
    )
    if matches:
        last = matches[-1]
        return last.group("name") or last.group("vname")
    return None


def _extract_url_and_query(raw_url: str) -> Tuple[str, List[str], bool]:
    """Return (normalized_path, [query_params], is_external)."""
    url = _strip_quotes(raw_url)
    is_external = False

    if url.startswith("http://") or url.startswith("https://"):
        is_external = True
        if "?" in url:
            path, qs = url.split("?", 1)
            params = _QUERY_PARAM_RE.findall(qs)
        else:
            path = url
            params = []
        return path.rstrip("/"), params, is_external

    # Normalize template literal expressions ${id} to :param
    url = _TEMPLATE_EXPR_RE.sub(":param", url)

    if "?" in url:
        path, qs = url.split("?", 1)
        params = _QUERY_PARAM_RE.findall(qs)
    else:
        path = url
        params = []

    return path.rstrip("/") or "/", params, is_external


def _extract_body_fields(body_text: str) -> List[str]:
    inner = ""
    m = _BODY_FIELDS_RE.search(body_text)
    if m:
        inner = m.group(1)
    else:
        bm = _INLINE_BODY_RE.search(body_text)
        if bm:
            inner = bm.group(1)
        elif body_text.strip().startswith("{"):
            inner = body_text.strip()[1:-1]

    if inner:
        fields: List[str] = []
        for part in inner.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                field = part.split(":", 1)[0].strip().strip("'\"")
            else:
                field = part.split()[0].strip().strip("'\"") if part.split() else ""
            if (
                field
                and field not in _FETCH_OPTION_KEYS
                and re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", field)
            ):
                if field not in fields:
                    fields.append(field)
        return fields
    return []


def analyze_frontend_file(
    filepath: str,
    source: str,
    env_resolver: Optional[Any] = None,
) -> List[ApiCall]:
    """Parse *source* (JS/TS) and return all detected API calls."""
    calls: List[ApiCall] = []

    # 1. --- fetch() ---
    for m in _FETCH_RE.finditer(source):
        raw_url = m.group("url")
        opts = m.group("opts") or ""
        path, query_params, is_external = _extract_url_and_query(raw_url)

        mm = _METHOD_RE.search(opts)
        method = mm.group("method").upper() if mm else "GET"

        fetch_span = source[m.start() : m.end() + 20]
        body_fields = _extract_body_fields(fetch_span) if opts else []

        end = m.end()
        nearby = source[end : end + 500]
        resp_fields = list(dict.fromkeys(_RESP_FIELD_RE.findall(nearby)))
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())

        calls.append(
            ApiCall(
                method=method,
                path=path,
                query_params=query_params,
                body_fields=body_fields,
                response_fields=resp_fields,
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="fetch",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 2. --- axios.METHOD() / client.METHOD() ---
    for m in _AXIOS_RE.finditer(source):
        raw_method = m.group("method").upper()
        raw_url = m.group("url")
        client_name = m.group("client")
        body_text = m.group("body") or ""
        path, query_params, is_external = _extract_url_and_query(raw_url)
        body_fields = _extract_body_fields(body_text)

        end = m.end()
        nearby = source[end : end + 500]
        resp_fields = list(dict.fromkeys(_RESP_FIELD_RE.findall(nearby)))
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())

        framework = "axios" if client_name.lower() == "axios" else "custom-client"

        calls.append(
            ApiCall(
                method=raw_method,
                path=path,
                query_params=query_params,
                body_fields=body_fields,
                response_fields=resp_fields,
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework=framework,
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 3. --- axios({ method: '...', url: '...' }) ---
    for m in _AXIOS_CONFIG_RE.finditer(source):
        config = m.group("config")
        url_m = _URL_IN_CONFIG_RE.search(config)
        if url_m:
            raw_url = url_m.group("url")
            path, query_params, is_external = _extract_url_and_query(raw_url)
            mm = _METHOD_RE.search(config)
            method = mm.group("method").upper() if mm else "GET"
            body_fields = _extract_body_fields(config)
            line_no = _line_number(source, m.start())
            ctx = _find_calling_context(source, m.start())

            calls.append(
                ApiCall(
                    method=method,
                    path=path,
                    query_params=query_params,
                    body_fields=body_fields,
                    response_fields=[],
                    source_file=filepath,
                    line_number=line_no,
                    calling_context=ctx,
                    framework="axios",
                    confidence="high",
                    evidence=_get_evidence(source, line_no),
                    is_external=is_external,
                )
            )

    # 4. --- XMLHttpRequest ---
    for m in _XHR_RE.finditer(source):
        method = m.group("method").upper()
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())

        calls.append(
            ApiCall(
                method=method,
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="XMLHttpRequest",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 5. --- SWR (useSWR) ---
    for m in _SWR_RE.finditer(source):
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())

        calls.append(
            ApiCall(
                method="GET",
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="swr",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 6. --- React Query / TanStack Query ---
    for r_re in (_REACT_QUERY_RE, _REACT_QUERY_KEY_RE):
        for m in r_re.finditer(source):
            raw_url = m.group("url")
            path, query_params, is_external = _extract_url_and_query(raw_url)
            line_no = _line_number(source, m.start())
            ctx = _find_calling_context(source, m.start())

            calls.append(
                ApiCall(
                    method="GET",
                    path=path,
                    query_params=query_params,
                    body_fields=[],
                    response_fields=[],
                    source_file=filepath,
                    line_number=line_no,
                    calling_context=ctx,
                    framework="react-query",
                    confidence="high",
                    evidence=_get_evidence(source, line_no),
                    is_external=is_external,
                )
            )

    # 7. --- Ky ---
    for m in _KY_RE.finditer(source):
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())
        method = m.group("method").upper()
        if env_resolver:
            path = env_resolver.resolve_call_path(path, filepath)

        calls.append(
            ApiCall(
                method=method,
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="ky",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 8. --- Got ---
    for m in _GOT_RE.finditer(source):
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())
        method = (m.group("method") or "GET").upper()
        if env_resolver:
            path = env_resolver.resolve_call_path(path, filepath)

        calls.append(
            ApiCall(
                method=method,
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="got",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 9. --- SuperAgent ---
    for m in _SUPERAGENT_RE.finditer(source):
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())
        method = m.group("method").upper()
        if env_resolver:
            path = env_resolver.resolve_call_path(path, filepath)

        calls.append(
            ApiCall(
                method=method,
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="superagent",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 10. --- WebSocket ---
    for m in _WS_RE.finditer(source):
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())

        calls.append(
            ApiCall(
                method="WS",
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="WebSocket",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 11. --- Socket.IO ---
    for m in _SOCKETIO_RE.finditer(source):
        raw_url = m.group("url") or "'/socket.io'"
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())

        calls.append(
            ApiCall(
                method="WS",
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="Socket.IO",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 12. --- EventSource ---
    for m in _EVENTSOURCE_RE.finditer(source):
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())

        calls.append(
            ApiCall(
                method="GET",
                path=path,
                query_params=query_params,
                body_fields=[],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="EventSource",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # 13. --- GraphQL Request ---
    for m in _GQL_REQ_RE.finditer(source):
        raw_url = m.group("url")
        path, query_params, is_external = _extract_url_and_query(raw_url)
        line_no = _line_number(source, m.start())
        ctx = _find_calling_context(source, m.start())
        if env_resolver:
            path = env_resolver.resolve_call_path(path, filepath)

        calls.append(
            ApiCall(
                method="POST",
                path=path,
                query_params=query_params,
                body_fields=["query"],
                response_fields=[],
                source_file=filepath,
                line_number=line_no,
                calling_context=ctx,
                framework="graphql-request",
                confidence="high",
                evidence=_get_evidence(source, line_no),
                is_external=is_external,
            )
        )

    # If env_resolver is present, adjust paths for any relative fetch/axios/swr/react-query calls
    if env_resolver:
        for c in calls:
            if not c.is_external and not c.path.startswith("ws://") and not c.path.startswith("wss://"):
                c.path = env_resolver.resolve_call_path(c.path, filepath)

    return calls


def analyze_frontend_files(
    project_root: str,
    frontend_files: List[str],
    env_resolver: Optional[Any] = None,
) -> List[ApiCall]:
    """Analyze all frontend files and return aggregated API calls."""
    all_calls: List[ApiCall] = []
    for rel_path in frontend_files:
        full_path = os.path.join(project_root, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            calls = analyze_frontend_file(rel_path, source, env_resolver=env_resolver)
            all_calls.extend(calls)
        except OSError:
            pass
    return all_calls

