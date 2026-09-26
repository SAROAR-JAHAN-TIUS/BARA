"""
BARA Backend – Tests for all analyzer components.
"""
import sys
import os

# Ensure project is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.analyzers.normalizer import normalize_path, paths_match
from app.analyzers.frontend_analyzer import analyze_frontend_file
from app.analyzers.backend_analyzer import analyze_backend_file
from app.analyzers.mismatch_detector import detect_mismatches
from app.analyzers.scanner import scan_project
from app.analyzers.architecture_builder import build_architecture
from app.models.analysis import ApiCall, ApiEndpoint


# ──────────────────────────────────────────────────────────────────────────────
# Path Normalization Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalizer:
    def test_trailing_slash_stripped(self):
        assert normalize_path("/api/users/") == normalize_path("/api/users")

    def test_leading_slash_added(self):
        assert normalize_path("api/users") == "/api/users"

    def test_path_parameter_normalized(self):
        assert normalize_path("/api/users/{id}") == normalize_path("/api/users/:param")

    def test_numeric_segment_treated_as_param(self):
        assert normalize_path("/api/users/123") == normalize_path("/api/users/{id}")

    def test_uuid_segment_treated_as_param(self):
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert normalize_path(f"/api/users/{uuid}") == normalize_path("/api/users/{id}")

    def test_root_path(self):
        assert normalize_path("/") == "/"

    def test_paths_match_equivalent(self):
        assert paths_match("/api/users/", "/api/users")

    def test_paths_match_param_vs_concrete(self):
        assert paths_match("/api/users/42", "/api/users/{id}")

    def test_paths_dont_match_different_segments(self):
        assert not paths_match("/api/user", "/api/users")


# ──────────────────────────────────────────────────────────────────────────────
# Frontend Analyzer Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFrontendAnalyzer:
    def test_simple_fetch_get(self):
        source = 'const r = fetch("/api/users");'
        calls = analyze_frontend_file("test.js", source)
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].path == "/api/users"

    def test_fetch_post_with_body(self):
        source = '''fetch("/api/users", {
            method: "POST",
            body: JSON.stringify({ username: "alice", email: "a@b.com" })
        })'''
        calls = analyze_frontend_file("test.js", source)
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert calls[0].path == "/api/users"
        assert "username" in calls[0].body_fields

    def test_axios_get(self):
        source = 'axios.get("/api/todos");'
        calls = analyze_frontend_file("test.js", source)
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].path == "/api/todos"

    def test_axios_post(self):
        source = 'axios.post("/api/login", { email: "a@b.com", password: "pw" });'
        calls = analyze_frontend_file("test.js", source)
        assert len(calls) == 1
        assert calls[0].method == "POST"

    def test_query_params_extracted(self):
        source = 'fetch("/api/todos?limit=10&page=1");'
        calls = analyze_frontend_file("test.js", source)
        assert len(calls) == 1
        assert "limit" in calls[0].query_params
        assert "page" in calls[0].query_params

    def test_line_number_tracked(self):
        source = "\n\nfetch('/api/health');"
        calls = analyze_frontend_file("test.js", source)
        assert calls[0].line_number == 3

    def test_no_calls_in_empty_file(self):
        calls = analyze_frontend_file("empty.js", "// nothing here")
        assert calls == []

    def test_external_url_detected(self):
        source = 'fetch("https://example.com/api/data");'
        calls = analyze_frontend_file("test.js", source)
        # External URLs are still extracted (for reporting)
        assert len(calls) == 1
        assert "example.com" in calls[0].path


# ──────────────────────────────────────────────────────────────────────────────
# Backend Analyzer Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBackendAnalyzer:
    def test_simple_get_route(self):
        source = '''
@app.get("/api/users")
def get_users():
    return []
'''
        eps = analyze_backend_file("main.py", source)
        assert len(eps) == 1
        assert eps[0].method == "GET"
        assert eps[0].path == "/api/users"

    def test_post_route(self):
        source = '''
@app.post("/api/users")
def create_user(body: CreateUser):
    return {}
'''
        eps = analyze_backend_file("main.py", source)
        assert len(eps) == 1
        assert eps[0].method == "POST"

    def test_router_decorator(self):
        source = '''
@router.get("/api/items")
def list_items():
    return []
'''
        eps = analyze_backend_file("routes.py", source)
        assert len(eps) == 1
        assert eps[0].path == "/api/items"

    def test_pydantic_model_fields_extracted(self):
        source = '''
from pydantic import BaseModel

class CreateUserRequest(BaseModel):
    name: str
    email: str

@app.post("/api/register")
def register(body: CreateUserRequest):
    pass
'''
        eps = analyze_backend_file("main.py", source)
        assert len(eps) == 1
        assert "name" in eps[0].request_fields
        assert "email" in eps[0].request_fields

    def test_trailing_slash_stripped(self):
        source = '''
@app.get("/api/users/")
def get_users():
    return []
'''
        eps = analyze_backend_file("main.py", source)
        assert eps[0].path == "/api/users"

    def test_line_number_tracked(self):
        source = "\n\n@app.get('/api/health')\ndef health():\n    return 'ok'\n"
        eps = analyze_backend_file("main.py", source)
        assert eps[0].line_number == 3

    def test_no_routes_in_empty_file(self):
        eps = analyze_backend_file("empty.py", "# nothing")
        assert eps == []


# ──────────────────────────────────────────────────────────────────────────────
# Mismatch Detection Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMismatchDetector:
    def _call(self, method, path, body_fields=None, response_fields=None, query_params=None):
        return ApiCall(
            method=method, path=path,
            body_fields=body_fields or [],
            response_fields=response_fields or [],
            query_params=query_params or [],
            source_file="frontend.js", line_number=1,
        )

    def _ep(self, method, path, request_fields=None, response_fields=None):
        return ApiEndpoint(
            method=method, path=path,
            request_fields=request_fields or [],
            response_fields=response_fields or [],
            source_file="backend.py", line_number=1,
        )

    def test_missing_backend_endpoint(self):
        calls = [self._call("GET", "/api/users")]
        endpoints = []
        issues = detect_mismatches(calls, endpoints)
        assert len(issues) == 1
        assert issues[0].issue_type == "MISSING_BACKEND_ENDPOINT"
        assert issues[0].severity == "high"

    def test_method_mismatch(self):
        calls = [self._call("POST", "/api/login")]
        endpoints = [self._ep("GET", "/api/login")]
        issues = detect_mismatches(calls, endpoints)
        assert len(issues) == 1
        assert issues[0].issue_type == "METHOD_MISMATCH"
        assert issues[0].expected == "GET"
        assert issues[0].actual == "POST"

    def test_path_mismatch_detected_as_missing(self):
        """Frontend calls /api/users, backend has /api/user → MISSING_BACKEND_ENDPOINT."""
        calls = [self._call("GET", "/api/users")]
        endpoints = [self._ep("GET", "/api/user")]
        issues = detect_mismatches(calls, endpoints)
        assert any(i.issue_type == "MISSING_BACKEND_ENDPOINT" for i in issues)

    def test_request_field_mismatch(self):
        calls = [self._call("POST", "/api/register", body_fields=["username", "email"])]
        endpoints = [self._ep("POST", "/api/register", request_fields=["name", "email"])]
        issues = detect_mismatches(calls, endpoints)
        assert any(i.issue_type == "REQUEST_FIELD_MISMATCH" for i in issues)
        rf = next(i for i in issues if i.issue_type == "REQUEST_FIELD_MISMATCH")
        assert rf.actual == "username"

    def test_response_field_mismatch(self):
        calls = [self._call("GET", "/api/users", response_fields=["name"])]
        endpoints = [self._ep("GET", "/api/users", response_fields=["full_name"])]
        issues = detect_mismatches(calls, endpoints)
        assert any(i.issue_type == "RESPONSE_FIELD_MISMATCH" for i in issues)

    def test_query_param_mismatch(self):
        calls = [self._call("GET", "/api/todos", query_params=["limit"])]
        endpoints = [self._ep("GET", "/api/todos")]
        issues = detect_mismatches(calls, endpoints)
        assert any(i.issue_type == "QUERY_PARAM_MISMATCH" for i in issues)
        qp = next(i for i in issues if i.issue_type == "QUERY_PARAM_MISMATCH")
        assert qp.actual == "limit"

    def test_no_issues_for_correct_match(self):
        calls = [self._call("GET", "/api/health")]
        endpoints = [self._ep("GET", "/api/health")]
        issues = detect_mismatches(calls, endpoints)
        assert issues == []

    def test_issue_has_explanation_and_fix(self):
        calls = [self._call("GET", "/api/missing")]
        issues = detect_mismatches(calls, [])
        assert issues[0].explanation
        assert issues[0].suggested_fix

    def test_external_url_skipped(self):
        calls = [self._call("GET", "https://external.api.com/data")]
        issues = detect_mismatches(calls, [])
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────────
# Demo Project Integration Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestDemoProject:
    """Every intentional bug in the demo project must be detected."""

    DEMO_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "examples", "demo-project"
    )

    def test_demo_path_exists(self):
        assert os.path.isdir(self.DEMO_PATH), f"Demo project not found at {self.DEMO_PATH}"

    def test_demo_scan(self):
        scan = scan_project(self.DEMO_PATH)
        assert len(scan.frontend_files) > 0, "No frontend files found"
        assert len(scan.backend_files) > 0, "No backend files found"

    def test_demo_frontend_calls(self):
        from app.analyzers.frontend_analyzer import analyze_frontend_files
        scan = scan_project(self.DEMO_PATH)
        calls = analyze_frontend_files(self.DEMO_PATH, scan.frontend_files)
        paths = [c.path for c in calls]
        assert "/api/users" in paths, "BUG1: /api/users call not detected"
        assert "/api/login" in paths, "BUG2: /api/login call not detected"
        assert "/api/register" in paths, "BUG3: /api/register call not detected"

    def test_demo_backend_endpoints(self):
        from app.analyzers.backend_analyzer import analyze_backend_files
        scan = scan_project(self.DEMO_PATH)
        eps = analyze_backend_files(self.DEMO_PATH, scan.backend_files)
        paths = [e.path for e in eps]
        assert "/api/user" in paths, "Backend /api/user not detected"
        assert "/api/login" in paths, "Backend /api/login not detected"

    def test_demo_all_bugs_detected(self):
        """Run the full pipeline and assert all 5 bugs are detected."""
        from app.services.analysis_service import run_analysis
        from app.models.analysis import AnalysisRequest
        result = run_analysis(AnalysisRequest(project_path=self.DEMO_PATH))
        issue_types = [i.issue_type for i in result.issues]

        # BUG 1 – path mismatch (/api/users vs /api/user) → MISSING_BACKEND_ENDPOINT
        assert "MISSING_BACKEND_ENDPOINT" in issue_types, (
            f"BUG1 (PATH_MISMATCH) not detected. Issues: {issue_types}"
        )

        # BUG 2 – method mismatch POST vs GET /api/login
        assert "METHOD_MISMATCH" in issue_types, (
            f"BUG2 (METHOD_MISMATCH) not detected. Issues: {issue_types}"
        )

        # BUG 3 – request field mismatch username vs name
        assert "REQUEST_FIELD_MISMATCH" in issue_types, (
            f"BUG3 (REQUEST_FIELD_MISMATCH) not detected. Issues: {issue_types}"
        )

        # BUG 5 – query param limit vs page_size
        assert "QUERY_PARAM_MISMATCH" in issue_types, (
            f"BUG5 (QUERY_PARAM_MISMATCH) not detected. Issues: {issue_types}"
        )

    def test_demo_issues_have_explanations(self):
        from app.services.analysis_service import run_analysis
        from app.models.analysis import AnalysisRequest
        result = run_analysis(AnalysisRequest(project_path=self.DEMO_PATH))
        for issue in result.issues:
            assert issue.explanation, f"Issue {issue.issue_type} has no explanation"
            assert issue.suggested_fix, f"Issue {issue.issue_type} has no suggested fix"
            assert issue.severity in ("high", "medium", "low"), f"Invalid severity: {issue.severity}"


# ──────────────────────────────────────────────────────────────────────────────
# Scanner Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestScanner:
    def test_scan_demo_project(self):
        demo = os.path.join(
            os.path.dirname(__file__), "..", "..", "examples", "demo-project"
        )
        result = scan_project(demo)
        assert result.root == os.path.abspath(demo)
        assert len(result.files) > 0

    def test_scan_invalid_path(self):
        with pytest.raises(ValueError):
            scan_project("/nonexistent/path/xyz")

    def test_scan_skips_node_modules(self, tmp_path):
        # Create a fake project with node_modules
        fe_dir = tmp_path / "frontend"
        fe_dir.mkdir()
        (fe_dir / "package.json").write_text("{}")
        (fe_dir / "src").mkdir()
        (fe_dir / "src" / "index.js").write_text('fetch("/api/test");')
        nm = fe_dir / "node_modules" / "some-lib"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text('fetch("/should/not/appear");')
        result = scan_project(str(tmp_path))
        paths = [f.path for f in result.files]
        assert not any("node_modules" in p for p in paths)


# ──────────────────────────────────────────────────────────────────────────────
# HTTP API Tests (using TestClient)
# ──────────────────────────────────────────────────────────────────────────────

class TestHttpApi:
    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_analyze_endpoint_valid_project(self):
        from fastapi.testclient import TestClient
        from app.main import app
        demo = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "examples", "demo-project")
        )
        client = TestClient(app)
        r = client.post("/api/analyze", json={"project_path": demo})
        assert r.status_code == 200
        body = r.json()
        assert "analysis_id" in body
        assert "issues" in body
        assert len(body["issues"]) > 0

    def test_analyze_endpoint_invalid_path(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        r = client.post("/api/analyze", json={"project_path": "/nonexistent/path"})
        assert r.status_code == 400

    def test_get_analysis_by_id(self):
        from fastapi.testclient import TestClient
        from app.main import app
        demo = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "examples", "demo-project")
        )
        client = TestClient(app)
        r = client.post("/api/analyze", json={"project_path": demo})
        analysis_id = r.json()["analysis_id"]
        r2 = client.get(f"/api/analysis/{analysis_id}")
        assert r2.status_code == 200
        assert r2.json()["analysis_id"] == analysis_id

    def test_get_analysis_not_found(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        r = client.get("/api/analysis/nonexistent-id")
        assert r.status_code == 404
