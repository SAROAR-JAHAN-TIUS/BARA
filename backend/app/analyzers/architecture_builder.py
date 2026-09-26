"""
BARA Backend – Architecture Builder.

Builds a structured JSON graph from frontend calls, backend endpoints, and issues.
"""
from __future__ import annotations
import os
from typing import List, Set

from app.models.analysis import ApiCall, ApiEndpoint, Issue, Architecture, ArchNode, ArchEdge
from app.analyzers.normalizer import paths_match


def build_architecture(
    frontend_calls: List[ApiCall],
    backend_endpoints: List[ApiEndpoint],
    issues: List[Issue],
    project_root: str,
) -> Architecture:
    nodes: List[ArchNode] = []
    edges: List[ArchEdge] = []
    seen_node_ids: Set[str] = set()

    def add_node(node: ArchNode):
        if node.id not in seen_node_ids:
            nodes.append(node)
            seen_node_ids.add(node.id)

    # ---- Frontend component nodes (one per unique source file) ----
    fe_files: Set[str] = set()
    for call in frontend_calls:
        fe_files.add(call.source_file)

    for fe_file in sorted(fe_files):
        node_id = f"fe:{fe_file}"
        label = os.path.basename(fe_file)
        add_node(ArchNode(id=node_id, kind="frontend_component", label=label, source_file=fe_file))

    # ---- Backend endpoint nodes ----
    for ep in backend_endpoints:
        node_id = f"be:{ep.method}:{ep.path}"
        label = f"{ep.method} {ep.path}"
        add_node(
            ArchNode(
                id=node_id,
                kind="backend_endpoint",
                label=label,
                source_file=ep.source_file,
                details={
                    "method": ep.method,
                    "path": ep.path,
                    "request_model": ep.request_model,
                    "request_fields": ep.request_fields,
                    "response_model": ep.response_model,
                    "response_fields": ep.response_fields,
                },
            )
        )

    # ---- Detect databases (naive: look for SQLAlchemy / psycopg2 / sqlite imports) ----
    # Will be enriched later; placeholder node if any backend file references DB
    db_indicators = {"sqlalchemy", "psycopg2", "pymysql", "sqlite3", "motor", "pymongo"}
    # (scanning is best effort — architecture builder doesn't re-read files)

    # ---- Edges: frontend → backend endpoint ----
    issue_paths: Set[str] = set()
    for issue in issues:
        if issue.frontend_location:
            issue_paths.add(issue.frontend_location.file)

    for call in frontend_calls:
        fe_node_id = f"fe:{call.source_file}"
        # Find matching backend endpoint
        matched_ep = None
        for ep in backend_endpoints:
            if paths_match(call.path, ep.path) and ep.method.upper() == call.method.upper():
                matched_ep = ep
                break

        has_issue = call.source_file in issue_paths

        if matched_ep:
            be_node_id = f"be:{matched_ep.method}:{matched_ep.path}"
            edges.append(
                ArchEdge(
                    source=fe_node_id,
                    target=be_node_id,
                    label=f"{call.method} {call.path}",
                    has_issue=has_issue,
                )
            )
        else:
            # No backend match → create a "ghost" missing endpoint node
            ghost_id = f"missing:{call.method}:{call.path}"
            if ghost_id not in seen_node_ids:
                add_node(
                    ArchNode(
                        id=ghost_id,
                        kind="missing_endpoint",
                        label=f"MISSING: {call.method} {call.path}",
                        details={"method": call.method, "path": call.path},
                    )
                )
            edges.append(
                ArchEdge(
                    source=fe_node_id,
                    target=ghost_id,
                    label=f"{call.method} {call.path}",
                    has_issue=True,
                )
            )

    return Architecture(nodes=nodes, edges=edges)
