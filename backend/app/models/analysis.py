"""
BARA Backend – Pydantic data models.
"""
from __future__ import annotations
from typing import Any, List, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Scanner models
# ---------------------------------------------------------------------------

class ScannedFile(BaseModel):
    path: str
    language: str  # "js", "ts", "py"
    file_type: str  # "frontend", "backend", "unknown"


class ScanResult(BaseModel):
    root: str
    files: List[ScannedFile] = []
    frontend_files: List[str] = []
    backend_files: List[str] = []


# ---------------------------------------------------------------------------
# API call / endpoint models
# ---------------------------------------------------------------------------

class ApiCall(BaseModel):
    """A frontend API call detected in source code."""
    method: str
    path: str
    query_params: List[str] = []
    body_fields: List[str] = []
    response_fields: List[str] = []
    source_file: str
    line_number: int


class ApiEndpoint(BaseModel):
    """A backend route detected in source code."""
    method: str
    path: str
    request_model: Optional[str] = None
    request_fields: List[str] = []
    response_model: Optional[str] = None
    response_fields: List[str] = []
    source_file: str
    line_number: int


# ---------------------------------------------------------------------------
# Issue models
# ---------------------------------------------------------------------------

class Location(BaseModel):
    file: str
    line: int


class Issue(BaseModel):
    issue_type: str
    severity: str  # "high" | "medium" | "low"
    frontend_location: Optional[Location] = None
    backend_location: Optional[Location] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    explanation: str
    suggested_fix: str


# ---------------------------------------------------------------------------
# Architecture models
# ---------------------------------------------------------------------------

class ArchNode(BaseModel):
    id: str
    kind: str  # "frontend_component", "backend_endpoint", "service", "database"
    label: str
    source_file: Optional[str] = None
    details: dict = {}


class ArchEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    has_issue: bool = False


class Architecture(BaseModel):
    nodes: List[ArchNode] = []
    edges: List[ArchEdge] = []


# ---------------------------------------------------------------------------
# Analysis models
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    """Request payload: provide an absolute path on the server's filesystem."""
    project_path: str


class AnalysisResult(BaseModel):
    analysis_id: str
    project_path: str
    frontend_calls: List[ApiCall] = []
    backend_endpoints: List[ApiEndpoint] = []
    issues: List[Issue] = []
    architecture: Architecture = Architecture()
    summary: dict = {}
