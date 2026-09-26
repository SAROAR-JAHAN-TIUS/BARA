"""
BARA Backend – Analysis Service.

Orchestrates the full analysis pipeline.
"""
from __future__ import annotations
import uuid
from typing import Dict

from app.models.analysis import AnalysisResult, AnalysisRequest
from app.analyzers.scanner import scan_project
from app.analyzers.frontend_analyzer import analyze_frontend_files
from app.analyzers.backend_analyzer import analyze_backend_files
from app.analyzers.mismatch_detector import detect_mismatches
from app.analyzers.architecture_builder import build_architecture

# In-memory store for analysis results (keyed by analysis_id)
_store: Dict[str, AnalysisResult] = {}


def run_analysis(request: AnalysisRequest) -> AnalysisResult:
    """Run the full BARA analysis pipeline and return a result."""
    project_path = request.project_path

    # 1. Scan project
    scan = scan_project(project_path)

    # 2. Analyze frontend files
    frontend_calls = analyze_frontend_files(project_path, scan.frontend_files)

    # 3. Analyze backend files
    backend_endpoints = analyze_backend_files(project_path, scan.backend_files)

    # 4. Detect mismatches
    issues = detect_mismatches(frontend_calls, backend_endpoints)

    # 5. Build architecture graph
    architecture = build_architecture(
        frontend_calls, backend_endpoints, issues, project_path
    )

    # 6. Build summary
    summary = {
        "total_frontend_calls": len(frontend_calls),
        "total_backend_endpoints": len(backend_endpoints),
        "total_issues": len(issues),
        "issues_by_type": {},
        "issues_by_severity": {"high": 0, "medium": 0, "low": 0},
        "frontend_files_scanned": len(scan.frontend_files),
        "backend_files_scanned": len(scan.backend_files),
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
        project_path=project_path,
        frontend_calls=frontend_calls,
        backend_endpoints=backend_endpoints,
        issues=issues,
        architecture=architecture,
        summary=summary,
    )

    _store[analysis_id] = result
    return result


def get_analysis(analysis_id: str) -> AnalysisResult | None:
    return _store.get(analysis_id)
