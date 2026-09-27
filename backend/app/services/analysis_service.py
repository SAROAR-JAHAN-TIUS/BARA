"""
BARA Backend – Analysis Service.

Orchestrates the full analysis pipeline.

Source Manager → project_path → Analyzer Pipeline → AnalysisResult
"""
from __future__ import annotations

import uuid
from typing import Dict

from app.models.analysis import AnalysisResult, AnalysisRequest
from app.analyzers.scanner import scan_project
from app.analyzers.frontend_analyzer import analyze_frontend_files
from app.analyzers.backend_analyzer import analyze_backend_files
from app.analyzers.mismatch_detector import detect_mismatches, compute_match_stats
from app.analyzers.architecture_builder import (
    build_architecture,
    build_api_connections,
    build_repository_tree,
    extract_database_services,
)
from app.analyzers.env_resolver import EnvResolver
from app.analyzers.prefix_resolver import RoutePrefixResolver
from app.services.source_manager import (
    resolve_source,
    cleanup,
    resolve_uploaded_folder,
    ResolvedSource,
)

# In-memory store for analysis results (keyed by analysis_id)
_store: Dict[str, AnalysisResult] = {}


def run_analysis_pipeline(resolved: ResolvedSource) -> AnalysisResult:
    """
    Unified analysis pipeline for any resolved source (local folder, upload, or GitHub clone).
    """
    try:
        # ── Run the deterministic analysis pipeline ──────────────────────
        project_path = resolved.project_path

        # 1. Scan project
        scan = scan_project(project_path)

        # 2. Resolvers: environment & route prefixes
        env_resolver = EnvResolver(project_path)
        env_resolver.resolve_all(scan.frontend_files)

        prefix_resolver = RoutePrefixResolver(project_path)
        prefix_resolver.scan_all(scan.backend_files)

        # 3. Analyze frontend files with env resolving
        frontend_calls = analyze_frontend_files(
            project_path, scan.frontend_files, env_resolver=env_resolver
        )

        # 4. Analyze backend files with prefix resolving
        backend_endpoints = analyze_backend_files(
            project_path, scan.backend_files, prefix_resolver=prefix_resolver
        )

        # 5. Detect mismatches & compute statistics
        issues = detect_mismatches(frontend_calls, backend_endpoints)
        match_stats = compute_match_stats(frontend_calls, backend_endpoints, issues)

        # 6. Build multi-tier architecture graph
        architecture = build_architecture(
            frontend_calls=frontend_calls,
            backend_endpoints=backend_endpoints,
            issues=issues,
            project_root=project_path,
            project_name=resolved.project_name,
            detected_technologies=scan.detected_technologies,
            backend_status=scan.backend_status,
        )

        # 7. Build api_connections, repository_tree, and database_services
        has_backend = len(backend_endpoints) > 0
        api_connections = build_api_connections(
            frontend_calls=frontend_calls,
            backend_endpoints=backend_endpoints,
            issues=issues,
            has_backend=has_backend,
        )
        repository_tree = build_repository_tree(project_path, scan.files)
        database_services = extract_database_services(scan.detected_technologies, backend_endpoints)

        # 6. Refine backend_framework & backend_status from extracted endpoints if needed
        backend_framework = scan.backend_framework
        backend_status = scan.backend_status
        if not backend_framework:
            for ep in backend_endpoints:
                fw = (ep.framework or "").lower()
                if fw and not any(k in fw for k in ("generic", "unknown")):
                    backend_framework = ep.framework
                    backend_status = "Framework detected"
                    break

        # 7. Build summary
        summary = {
            "total_frontend_calls": len(frontend_calls),
            "total_backend_endpoints": len(backend_endpoints),
            "total_issues": len(issues),
            "matched_apis": match_stats["matched_apis"],
            "mismatched_apis": match_stats["mismatched_apis"],
            "external_apis": match_stats["external_apis"],
            "architecture_nodes_count": len(architecture.nodes),
            "architecture_edges_count": len(architecture.edges),
            "frontend_files_scanned": len(scan.frontend_files),
            "backend_files_scanned": len(scan.backend_files),
            "project_type": scan.project_type,
            "detected_technologies": scan.detected_technologies,
            "backend_framework": backend_framework,
            "backend_status": backend_status,
            "monorepo_packages": scan.monorepo_packages,
            "issues_by_type": {},
            "issues_by_severity": {"high": 0, "medium": 0, "low": 0},
        }
        for issue in issues:
            summary["issues_by_type"][issue.issue_type] = (
                summary["issues_by_type"].get(issue.issue_type, 0) + 1
            )
            sev = issue.severity.lower()
            if sev in summary["issues_by_severity"]:
                summary["issues_by_severity"][sev] += 1

        analysis_id = str(uuid.uuid4())
        result = AnalysisResult(
            analysis_id=analysis_id,
            source_type=resolved.source_type,
            source=resolved.source,
            project_name=resolved.project_name,
            github_url=resolved.github_url,
            project_type=scan.project_type,
            backend_framework=backend_framework,
            backend_status=backend_status,
            detected_technologies=scan.detected_technologies,
            scanned_files=scan.files,
            frontend_calls=frontend_calls,
            backend_endpoints=backend_endpoints,
            issues=issues,
            architecture=architecture,
            api_connections=api_connections,
            repository_tree=repository_tree,
            base_urls=env_resolver.env_vars,
            database_services=database_services,
            summary=summary,
        )

        _store[analysis_id] = result
        return result

    finally:
        # Always clean up temporary workspaces (GitHub clones or uploads)
        # Never touches permanent local projects (resolved.temporary == False)
        cleanup(resolved)


def run_analysis(request: AnalysisRequest) -> AnalysisResult:
    """Analyze a project from a local filesystem path or GitHub URL."""
    resolved = resolve_source(request.source_type, request.source)
    return run_analysis_pipeline(resolved)


async def run_upload_analysis(
    folder_name: str,
    path_list: list[str],
    files: list[Any],
) -> AnalysisResult:
    """Analyze a project from uploaded folder files using the unified pipeline."""
    resolved = await resolve_uploaded_folder(folder_name, path_list, files)
    return run_analysis_pipeline(resolved)


def get_analysis(analysis_id: str) -> AnalysisResult | None:
    return _store.get(analysis_id)
