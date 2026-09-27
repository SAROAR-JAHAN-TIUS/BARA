"""
BARA Backend – Pydantic data models.
"""
from __future__ import annotations
from typing import Any, List, Optional, Dict
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Scanner models
# ---------------------------------------------------------------------------

class ScannedFile(BaseModel):
    path: str
    language: str  # "js", "ts", "py", "java", "go", "cs", "rb", "php", etc.
    file_type: str  # "frontend", "backend", "config", "unknown"
    category: Optional[str] = None  # "page", "component", "service", "controller", "route", "model", "db", "config"


class ScanResult(BaseModel):
    root: str
    files: List[ScannedFile] = []
    frontend_files: List[str] = []
    backend_files: List[str] = []
    detected_technologies: List[str] = []
    project_type: str = "unknown"  # "fullstack", "frontend_only", "backend_only", "documentation_only"
    backend_framework: Optional[str] = None
    backend_status: str = "No backend/API code detected"  # "Framework detected" | "Unknown backend/API framework" | "No backend/API code detected"
    monorepo_packages: List[str] = []


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
    calling_context: Optional[str] = None  # Component/function name e.g. "LoginPage" or "login"
    framework: str = "fetch"  # "fetch", "axios", "react-query", "swr", "apollo", "custom-client"
    confidence: str = "high"  # "high", "medium", "low"
    evidence: str = ""  # Source code line snippet
    is_external: bool = False  # True if calling a remote 3rd-party domain


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
    controller: Optional[str] = None  # Controller/class/function name e.g. "AuthController.login"
    framework: str = "unknown"  # "FastAPI", "Flask", "Django", "Express", "Spring Boot", "Gin", etc.
    confidence: str = "high"  # "high", "medium", "low"
    evidence: str = ""  # Source code line snippet


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
    kind: str  # "PROJECT", "FRONTEND", "FRONTEND_FILE", "API_CLIENT", "API_REQUEST", "BACKEND", "ROUTE", "CONTROLLER", "SERVICE", "DATABASE", "EXTERNAL_API", "WEBSOCKET", "GRAPHQL", "AUTHENTICATION", "CONFIGURATION"
    label: str
    source_file: Optional[str] = None
    details: Dict[str, Any] = {}


class ArchEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    relation: str = "CALLS"  # "CONTAINS", "IMPORTS", "CALLS", "CONNECTS_TO", "ROUTES_TO", "HANDLES", "USES", "READS_FROM", "WRITES_TO", "AUTHENTICATES"
    status: str = "matched"  # "matched", "mismatch", "unhandled", "external"
    has_issue: bool = False


class Architecture(BaseModel):
    nodes: List[ArchNode] = []
    edges: List[ArchEdge] = []
    explanation: Optional[str] = None  # Explains graph when no backend exists


# ---------------------------------------------------------------------------
# Connection & Tree models
# ---------------------------------------------------------------------------

class ApiConnection(BaseModel):
    """Unified representation of a Frontend <-> Backend connection."""
    id: str
    frontend_call: Optional[ApiCall] = None
    backend_endpoint: Optional[ApiEndpoint] = None
    caller_location: Optional[str] = None  # e.g. "LoginPage.tsx:42"
    route_handler: Optional[str] = None   # e.g. "auth_controller.py:login"
    service: Optional[str] = None         # e.g. "auth_service.py:authenticate"
    database: Optional[str] = None        # e.g. "PostgreSQL / User"
    protocol: str = "http"                # "http", "websocket", "graphql"
    status: str = "MATCHED"               # "MATCHED", "MISSING_BACKEND_ENDPOINT", "METHOD_MISMATCH", "FIELD_MISMATCH", "QUERY_PARAM_MISMATCH", "PATH_PARAMETER_MISMATCH", "CONTENT_TYPE_MISMATCH", "AUTH_HEADER_MISMATCH", "UNUSED_BACKEND_ENDPOINT", "EXTERNAL", "UNKNOWN_BACKEND"
    resolved_path: str = ""
    method: str = "GET"
    issues: List[Issue] = []
    line_number_frontend: Optional[int] = None
    line_number_backend: Optional[int] = None


class RepositoryTreeNode(BaseModel):
    """Hierarchical node for repository structure view."""
    name: str
    path: str
    type: str = "file"  # "file" | "directory"
    role: Optional[str] = None  # "page", "component", "route", "controller", "service", "model", "db", "config", "client", "asset"
    language: Optional[str] = None
    children: Optional[List[RepositoryTreeNode]] = None


# ---------------------------------------------------------------------------
# Analysis models
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    """Request payload for /api/analyze.
    
    source_type: 'local' or 'github'
    source: absolute local path or GitHub HTTPS URL
    """
    source_type: str  # 'local' | 'github'
    source: str


class AnalysisResult(BaseModel):
    analysis_id: str
    source_type: str = "local"   # "local" | "github"
    source: str = ""             # original user input
    project_name: str = ""       # display name
    github_url: Optional[str] = None
    project_type: str = "unknown"
    backend_framework: Optional[str] = None
    backend_status: str = "No backend/API code detected"
    detected_technologies: List[str] = []
    scanned_files: List[ScannedFile] = []
    frontend_calls: List[ApiCall] = []
    backend_endpoints: List[ApiEndpoint] = []
    issues: List[Issue] = []
    architecture: Architecture = Architecture()
    api_connections: List[ApiConnection] = []
    repository_tree: Optional[RepositoryTreeNode] = None
    base_urls: Dict[str, str] = {}
    database_services: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {}
