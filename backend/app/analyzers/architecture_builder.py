"""
BARA Backend – Multi-Tier Architecture Graph Builder.

Builds a real directional architecture graph from actual repository analysis:
Repository
   ↓
Frontend (Pages / Components → API Client / Services)
   ↓ (API Calls: POST /api/login)
Backend (Routes → Controllers → Services → Database / External APIs)

If no backend exists, truthfully renders:
Repository → Frontend → External API
without fabricating any fake backend routes.
"""
from __future__ import annotations
import os
from typing import List, Set, Optional, Dict, Any

from app.models.analysis import (
    ApiCall,
    ApiEndpoint,
    Issue,
    Architecture,
    ArchNode,
    ArchEdge,
    ApiConnection,
    RepositoryTreeNode,
    ScannedFile,
)
from app.analyzers.normalizer import paths_match


def build_architecture(
    frontend_calls: List[ApiCall],
    backend_endpoints: List[ApiEndpoint],
    issues: List[Issue],
    project_root: str,
    project_name: str = "",
    detected_technologies: Optional[List[str]] = None,
    backend_status: str = "No backend/API code detected",
) -> Architecture:
    nodes: List[ArchNode] = []
    edges: List[ArchEdge] = []
    seen_node_ids: Set[str] = set()

    def add_node(node: ArchNode):
        if node.id not in seen_node_ids:
            nodes.append(node)
            seen_node_ids.add(node.id)

    def add_edge(edge: ArchEdge):
        edges.append(edge)

    detected_technologies = detected_technologies or []
    has_backend = len(backend_endpoints) > 0

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Repository Root Node
    # ─────────────────────────────────────────────────────────────────────────
    repo_label = project_name or os.path.basename(os.path.abspath(project_root)) or "Repository"
    repo_node_id = "repo:root"
    add_node(
        ArchNode(
            id=repo_node_id,
            kind="repository",
            label=f"📦 {repo_label}",
            details={"technologies": detected_technologies},
        )
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Frontend Layer (Pages, Services, Components)
    # ─────────────────────────────────────────────────────────────────────────
    fe_files: Set[str] = {c.source_file for c in frontend_calls}
    issue_fe_files: Set[str] = {
        i.frontend_location.file for i in issues if i.frontend_location
    }

    for fe_file in sorted(fe_files):
        norm = fe_file.replace("\\", "/").lower()
        base = os.path.basename(fe_file)

        if any(p in norm for p in ["/pages/", "/app/", "/views/"]):
            kind = "frontend_page"
            label = f"📄 {base}"
        elif any(s in norm for s in ["/services/", "/api/", "/client/", "/clients/"]):
            kind = "frontend_service"
            label = f"⚡ {base}"
        else:
            kind = "frontend_component"
            label = f"🧩 {base}"

        fe_node_id = f"fe:{fe_file}"
        add_node(
            ArchNode(
                id=fe_node_id,
                kind=kind,
                label=label,
                source_file=fe_file,
                details={"category": kind},
            )
        )
        # Connect repository to top-level frontend files
        add_edge(
            ArchEdge(
                source=repo_node_id,
                target=fe_node_id,
                label="contains",
                relation="routes_to",
                status="matched",
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Database Node (if database libraries / ORMs detected)
    # ─────────────────────────────────────────────────────────────────────────
    db_techs = [
        t for t in detected_technologies
        if t in ("SQLAlchemy", "Prisma", "Mongoose", "TypeORM", "Hibernate", "GORM", "Entity Framework")
    ]
    db_node_id = None
    if has_backend and db_techs:
        db_node_id = "db:storage"
        add_node(
            ArchNode(
                id=db_node_id,
                kind="database",
                label=f"🗄️ Database ({', '.join(db_techs)})",
                details={"technologies": db_techs},
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Backend Endpoints & Controllers (only if backend exists)
    # ─────────────────────────────────────────────────────────────────────────
    controllers_seen: Dict[str, str] = {}

    for ep in backend_endpoints:
        ep_node_id = f"be:{ep.method}:{ep.path}"
        add_node(
            ArchNode(
                id=ep_node_id,
                kind="backend_endpoint",
                label=f"⚙️ {ep.method} {ep.path}",
                source_file=ep.source_file,
                details={
                    "method": ep.method,
                    "path": ep.path,
                    "framework": ep.framework,
                    "controller": ep.controller,
                    "confidence": ep.confidence,
                    "line_number": ep.line_number,
                    "evidence": ep.evidence,
                    "request_model": ep.request_model,
                    "request_fields": ep.request_fields,
                    "response_model": ep.response_model,
                    "response_fields": ep.response_fields,
                },
            )
        )

        # Controller / Handler Node
        if ep.controller:
            ctrl_id = f"ctrl:{ep.source_file}:{ep.controller}"
            if ctrl_id not in seen_node_ids:
                add_node(
                    ArchNode(
                        id=ctrl_id,
                        kind="backend_controller",
                        label=f"🎮 {ep.controller}",
                        source_file=ep.source_file,
                        details={"handler": ep.controller, "framework": ep.framework},
                    )
                )
                controllers_seen[ep.controller] = ctrl_id

            # Route -> Controller
            add_edge(
                ArchEdge(
                    source=ep_node_id,
                    target=ctrl_id,
                    label="handles",
                    relation="routes_to",
                    status="matched",
                )
            )

            # Controller -> Database
            if db_node_id:
                add_edge(
                    ArchEdge(
                        source=ctrl_id,
                        target=db_node_id,
                        label="queries",
                        relation="queries_db",
                        status="matched",
                    )
                )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Connect Frontend Calls to Backend Endpoints / External APIs
    # ─────────────────────────────────────────────────────────────────────────
    explanation: Optional[str] = None

    if not has_backend and len(frontend_calls) > 0:
        explanation = "Frontend detected, but no backend routes were found. No backend implementation exists in this project."

    for call in frontend_calls:
        fe_node_id = f"fe:{call.source_file}"
        has_issue = call.source_file in issue_fe_files

        # A. External API call (e.g. absolute URL or repository has no backend)
        if call.is_external or not has_backend or call.path.startswith("http://") or call.path.startswith("https://"):
            ext_label = "External API"
            ext_id = f"ext:{call.path}"
            add_node(
                ArchNode(
                    id=ext_id,
                    kind="external_api",
                    label=f"🌐 {call.method} {call.path}",
                    details={
                        "path": call.path,
                        "method": call.method,
                        "is_external": True,
                        "calling_context": call.calling_context,
                        "evidence": call.evidence,
                    },
                )
            )
            add_edge(
                ArchEdge(
                    source=fe_node_id,
                    target=ext_id,
                    label=f"{call.method} {call.path}",
                    relation="external_request",
                    status="external",
                    has_issue=False,
                )
            )
            continue

        # B. Backend exists: find matching endpoint
        matched_ep = None
        for ep in backend_endpoints:
            if paths_match(call.path, ep.path) and ep.method.upper() == call.method.upper():
                matched_ep = ep
                break

        if matched_ep:
            be_node_id = f"be:{matched_ep.method}:{matched_ep.path}"
            add_edge(
                ArchEdge(
                    source=fe_node_id,
                    target=be_node_id,
                    label=f"{call.method} {call.path}",
                    relation="calls",
                    status="matched",
                    has_issue=has_issue,
                )
            )
        else:
            # Different method exists?
            different_method_ep = None
            for ep in backend_endpoints:
                if paths_match(call.path, ep.path):
                    different_method_ep = ep
                    break

            if different_method_ep:
                be_node_id = f"be:{different_method_ep.method}:{different_method_ep.path}"
                add_edge(
                    ArchEdge(
                        source=fe_node_id,
                        target=be_node_id,
                        label=f"{call.method} (Expected: {different_method_ep.method})",
                        relation="calls",
                        status="mismatch",
                        has_issue=True,
                    )
                )
            else:
                # Unresolved internal route
                unresolved_id = f"missing:{call.method}:{call.path}"
                add_node(
                    ArchNode(
                        id=unresolved_id,
                        kind="external_api",
                        label=f"❓ Unresolved: {call.method} {call.path}",
                        details={"method": call.method, "path": call.path},
                    )
                )
                add_edge(
                    ArchEdge(
                        source=fe_node_id,
                        target=unresolved_id,
                        label=f"{call.method} {call.path}",
                        relation="calls",
                        status="unhandled",
                        has_issue=True,
                    )
                )

    if has_backend and len(frontend_calls) == 0:
        explanation = "Backend detected, but no frontend API callers were found."
    elif not has_backend and len(frontend_calls) == 0:
        explanation = "No backend routes or frontend API calls were detected in this repository."

    return Architecture(nodes=nodes, edges=edges, explanation=explanation)


def build_api_connections(
    frontend_calls: List[ApiCall],
    backend_endpoints: List[ApiEndpoint],
    issues: List[Issue],
    has_backend: bool = True,
) -> List[ApiConnection]:
    """Compile comprehensive Frontend <-> Backend connection records."""
    connections: List[ApiConnection] = []
    matched_endpoint_keys: Set[tuple[str, str]] = set()

    for idx, call in enumerate(frontend_calls):
        cid = f"conn-fe-{idx}"
        proto = "http"
        if call.framework in ("WebSocket", "Socket.IO") or call.path.startswith("ws://") or call.path.startswith("wss://"):
            proto = "websocket"
        elif call.framework in ("graphql-request", "GraphQL") or "/graphql" in call.path:
            proto = "graphql"

        # Check if external
        if call.is_external or call.path.startswith("http://") or call.path.startswith("https://"):
            connections.append(
                ApiConnection(
                    id=cid,
                    frontend_call=call,
                    backend_endpoint=None,
                    caller_location=f"{call.source_file}:{call.line_number}",
                    route_handler=None,
                    protocol=proto,
                    status="EXTERNAL",
                    resolved_path=call.path,
                    method=call.method,
                    issues=[],
                    line_number_frontend=call.line_number,
                )
            )
            continue

        if not has_backend and len(backend_endpoints) == 0:
            rel_issues = [
                i for i in issues
                if i.frontend_location and i.frontend_location.file == call.source_file and i.frontend_location.line == call.line_number
            ]
            connections.append(
                ApiConnection(
                    id=cid,
                    frontend_call=call,
                    backend_endpoint=None,
                    caller_location=f"{call.source_file}:{call.line_number}",
                    route_handler=None,
                    protocol=proto,
                    status="UNKNOWN_BACKEND",
                    resolved_path=call.path,
                    method=call.method,
                    issues=rel_issues,
                    line_number_frontend=call.line_number,
                )
            )
            continue

        # Look for matching backend endpoint
        matched_ep = None
        for ep in backend_endpoints:
            if paths_match(call.path, ep.path) and ep.method.upper() == call.method.upper():
                matched_ep = ep
                matched_endpoint_keys.add((ep.method.upper(), ep.path))
                break

        if matched_ep:
            rel_issues = [
                i for i in issues
                if (i.frontend_location and i.frontend_location.file == call.source_file and i.frontend_location.line == call.line_number)
                or (i.backend_location and i.backend_location.file == matched_ep.source_file and i.backend_location.line == matched_ep.line_number)
            ]
            status = "MATCHED"
            if any(i.issue_type in ("REQUEST_FIELD_MISMATCH", "FIELD_MISMATCH") for i in rel_issues):
                status = "FIELD_MISMATCH"
            elif any(i.issue_type == "QUERY_PARAM_MISMATCH" for i in rel_issues):
                status = "QUERY_PARAM_MISMATCH"
            elif any(i.issue_type == "PATH_PARAMETER_MISMATCH" for i in rel_issues):
                status = "PATH_PARAMETER_MISMATCH"

            connections.append(
                ApiConnection(
                    id=cid,
                    frontend_call=call,
                    backend_endpoint=matched_ep,
                    caller_location=f"{call.source_file}:{call.line_number}",
                    route_handler=f"{matched_ep.source_file}:{matched_ep.controller}" if matched_ep.controller else f"{matched_ep.source_file}:{matched_ep.line_number}",
                    protocol=proto,
                    status=status,
                    resolved_path=matched_ep.path,
                    method=call.method,
                    issues=rel_issues,
                    line_number_frontend=call.line_number,
                    line_number_backend=matched_ep.line_number,
                )
            )
        else:
            diff_ep = None
            for ep in backend_endpoints:
                if paths_match(call.path, ep.path):
                    diff_ep = ep
                    matched_endpoint_keys.add((ep.method.upper(), ep.path))
                    break

            rel_issues = [
                i for i in issues
                if i.frontend_location and i.frontend_location.file == call.source_file and i.frontend_location.line == call.line_number
            ]
            if diff_ep:
                connections.append(
                    ApiConnection(
                        id=cid,
                        frontend_call=call,
                        backend_endpoint=diff_ep,
                        caller_location=f"{call.source_file}:{call.line_number}",
                        route_handler=f"{diff_ep.source_file}:{diff_ep.controller}" if diff_ep.controller else f"{diff_ep.source_file}:{diff_ep.line_number}",
                        protocol=proto,
                        status="METHOD_MISMATCH",
                        resolved_path=diff_ep.path,
                        method=call.method,
                        issues=rel_issues,
                        line_number_frontend=call.line_number,
                        line_number_backend=diff_ep.line_number,
                    )
                )
            else:
                connections.append(
                    ApiConnection(
                        id=cid,
                        frontend_call=call,
                        backend_endpoint=None,
                        caller_location=f"{call.source_file}:{call.line_number}",
                        route_handler=None,
                        protocol=proto,
                        status="MISSING_BACKEND_ENDPOINT",
                        resolved_path=call.path,
                        method=call.method,
                        issues=rel_issues,
                        line_number_frontend=call.line_number,
                    )
                )

    # UNUSED_BACKEND_ENDPOINT connections
    for idx, ep in enumerate(backend_endpoints):
        if (ep.method.upper(), ep.path) not in matched_endpoint_keys:
            cid = f"conn-be-{idx}"
            proto = "websocket" if ep.method == "WS" else ("graphql" if ep.framework == "GraphQL" or "/graphql" in ep.path else "http")
            rel_issues = [
                i for i in issues
                if i.backend_location and i.backend_location.file == ep.source_file and i.backend_location.line == ep.line_number
            ]
            connections.append(
                ApiConnection(
                    id=cid,
                    frontend_call=None,
                    backend_endpoint=ep,
                    caller_location=None,
                    route_handler=f"{ep.source_file}:{ep.controller}" if ep.controller else f"{ep.source_file}:{ep.line_number}",
                    protocol=proto,
                    status="UNUSED_BACKEND_ENDPOINT",
                    resolved_path=ep.path,
                    method=ep.method,
                    issues=rel_issues,
                    line_number_backend=ep.line_number,
                )
            )

    return connections


def build_repository_tree(project_root: str, scanned_files: List[ScannedFile]) -> RepositoryTreeNode:
    """Build hierarchical repository file explorer tree."""
    from app.analyzers.scanner import SKIP_DIRS, _categorize_file, _detect_language

    scanned_lookup = {sf.path.replace("\\", "/"): sf for sf in scanned_files}
    root_node = RepositoryTreeNode(
        name=os.path.basename(os.path.abspath(project_root)) or "root",
        path="",
        type="directory",
        children=[],
    )

    node_map: Dict[str, RepositoryTreeNode] = {"": root_node}

    for root, dirs, files in os.walk(project_root):
        dirs[:] = sorted([d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")])
        rel_root = os.path.relpath(root, project_root).replace("\\", "/")
        if rel_root == ".":
            rel_root = ""

        current_node = node_map.get(rel_root)
        if not current_node:
            continue

        if current_node.children is None:
            current_node.children = []

        for d in dirs:
            dir_rel = f"{rel_root}/{d}".lstrip("/")
            dir_node = RepositoryTreeNode(
                name=d,
                path=dir_rel,
                type="directory",
                children=[],
            )
            current_node.children.append(dir_node)
            node_map[dir_rel] = dir_node

        for f in sorted(files):
            if f.startswith("."):
                continue
            file_rel = f"{rel_root}/{f}".lstrip("/")
            ext = os.path.splitext(f)[1].lower()
            scanned = scanned_lookup.get(file_rel)
            role = scanned.category if scanned else _categorize_file(file_rel)
            lang = scanned.language if scanned else _detect_language(ext)

            file_node = RepositoryTreeNode(
                name=f,
                path=file_rel,
                type="file",
                role=role or "file",
                language=lang if lang != "unknown" else None,
            )
            current_node.children.append(file_node)

    return root_node


def extract_database_services(detected_technologies: List[str], backend_endpoints: List[ApiEndpoint]) -> List[Dict[str, Any]]:
    """Detect database configurations and external services."""
    services = []
    db_techs = [t for t in detected_technologies if t in (
        "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Prisma", "SQLAlchemy",
        "Mongoose", "TypeORM", "Sequelize", "GORM", "Hibernate", "Entity Framework", "Firebase", "Supabase"
    )]
    for db in db_techs:
        services.append({
            "type": "database",
            "name": db,
            "status": "Configured / Active",
            "connected_endpoints_count": len(backend_endpoints),
        })

    ext_apis = [t for t in detected_technologies if t in ("Stripe", "OpenAI", "AWS SDK", "GitHub API")]
    for ext in ext_apis:
        services.append({
            "type": "external_api",
            "name": ext,
            "status": "Integrated",
            "connected_endpoints_count": 0,
        })
    return services

