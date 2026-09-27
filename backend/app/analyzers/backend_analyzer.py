"""
BARA Backend – Multi-Framework Backend Analyzer.

Extracts route definitions from:
- Python: FastAPI, Flask, Django, Django REST Framework
- JavaScript / TypeScript: Express, Fastify, NestJS, Koa, Hono, Next.js API, Nuxt Server
- Java: Spring Boot, Spring MVC
- Go: net/http, Gin, Echo, Fiber
- Ruby: Rails
- PHP: Laravel, Symfony
- C#: ASP.NET Core
- Generic / Unknown Route Fallback
"""
from __future__ import annotations
import re
import os
import ast
from typing import List, Optional, Dict, Tuple

from app.models.analysis import ApiEndpoint


def _line_number(source: str, pos: int) -> int:
    return source[:pos].count("\n") + 1


def _get_evidence(source: str, line_no: int) -> str:
    lines = source.splitlines()
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# 1. Python Analyzers (FastAPI, Flask, Django)
# ─────────────────────────────────────────────────────────────────────────────

_FASTAPI_ROUTE_RE = re.compile(
    r"""@\w+\s*\.\s*(?P<method>get|post|put|patch|delete)\s*\(\s*"""
    r"""(?P<path>['"][^'"]+['"])""",
    re.IGNORECASE,
)

_FLASK_ROUTE_RE = re.compile(
    r"""@\w+\s*\.\s*route\s*\(\s*"""
    r"""(?P<path>['"][^'"]+['"])"""
    r"""(?:\s*,\s*methods\s*=\s*\[(?P<methods>[^\]]+)\])?""",
    re.IGNORECASE,
)

_DJANGO_PATH_RE = re.compile(
    r"""\b(?:path|re_path|url)\s*\(\s*"""
    r"""['"](?P<path>[^'"]+)['"]\s*,\s*"""
    r"""(?P<view>[A-Za-z0-9_.]+)""",
)

_DJANGO_ROUTER_RE = re.compile(
    r"""router\.register\s*\(\s*r?['"](?P<prefix>[^'"]+)['"]\s*,\s*(?P<viewset>\w+)""",
)


def _extract_pydantic_models(source: str) -> Dict[str, List[str]]:
    import textwrap
    models: Dict[str, List[str]] = {}
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return models

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        fields: List[str] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append(item.target.id)
        if fields:
            models[node.name] = fields
    return models


def _infer_function_info(source: str, func_start_pos: int) -> Tuple[Optional[str], List[str]]:
    snippet = source[func_start_pos : func_start_pos + 600]
    sig_match = re.search(r"""def\s+(?P<name>\w+)\s*\(([^)]*)\)""", snippet, re.DOTALL)
    if not sig_match:
        return None, []
    func_name = sig_match.group("name")
    sig = sig_match.group(2)
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
    return func_name, model_params


def _analyze_python_backend(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []
    pydantic_models = _extract_pydantic_models(source)

    # 1. FastAPI
    for m in _FASTAPI_ROUTE_RE.finditer(source):
        method = m.group("method").upper()
        raw_path = m.group("path").strip("'\"")
        line_no = _line_number(source, m.start())
        path = raw_path.rstrip("/") or "/"
        func_name, model_params = _infer_function_info(source, m.end())

        request_model = model_params[0] if model_params else None
        request_fields = pydantic_models.get(request_model, []) if request_model else []
        response_model = None
        response_fields = []
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
                controller=func_name,
                framework="FastAPI",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    # 1b. FastAPI WebSocket
    for m in re.finditer(r"""@\w+\s*\.\s*websocket\s*\(\s*(?P<path>['"][^'"]+['"])""", source, re.IGNORECASE):
        raw_path = m.group("path").strip("'\"")
        line_no = _line_number(source, m.start())
        path = raw_path.rstrip("/") or "/"
        func_name, _ = _infer_function_info(source, m.end())
        endpoints.append(
            ApiEndpoint(
                method="WS",
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=func_name,
                framework="FastAPI",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    # 1c. Python GraphQL (Strawberry, Graphene, GraphQLRouter)
    for m in re.finditer(r"""(?:GraphQLView\.as_view|GraphQLRouter\s*\([^)]*\)|add_route\s*\(\s*['"](?P<gpath>[^'"]*graphql[^'"]*)['"]|include_router\s*\([^)]*prefix\s*=\s*['"](?P<gprefix>[^'"]*graphql[^'"]*)['"])""", source, re.IGNORECASE):
        gpath = m.groupdict().get("gpath") or m.groupdict().get("gprefix") or "/graphql"
        line_no = _line_number(source, m.start())
        endpoints.append(
            ApiEndpoint(
                method="POST",
                path=gpath.rstrip("/") or "/graphql",
                source_file=filepath,
                line_number=line_no,
                controller="GraphQLHandler",
                framework="GraphQL",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    # 2. Flask
    for m in _FLASK_ROUTE_RE.finditer(source):
        raw_path = m.group("path").strip("'\"")
        line_no = _line_number(source, m.start())
        path = raw_path.rstrip("/") or "/"
        methods_str = m.group("methods")
        methods = [x.strip().strip("'\"").upper() for x in methods_str.split(",") if x.strip().strip("'\"")] if methods_str else ["GET"]
        func_name, _ = _infer_function_info(source, m.end())

        for method in methods:
            endpoints.append(
                ApiEndpoint(
                    method=method,
                    path=path,
                    source_file=filepath,
                    line_number=line_no,
                    controller=func_name,
                    framework="Flask",
                    confidence="high",
                    evidence=_get_evidence(source, line_no),
                )
            )

    # 2b. Flask WebSocket (flask-sock / flask-socketio)
    for m in re.finditer(r"""@(?:sock|ws)\s*\.\s*route\s*\(\s*(?P<path>['"][^'"]+['"])""", source, re.IGNORECASE):
        raw_path = m.group("path").strip("'\"")
        line_no = _line_number(source, m.start())
        path = raw_path.rstrip("/") or "/"
        func_name, _ = _infer_function_info(source, m.end())
        endpoints.append(
            ApiEndpoint(
                method="WS",
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=func_name,
                framework="Flask",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    # 3. Django / DRF
    for m in _DJANGO_PATH_RE.finditer(source):
        raw_path = m.group("path").strip("^$")
        if not raw_path.startswith("/"):
            raw_path = "/" + raw_path
        path = raw_path.rstrip("/") or "/"
        view = m.group("view")
        line_no = _line_number(source, m.start())

        # Determine method if detectable from view name (e.g. list, create, get, post)
        method = "GET"
        if any(w in view.lower() for w in ["create", "post", "login", "register"]):
            method = "POST"
        elif any(w in view.lower() for w in ["delete", "remove"]):
            method = "DELETE"
        elif any(w in view.lower() for w in ["update", "put"]):
            method = "PUT"

        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=view,
                framework="Django",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    for m in _DJANGO_ROUTER_RE.finditer(source):
        prefix = m.group("prefix").strip("/")
        viewset = m.group("viewset")
        line_no = _line_number(source, m.start())
        path = f"/{prefix}"
        endpoints.append(
            ApiEndpoint(
                method="GET",
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=f"{viewset}.list",
                framework="Django REST Framework",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )
        endpoints.append(
            ApiEndpoint(
                method="POST",
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=f"{viewset}.create",
                framework="Django REST Framework",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# 2. JavaScript / TypeScript Backend Analyzers (Express, Fastify, NestJS, Next.js)
# ─────────────────────────────────────────────────────────────────────────────

_EXPRESS_ROUTE_RE = re.compile(
    r"""\b(?P<caller>app|router|server|api|routes|fastify|hono)\s*\.\s*(?P<method>get|post|put|patch|delete)\s*\(\s*"""
    r"""(?P<path>['"`][^'"`]+['"`])""",
    re.IGNORECASE,
)

_EXPRESS_REQ_FIELD_RE = re.compile(r"""req\.body\.(\w+)""")
_EXPRESS_DESTRUCT_RE = re.compile(r"""\{([^{}]+)\}\s*=\s*req\.body""")
_EXPRESS_RESP_FIELD_RE = re.compile(r"""res\.(?:json|send)\s*\(\s*\{([^{}]+)\}""")

_NEST_CONTROLLER_RE = re.compile(r"""@Controller\s*\(\s*['"`]?(?P<prefix>[^'"`)]*?)['"`]?\s*\)""")
_NEST_METHOD_RE = re.compile(
    r"""@(?P<method>Get|Post|Put|Delete|Patch)\s*\(\s*['"`]?(?P<subpath>[^'"`)]*?)['"`]?\s*\)\s*(?:\n\s*)?(?:async\s+)?(?P<handler>\w+)\s*\(""",
    re.MULTILINE,
)

_NEXT_ROUTE_HANDLER_RE = re.compile(
    r"""export\s+(?:async\s+)?function\s+(?P<method>GET|POST|PUT|DELETE|PATCH)\b""",
)


def _analyze_js_ts_backend(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []
    norm_path = filepath.replace("\\", "/").lower()

    # 1. Next.js App Router (app/api/**/route.ts)
    if "app/api/" in norm_path and "route." in os.path.basename(norm_path):
        sub = norm_path.split("app/api/", 1)[1]
        route_dir = os.path.dirname(sub)
        api_path = f"/api/{route_dir}".rstrip("/") or "/api"
        for m in _NEXT_ROUTE_HANDLER_RE.finditer(source):
            method = m.group("method")
            line_no = _line_number(source, m.start())
            endpoints.append(
                ApiEndpoint(
                    method=method,
                    path=api_path,
                    source_file=filepath,
                    line_number=line_no,
                    controller=f"{method} {api_path}",
                    framework="Next.js API",
                    confidence="high",
                    evidence=_get_evidence(source, line_no),
                )
            )
        if endpoints:
            return endpoints

    # 2. Next.js Pages Router (pages/api/**.ts)
    if "pages/api/" in norm_path:
        sub = norm_path.split("pages/api/", 1)[1]
        base_name = os.path.splitext(sub)[0]
        if base_name == "index":
            api_path = "/api"
        else:
            api_path = f"/api/{base_name}"
        line_no = 1
        methods = ["GET"]
        if "req.method" in source:
            detected_methods = re.findall(r"""req\.method\s*===?\s*['"](GET|POST|PUT|DELETE|PATCH)['"]""", source)
            if detected_methods:
                methods = list(dict.fromkeys(detected_methods))
        for method in methods:
            endpoints.append(
                ApiEndpoint(
                    method=method,
                    path=api_path,
                    source_file=filepath,
                    line_number=line_no,
                    controller="handler",
                    framework="Next.js API",
                    confidence="high",
                    evidence=_get_evidence(source, line_no),
                )
            )
        if endpoints:
            return endpoints

    # 3. NestJS Controllers
    ctrl_m = _NEST_CONTROLLER_RE.search(source)
    if ctrl_m:
        prefix = ctrl_m.group("prefix").strip("/")
        for m in _NEST_METHOD_RE.finditer(source):
            method = m.group("method").upper()
            subpath = m.group("subpath").strip("/")
            handler = m.group("handler")
            line_no = _line_number(source, m.start())
            path = f"/{prefix}/{subpath}".rstrip("/") or "/"
            endpoints.append(
                ApiEndpoint(
                    method=method,
                    path=path,
                    source_file=filepath,
                    line_number=line_no,
                    controller=handler,
                    framework="NestJS",
                    confidence="high",
                    evidence=_get_evidence(source, line_no),
                )
            )
        if endpoints:
            return endpoints

    # 4. Express / Fastify / Koa / Hono
    for m in _EXPRESS_ROUTE_RE.finditer(source):
        method = m.group("method").upper()
        caller = m.group("caller").lower()
        raw_path = m.group("path").strip("'\"`")
        line_no = _line_number(source, m.start())
        path = raw_path.rstrip("/") or "/"

        framework = "Fastify" if caller == "fastify" else ("Hono" if caller == "hono" else "Express")

        snippet = source[m.end() : m.end() + 600]
        req_fields = list(dict.fromkeys(_EXPRESS_REQ_FIELD_RE.findall(snippet)))
        for dm in _EXPRESS_DESTRUCT_RE.finditer(snippet):
            for fld in dm.group(1).split(","):
                name = fld.split(":")[0].strip()
                if name and re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", name) and name not in req_fields:
                    req_fields.append(name)

        resp_fields: List[str] = []
        for rm in _EXPRESS_RESP_FIELD_RE.finditer(snippet):
            for part in rm.group(1).split(","):
                p = part.split(":")[0].strip().strip("'\"`")
                if p and re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", p) and p not in resp_fields:
                    resp_fields.append(p)

        # Look for handler function name
        handler = None
        handler_m = re.search(r""",\s*([A-Za-z0-9_]+)\s*\)""", source[m.start():m.end() + 50])
        if handler_m and handler_m.group(1) not in ("req", "res", "next", "function"):
            handler = handler_m.group(1)

        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                request_model=None,
                request_fields=req_fields,
                response_model=None,
                response_fields=resp_fields,
                source_file=filepath,
                line_number=line_no,
                controller=handler,
                framework=framework,
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    # 5. Node WebSocket (ws, socket.io, express-ws)
    for m in re.finditer(r"""(?:app\.ws\s*\(\s*['"](?P<p1>[^'"]+)['"]|new\s+WebSocketServer\s*\(\s*\{[^}]*path\s*:\s*['"](?P<p2>[^'"]+)['"]|io\.on\s*\(\s*['"]connection['"]|wss?\.on\s*\(\s*['"]connection['"]|@WebSocketGateway\s*\(\s*(?:['"](?P<p3>[^'"]+)['"])?)""", source, re.IGNORECASE):
        d = m.groupdict()
        wpath = d.get("p1") or d.get("p2") or d.get("p3") or "/ws"
        line_no = _line_number(source, m.start())
        endpoints.append(
            ApiEndpoint(
                method="WS",
                path=wpath.rstrip("/") or "/ws",
                source_file=filepath,
                line_number=line_no,
                controller="WebSocketHandler",
                framework="WebSocket",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    # 6. Node GraphQL (Apollo Server, Yoga, GraphQL schema)
    for m in re.finditer(r"""(?:applyMiddleware\s*\(\s*\{[^}]*path\s*:\s*['"](?P<p1>[^'"]+)['"]|createYoga\s*\(\s*\{[^}]*graphqlEndpoint\s*:\s*['"](?P<p2>[^'"]+)['"]|new\s+ApolloServer|buildSchema\s*\(|@Resolver\s*\()""", source, re.IGNORECASE):
        d = m.groupdict()
        gpath = d.get("p1") or d.get("p2") or "/graphql"
        line_no = _line_number(source, m.start())
        endpoints.append(
            ApiEndpoint(
                method="POST",
                path=gpath.rstrip("/") or "/graphql",
                source_file=filepath,
                line_number=line_no,
                controller="GraphQLHandler",
                framework="GraphQL",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# 3. Java Spring Boot Analyzer
# ─────────────────────────────────────────────────────────────────────────────

_SPRING_CLASS_MAPPING = re.compile(
    r"""@(?:RequestMapping)\s*\(\s*(?:(?:value|path)\s*=\s*)?['"](?P<prefix>[^'"]+)['"]"""
)
_SPRING_METHOD_MAPPING = re.compile(
    r"""@(?P<method>Get|Post|Put|Delete|Patch)Mapping\s*(?:\(\s*(?:(?:value|path)\s*=\s*)?['"]?(?P<path>[^'"]*?)['"]?\s*\))?""",
    re.IGNORECASE,
)


def _analyze_java_backend(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []
    class_prefix = ""
    cm = _SPRING_CLASS_MAPPING.search(source)
    if cm:
        class_prefix = cm.group("prefix").strip("/")

    class_name = None
    cn_m = re.search(r"""(?:public\s+)?class\s+(?P<name>\w+)""", source)
    if cn_m:
        class_name = cn_m.group("name")

    for m in _SPRING_METHOD_MAPPING.finditer(source):
        method = m.group("method").upper()
        subpath = (m.group("path") or "").strip().strip("'\"").strip("/")
        line_no = _line_number(source, m.start())

        if class_prefix and subpath:
            path = f"/{class_prefix}/{subpath}"
        elif class_prefix:
            path = f"/{class_prefix}"
        elif subpath:
            path = f"/{subpath}"
        else:
            path = "/"

        # Look for method name
        fn_m = re.search(r"""(?:public\s+[\w<>, ]+\s+)(?P<fn>\w+)\s*\(""", source[m.end():m.end() + 200])
        controller = f"{class_name}.{fn_m.group('fn')}" if (class_name and fn_m) else class_name

        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=controller,
                framework="Spring Boot",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# 4. Go Backend Analyzer (Gin, Echo, Fiber, net/http)
# ─────────────────────────────────────────────────────────────────────────────

_GO_ROUTE_RE = re.compile(
    r"""\b(?P<router>r|router|api|e|echo|app|g|group|v1)\s*\.\s*(?P<method>GET|POST|PUT|DELETE|PATCH|Get|Post|Put|Delete|Patch)\s*\(\s*['"](?P<path>[^'"]+)['"]\s*,\s*(?P<handler>[A-Za-z0-9_.]+)""",
)
_GO_HTTP_RE = re.compile(
    r"""http\.HandleFunc\s*\(\s*['"](?P<path>[^'"]+)['"]\s*,\s*(?P<handler>[A-Za-z0-9_.]+)""",
)


def _analyze_go_backend(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []

    for m in _GO_ROUTE_RE.finditer(source):
        method = m.group("method").upper()
        raw_path = m.group("path").strip()
        handler = m.group("handler")
        line_no = _line_number(source, m.start())
        path = raw_path.rstrip("/") or "/"
        router = m.group("router").lower()

        framework = "Fiber" if router == "app" else ("Echo" if router in ("e", "echo") else "Gin")

        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=handler,
                framework=framework,
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    for m in _GO_HTTP_RE.finditer(source):
        raw_path = m.group("path").strip()
        handler = m.group("handler")
        line_no = _line_number(source, m.start())
        path = raw_path.rstrip("/") or "/"
        endpoints.append(
            ApiEndpoint(
                method="GET",
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=handler,
                framework="net/http",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# 5. Ruby on Rails Analyzer
# ─────────────────────────────────────────────────────────────────────────────

_RAILS_ROUTE_RE = re.compile(
    r"""\b(?P<method>get|post|put|patch|delete)\s+['"](?P<path>[^'"]+)['"](?:\s*,\s*to:\s*['"](?P<to>[^'"]+)['"])?""",
    re.IGNORECASE,
)
_RAILS_RESOURCES_RE = re.compile(
    r"""resources\s+:(?P<resource>\w+)""",
)


def _analyze_ruby_backend(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []
    for m in _RAILS_ROUTE_RE.finditer(source):
        method = m.group("method").upper()
        raw_path = m.group("path").strip()
        to = m.group("to")
        line_no = _line_number(source, m.start())
        path = "/" + raw_path.strip("/") if not raw_path.startswith("/") else raw_path
        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=to,
                framework="Rails",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )
    for m in _RAILS_RESOURCES_RE.finditer(source):
        resource = m.group("resource")
        line_no = _line_number(source, m.start())
        endpoints.append(
            ApiEndpoint(
                method="GET",
                path=f"/{resource}",
                source_file=filepath,
                line_number=line_no,
                controller=f"{resource}#index",
                framework="Rails",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )
        endpoints.append(
            ApiEndpoint(
                method="POST",
                path=f"/{resource}",
                source_file=filepath,
                line_number=line_no,
                controller=f"{resource}#create",
                framework="Rails",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )
    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# 6. PHP Analyzer (Laravel, Symfony)
# ─────────────────────────────────────────────────────────────────────────────

_LARAVEL_ROUTE_RE = re.compile(
    r"""Route::(?P<method>get|post|put|patch|delete)\s*\(\s*['"](?P<path>[^'"]+)['"](?:\s*,\s*(?:\[(?P<controller>[^\]]+)\]|['"](?P<action>[^'"]+)['"]))?""",
    re.IGNORECASE,
)


def _analyze_php_backend(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []
    for m in _LARAVEL_ROUTE_RE.finditer(source):
        method = m.group("method").upper()
        raw_path = m.group("path").strip()
        controller = m.group("controller") or m.group("action")
        line_no = _line_number(source, m.start())
        path = "/" + raw_path.strip("/") if not raw_path.startswith("/") else raw_path
        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=controller.strip() if controller else None,
                framework="Laravel",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )
    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# 7. C# ASP.NET Core Analyzer
# ─────────────────────────────────────────────────────────────────────────────

_CS_ROUTE_CLASS_RE = re.compile(r"""\[Route\s*\(\s*"(?P<prefix>[^"]+)"\s*\)\]""")
_CS_HTTP_METHOD_RE = re.compile(
    r"""\[Http(?P<method>Get|Post|Put|Delete|Patch)(?:\s*\(\s*"(?P<path>[^"]*)"\s*\))?\]""",
    re.IGNORECASE,
)
_CS_MINIMAL_API_RE = re.compile(
    r"""app\.Map(?P<method>Get|Post|Put|Delete|Patch)\s*\(\s*"(?P<path>[^"]+)"\s*,\s*(?P<handler>[A-Za-z0-9_.]+)?""",
    re.IGNORECASE,
)


def _analyze_csharp_backend(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []
    prefix = ""
    pm = _CS_ROUTE_CLASS_RE.search(source)
    if pm:
        prefix = pm.group("prefix").strip("/")

    # Class name
    class_name = None
    cn_m = re.search(r"""class\s+(?P<name>\w+Controller)""", source)
    if cn_m:
        class_name = cn_m.group("name")
        if "[controller]" in prefix:
            short_name = class_name[:-10].lower() if class_name.endswith("Controller") else class_name.lower()
            prefix = prefix.replace("[controller]", short_name)

    for m in _CS_HTTP_METHOD_RE.finditer(source):
        method = m.group("method").upper()
        subpath = (m.group("path") or "").strip().strip("/")
        line_no = _line_number(source, m.start())

        if prefix and subpath:
            path = f"/{prefix}/{subpath}"
        elif prefix:
            path = f"/{prefix}"
        elif subpath:
            path = f"/{subpath}"
        else:
            path = "/"

        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=class_name,
                framework="ASP.NET Core",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    for m in _CS_MINIMAL_API_RE.finditer(source):
        method = m.group("method").upper()
        raw_path = m.group("path").strip()
        handler = m.group("handler")
        line_no = _line_number(source, m.start())
        path = "/" + raw_path.strip("/") if not raw_path.startswith("/") else raw_path
        endpoints.append(
            ApiEndpoint(
                method=method,
                path=path,
                source_file=filepath,
                line_number=line_no,
                controller=handler,
                framework="ASP.NET Core",
                confidence="high",
                evidence=_get_evidence(source, line_no),
            )
        )

    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# 8. Generic Route Fallback
# ─────────────────────────────────────────────────────────────────────────────

_GENERIC_URL_PATH_RE = re.compile(
    r"""['"`](/(?:api|v[0-9]+|rest)/[a-zA-Z0-9_\-/{}:[\]]+)['"`]"""
)


def _analyze_generic_fallback(filepath: str, source: str) -> List[ApiEndpoint]:
    endpoints: List[ApiEndpoint] = []
    for m in _GENERIC_URL_PATH_RE.finditer(source):
        raw_path = m.group(1).rstrip("/") or "/"
        line_no = _line_number(source, m.start())

        # Check nearby snippet for HTTP methods
        nearby = source[max(0, m.start() - 100) : min(len(source), m.end() + 100)]
        method = "GET"
        for candidate in ["POST", "PUT", "DELETE", "PATCH", "GET"]:
            if candidate in nearby.upper():
                method = candidate
                break

        endpoints.append(
            ApiEndpoint(
                method=method,
                path=raw_path,
                source_file=filepath,
                line_number=line_no,
                controller=None,
                framework="Unknown/Generic",
                confidence="medium",
                evidence=_get_evidence(source, line_no),
            )
        )
    return endpoints


# ─────────────────────────────────────────────────────────────────────────────
# Main Backend Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def analyze_backend_file(filepath: str, source: str) -> List[ApiEndpoint]:
    """Parse *source* across supported backend languages and return detected route endpoints."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext in (".py", ".pyw"):
        endpoints = _analyze_python_backend(filepath, source)
    elif ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        endpoints = _analyze_js_ts_backend(filepath, source)
    elif ext == ".java":
        endpoints = _analyze_java_backend(filepath, source)
    elif ext == ".go":
        endpoints = _analyze_go_backend(filepath, source)
    elif ext == ".rb":
        endpoints = _analyze_ruby_backend(filepath, source)
    elif ext == ".php":
        endpoints = _analyze_php_backend(filepath, source)
    elif ext == ".cs":
        endpoints = _analyze_csharp_backend(filepath, source)
    else:
        endpoints = []

    # If no endpoints detected yet in this backend file, run generic fallback!
    if not endpoints and any(kw in filepath.lower() for kw in ["api", "route", "controller", "server", "backend", "handler", "endpoint"]):
        endpoints = _analyze_generic_fallback(filepath, source)

    return endpoints


def analyze_backend_files(
    project_root: str,
    backend_files: List[str],
    prefix_resolver: Optional[Any] = None,
) -> List[ApiEndpoint]:
    """Analyze all backend files and return aggregated endpoints."""
    all_endpoints: List[ApiEndpoint] = []
    for rel_path in backend_files:
        full_path = os.path.join(project_root, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            eps = analyze_backend_file(rel_path, source)
            if prefix_resolver:
                for ep in eps:
                    ep.path = prefix_resolver.resolve_endpoint_path(ep.path, rel_path)
            for ep in eps:
                # Deduplicate identical method+path in same file
                if not any(e.method == ep.method and e.path == ep.path and e.source_file == ep.source_file for e in all_endpoints):
                    all_endpoints.append(ep)
        except OSError:
            pass
    return all_endpoints

