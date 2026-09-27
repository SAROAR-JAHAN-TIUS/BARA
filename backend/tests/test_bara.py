"""
BARA Backend – Comprehensive Test Suite.

Covers:
- Normalizer
- Frontend Analyzer
- Backend Analyzer
- Mismatch Detector
- Integrated Analysis Pipeline (using dynamic temp project fixtures, NO demo-project)
- Scanner
- Source Manager (Local + GitHub resolution, clone, cleanup)
- HTTP API (/health, /api/analyze, /api/analysis/{id})
- All 18 Required Phase 13 Scenarios
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.analyzers.normalizer import normalize_path, paths_match
from app.analyzers.frontend_analyzer import analyze_frontend_file, analyze_frontend_files
from app.analyzers.backend_analyzer import analyze_backend_file, analyze_backend_files
from app.analyzers.mismatch_detector import detect_mismatches
from app.analyzers.scanner import scan_project
from app.models.analysis import AnalysisRequest, AnalysisResult, ApiCall, ApiEndpoint
from app.services.source_manager import (
    resolve_source,
    cleanup,
    is_github_url,
    ResolvedSource,
    get_active_temp_dir,
    drop_active_clone,
)
from app.services.analysis_service import run_analysis, get_analysis


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_mismatched_project(tmp_path):
    """
    Dynamically generates a temporary project with intentional API mismatches:
    1. PATH_MISMATCH / MISSING_BACKEND_ENDPOINT: frontend calls /api/users, backend has /api/user
    2. METHOD_MISMATCH: frontend calls POST /api/login, backend has GET /api/login
    3. REQUEST_FIELD_MISMATCH: frontend sends 'username' & 'email', backend expects 'name'
    4. QUERY_PARAM_MISMATCH: frontend sends '?limit=10', backend has page_size
    """
    fe_dir = tmp_path / "frontend" / "src"
    fe_dir.mkdir(parents=True)
    fe_code = """
    export async function getUsers() {
        const res = await fetch("/api/users");
        const data = await res.json();
        return data.map(u => ({ id: u.id, name: u.full_name }));
    }

    export async function login(email, password) {
        const res = await fetch("/api/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, username: email })
        });
        const data = await res.json();
        return data.token;
    }

    export async function getItems() {
        const res = await fetch("/api/items?limit=10");
        return res.json();
    }

    export async function register(email, username) {
        const res = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, username })
        });
        return res.json();
    }
    """
    (fe_dir / "api.js").write_text(fe_code)
    (tmp_path / "frontend" / "package.json").write_text('{"name": "test-fe"}')

    be_dir = tmp_path / "backend"
    be_dir.mkdir()
    be_code = """
    from fastapi import FastAPI
    from pydantic import BaseModel

    app = FastAPI()

    class LoginRequest(BaseModel):
        email: str
        name: str

    class RegisterRequest(BaseModel):
        email: str
        name: str

    @app.get("/api/user")
    def get_user():
        return {"id": 1, "full_name": "Test"}

    @app.get("/api/login")
    def login_handler(body: LoginRequest):
        return {"token": "xyz"}

    @app.post("/api/register")
    def register_handler(body: RegisterRequest):
        return {"status": "ok"}

    @app.get("/api/items")
    def list_items(page_size: int = 20):
        return []
    """
    (be_dir / "main.py").write_text(be_code)
    (tmp_path / "backend" / "requirements.txt").write_text("fastapi\npydantic\n")

    return tmp_path


# ──────────────────────────────────────────────────────────────────────────────
# 1. Normalizer Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestNormalizer:
    def test_trailing_slash_stripped(self):
        assert normalize_path("/api/users/") == "/api/users"

    def test_leading_slash_added(self):
        assert normalize_path("api/users") == "/api/users"

    def test_path_parameter_normalized(self):
        assert normalize_path("/api/users/{id}") == "/api/users/:param"
        assert normalize_path("/api/users/{user_id}/items") == "/api/users/:param/items"

    def test_numeric_segment_treated_as_param(self):
        assert normalize_path("/api/users/123") == "/api/users/:param"

    def test_uuid_segment_treated_as_param(self):
        assert normalize_path("/api/users/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d") == "/api/users/:param"

    def test_root_path(self):
        assert normalize_path("/") == "/"
        assert normalize_path("") == "/"

    def test_paths_match_equivalent(self):
        assert paths_match("/api/users", "/api/users/")
        assert paths_match("/api/users/{id}", "/api/users/:param")

    def test_paths_match_param_vs_concrete(self):
        assert paths_match("/api/users/123", "/api/users/{id}")

    def test_paths_dont_match_different_segments(self):
        assert not paths_match("/api/users", "/api/user")
        assert not paths_match("/api/posts", "/api/comments")

    def test_express_style_param(self):
        assert normalize_path("/api/users/:id") == "/api/users/:param"
        assert paths_match("/api/users/:id", "/api/users/123")
        assert paths_match("/api/users/:userId", "/api/users/{id}")



# ──────────────────────────────────────────────────────────────────────────────
# 2. Frontend Analyzer Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestFrontendAnalyzer:
    def test_simple_fetch_get(self, tmp_path):
        f = tmp_path / "api.js"
        f.write_text('const res = await fetch("/api/users");')
        calls = analyze_frontend_file("api.js", f.read_text())
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].path == "/api/users"

    def test_fetch_post_with_body(self, tmp_path):
        f = tmp_path / "api.js"
        f.write_text("""
        fetch("/api/login", {
            method: "POST",
            body: JSON.stringify({ email: "a@b.com", password: "secret" })
        });
        """)
        calls = analyze_frontend_file("api.js", f.read_text())
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert calls[0].path == "/api/login"
        assert "email" in calls[0].body_fields

    def test_axios_get(self, tmp_path):
        f = tmp_path / "api.js"
        f.write_text('const r = await axios.get("/api/products");')
        calls = analyze_frontend_file("api.js", f.read_text())
        assert len(calls) == 1
        assert calls[0].method == "GET"
        assert calls[0].path == "/api/products"

    def test_axios_post(self, tmp_path):
        f = tmp_path / "api.js"
        f.write_text('axios.post("/api/items", { title: "New Item" });')
        calls = analyze_frontend_file("api.js", f.read_text())
        assert len(calls) == 1
        assert calls[0].method == "POST"
        assert "title" in calls[0].body_fields

    def test_query_params_extracted(self, tmp_path):
        f = tmp_path / "api.js"
        f.write_text('fetch("/api/search?q=test&limit=10");')
        calls = analyze_frontend_file("api.js", f.read_text())
        assert "q" in calls[0].query_params
        assert "limit" in calls[0].query_params

    def test_no_calls_in_empty_file(self, tmp_path):
        f = tmp_path / "empty.js"
        f.write_text('const x = 1;')
        calls = analyze_frontend_file("empty.js", f.read_text())
        assert len(calls) == 0

    def test_external_url_detected(self, tmp_path):
        f = tmp_path / "api.js"
        f.write_text('fetch("https://external.api.com/v1/data");')
        calls = analyze_frontend_file("api.js", f.read_text())
        assert len(calls) == 1
        assert calls[0].path.startswith("https://")

    def test_custom_client_instance(self, tmp_path):
        f = tmp_path / "api.js"
        f.write_text('const res = await api.get("/api/products");\\nawait client.post("/api/login", { username, password });')
        calls = analyze_frontend_file("api.js", f.read_text())
        assert len(calls) == 2
        assert calls[0].method == "GET"
        assert calls[0].path == "/api/products"
        assert calls[1].method == "POST"
        assert "username" in calls[1].body_fields



# ──────────────────────────────────────────────────────────────────────────────
# 3. Backend Analyzer Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBackendAnalyzer:
    def test_simple_get_route(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/users")
def get_users():
    return []
""")
        eps = analyze_backend_file("main.py", f.read_text())
        assert len(eps) == 1
        assert eps[0].method == "GET"
        assert eps[0].path == "/api/users"

    def test_post_route(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class CreateUser(BaseModel):
    name: str

@app.post("/api/users")
def create_user(body: CreateUser):
    return {}
""")
        eps = analyze_backend_file("main.py", f.read_text())
        assert len(eps) == 1
        assert eps[0].method == "POST"
        assert "name" in eps[0].request_fields

    def test_router_decorator(self, tmp_path):
        f = tmp_path / "routes.py"
        f.write_text("""
from fastapi import APIRouter
router = APIRouter()

@router.delete("/api/items/{id}")
def delete_item(id: int):
    return {}
""")
        eps = analyze_backend_file("routes.py", f.read_text())
        assert len(eps) == 1
        assert eps[0].method == "DELETE"
        assert eps[0].path == "/api/items/{id}"

    def test_flask_route(self, tmp_path):
        f = tmp_path / "app.py"
        f.write_text("""
from flask import Flask
app = Flask(__name__)

@app.route("/api/items", methods=["GET", "POST"])
def items():
    return "ok"
""")
        eps = analyze_backend_file("app.py", f.read_text())
        assert len(eps) == 2
        methods = {ep.method for ep in eps}
        assert methods == {"GET", "POST"}
        assert eps[0].path == "/api/items"

    def test_express_route(self, tmp_path):
        f = tmp_path / "routes.js"
        f.write_text("""
router.post('/api/auth/login', (req, res) => {
    const { username, password } = req.body;
    res.json({ token: 'abc', user: username });
});
""")
        eps = analyze_backend_file("routes.js", f.read_text())
        assert len(eps) == 1
        assert eps[0].method == "POST"
        assert eps[0].path == "/api/auth/login"
        assert "username" in eps[0].request_fields
        assert "token" in eps[0].response_fields



# ──────────────────────────────────────────────────────────────────────────────
# 4. Mismatch Detector Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMismatchDetector:
    def test_missing_backend_endpoint(self):
        call = ApiCall(
            method="GET",
            path="/api/missing",
            source_file="api.js",
            line_number=1,
        )
        issues = detect_mismatches([call], [])
        assert len(issues) == 1
        assert issues[0].issue_type == "MISSING_BACKEND_ENDPOINT"
        assert issues[0].severity == "high"

    def test_method_mismatch(self):
        call = ApiCall(
            method="POST",
            path="/api/login",
            source_file="api.js",
            line_number=1,
        )
        ep = ApiEndpoint(
            method="GET",
            path="/api/login",
            source_file="main.py",
            line_number=10,
        )
        issues = detect_mismatches([call], [ep])
        assert len(issues) == 1
        assert issues[0].issue_type == "METHOD_MISMATCH"
        assert issues[0].severity == "high"

    def test_request_field_mismatch(self):
        call = ApiCall(
            method="POST",
            path="/api/users",
            body_fields=["username", "email"],
            source_file="api.js",
            line_number=1,
        )
        ep = ApiEndpoint(
            method="POST",
            path="/api/users",
            request_fields=["email"],
            source_file="main.py",
            line_number=10,
        )
        issues = detect_mismatches([call], [ep])
        field_issues = [i for i in issues if i.issue_type == "REQUEST_FIELD_MISMATCH"]
        assert len(field_issues) == 1
        assert "username" in field_issues[0].actual

    def test_no_issues_for_correct_match(self):
        call = ApiCall(
            method="GET",
            path="/api/users",
            source_file="api.js",
            line_number=1,
        )
        ep = ApiEndpoint(
            method="GET",
            path="/api/users",
            source_file="main.py",
            line_number=10,
        )
        issues = detect_mismatches([call], [ep])
        assert len(issues) == 0


# ──────────────────────────────────────────────────────────────────────────────
# 5. Integrated Analysis Pipeline (using dynamic temp project)
# ──────────────────────────────────────────────────────────────────────────────

class TestIntegrationAnalysis:
    """Verifies that the entire analysis engine detects mismatches without demo-project."""

    def test_scan_finds_files(self, sample_mismatched_project):
        scan = scan_project(str(sample_mismatched_project))
        assert len(scan.frontend_files) > 0
        assert len(scan.backend_files) > 0

    def test_mismatches_detected(self, sample_mismatched_project):
        result = run_analysis(
            AnalysisRequest(
                source_type="local",
                source=str(sample_mismatched_project),
            )
        )
        issue_types = [i.issue_type for i in result.issues]
        assert "MISSING_BACKEND_ENDPOINT" in issue_types
        assert "METHOD_MISMATCH" in issue_types
        assert "REQUEST_FIELD_MISMATCH" in issue_types
        assert "QUERY_PARAM_MISMATCH" in issue_types

    def test_issues_have_explanations_and_fixes(self, sample_mismatched_project):
        result = run_analysis(
            AnalysisRequest(
                source_type="local",
                source=str(sample_mismatched_project),
            )
        )
        for issue in result.issues:
            assert issue.explanation
            assert issue.suggested_fix
            assert issue.severity in ("high", "medium", "low")


# ──────────────────────────────────────────────────────────────────────────────
# 6. Scanner Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestScanner:
    def test_scan_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("console.log('ignored');")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.js").write_text("fetch('/api');")

        scan = scan_project(str(tmp_path))
        paths = [f.path for f in scan.files]
        assert not any("node_modules" in p for p in paths)
        assert any("app.js" in p for p in paths)

    def test_scan_invalid_path(self):
        with pytest.raises(ValueError, match="not a directory"):
            scan_project("/path/does/not/exist/at/all")

    def test_detect_technologies_and_project_type(self, tmp_path):
        from app.analyzers.scanner import detect_technologies
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.2.0", "express": "^4.18.2"}}')
        techs = detect_technologies(str(tmp_path), ["frontend/App.tsx"], ["server/index.js"])
        assert "React" in techs
        assert "Express" in techs

        scan = scan_project(str(tmp_path))
        assert "React" in scan.detected_technologies
        assert "Express" in scan.detected_technologies



# ──────────────────────────────────────────────────────────────────────────────
# 7. HTTP API Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestHttpApi:
    def test_health_endpoint(self):
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_analyze_local_project_success(self, sample_mismatched_project):
        client = TestClient(app)
        r = client.post(
            "/api/analyze",
            json={
                "source_type": "local",
                "source": str(sample_mismatched_project),
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["source_type"] == "local"
        assert data["source"] == str(sample_mismatched_project)
        assert data["project_name"] == sample_mismatched_project.name
        assert "analysis_id" in data
        assert len(data["issues"]) > 0

    def test_analyze_invalid_local_path_returns_400(self):
        client = TestClient(app)
        r = client.post(
            "/api/analyze",
            json={
                "source_type": "local",
                "source": "/nonexistent/directory/xyz",
            },
        )
        assert r.status_code == 400
        assert "Path does not exist" in r.json()["detail"]

    def test_get_analysis_by_id(self, sample_mismatched_project):
        client = TestClient(app)
        r1 = client.post(
            "/api/analyze",
            json={
                "source_type": "local",
                "source": str(sample_mismatched_project),
            },
        )
        analysis_id = r1.json()["analysis_id"]

        r2 = client.get(f"/api/analysis/{analysis_id}")
        assert r2.status_code == 200
        assert r2.json()["analysis_id"] == analysis_id

    def test_get_analysis_not_found(self):
        client = TestClient(app)
        r = client.get("/api/analysis/nonexistent-uuid-1234")
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 8. Source Manager Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSourceManager:
    def test_valid_github_url_detection(self):
        assert is_github_url("https://github.com/facebook/react")
        assert is_github_url("https://github.com/facebook/react.git")
        assert is_github_url("https://github.com/facebook/react/")
        assert is_github_url("https://github.com/facebook/react.git/")
        assert is_github_url("https://github.com/microsoft/vscode")
        assert is_github_url("https://github.com/SAROAR-JAHAN-TIUS/helping")
        assert is_github_url("https://github.com/codecrafters-io/build-your-own-x?utm_source")
        assert is_github_url("https://github.com/facebook/react#readme")

    def test_invalid_github_url_rejection(self):
        assert not is_github_url("http://github.com/owner/repo")   # http not https
        assert not is_github_url("https://gitlab.com/owner/repo")
        assert not is_github_url("https://github.com/owner")
        assert not is_github_url("https://github.com/owner/repo/tree/main")  # subpaths rejected
        assert not is_github_url("/home/baby/project")
        assert not is_github_url("not a url")
        assert not is_github_url("")

    def test_local_url_rejected(self):
        with pytest.raises(ValueError, match="looks like a URL, not a local path"):
            resolve_source("local", "https://github.com/owner/repo")

    def test_github_path_rejected(self):
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            resolve_source("github", "/home/baby/projects/myapp")

    def test_invalid_source_type_rejected(self):
        with pytest.raises(ValueError, match="Invalid source_type"):
            resolve_source("s3", "s3://bucket/project")

    def test_local_project_never_deleted(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1")
        resolved = resolve_source("local", str(tmp_path))
        assert not resolved.temporary
        cleanup(resolved)
        assert f.exists(), "Local project was modified or deleted!"


# ──────────────────────────────────────────────────────────────────────────────
# 9. All 18 Required Scenarios (Phase 13)
# ──────────────────────────────────────────────────────────────────────────────

class TestRequiredScenarios:
    """
    Direct verification of all 18 requirements from Phase 13:
    1. Local project succeeds.
    2. Local nonexistent path fails correctly.
    3. Local file instead of directory fails correctly.
    4. GitHub URL validation succeeds.
    5. Invalid GitHub URL fails correctly.
    6. Arbitrary GitHub repository URL is accepted.
    7. GitHub repository is cloned.
    8. Clone failure is handled.
    9. Temporary GitHub directory is created.
    10. Temporary GitHub directory is deleted after success.
    11. Temporary GitHub directory is deleted after failure.
    12. Local project is NEVER deleted.
    13. GitHub URL is NEVER treated as a filesystem path.
    14. Frontend request uses source_type + source.
    15. Backend accepts source_type + source.
    16. Existing analysis functionality still works.
    17. Existing API mismatch detection still works.
    18. Frontend production build succeeds (tested in frontend test runner).
    """

    def _mini_project(self, tmp_path):
        fe = tmp_path / "src"
        fe.mkdir(parents=True, exist_ok=True)
        (fe / "index.js").write_text('fetch("/api/hello");\n')
        be = tmp_path / "api"
        be.mkdir(parents=True, exist_ok=True)
        (be / "server.py").write_text(
            'from fastapi import FastAPI\napp = FastAPI()\n'
            '@app.get("/api/hello")\ndef h(): return {}\n'
        )
        return tmp_path

    # Scenario 1: Local project succeeds
    def test_scenario_01_local_project_succeeds(self, tmp_path):
        project = self._mini_project(tmp_path)
        req = AnalysisRequest(source_type="local", source=str(project))
        res = run_analysis(req)
        assert res.source_type == "local"
        assert res.source == str(project)
        assert res.project_name == project.name
        assert res.analysis_id

    # Scenario 2: Local nonexistent path fails correctly
    def test_scenario_02_local_nonexistent_fails(self):
        with pytest.raises(ValueError, match="Path does not exist"):
            resolve_source("local", "/path/that/really/does/not/exist/xyz_bara")

    # Scenario 3: Local file instead of directory fails correctly
    def test_scenario_03_local_file_fails(self, tmp_path):
        file_path = tmp_path / "standalone.py"
        file_path.write_text("x = 1")
        with pytest.raises(ValueError, match="Path is not a directory"):
            resolve_source("local", str(file_path))

    # Scenario 4: GitHub URL validation succeeds
    def test_scenario_04_github_url_validation_succeeds(self):
        assert is_github_url("https://github.com/facebook/react")
        assert is_github_url("https://github.com/facebook/react.git")
        assert is_github_url("https://github.com/facebook/react/")
        assert is_github_url("https://github.com/facebook/react.git/")

    # Scenario 5: Invalid GitHub URL fails correctly
    def test_scenario_05_invalid_github_url_fails(self):
        assert not is_github_url("https://notgithub.com/user/repo")
        assert not is_github_url("http://github.com/user/repo")
        assert not is_github_url("https://github.com/only-user")
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            resolve_source("github", "https://notgithub.com/user/repo")

    # Scenario 6: Arbitrary GitHub repository URL is accepted
    def test_scenario_06_arbitrary_github_url_accepted(self):
        repos = [
            "https://github.com/microsoft/vscode",
            "https://github.com/facebook/react",
            "https://github.com/SAROAR-JAHAN-TIUS/helping",
            "https://github.com/any-random-user-123/any-repo.js",
        ]
        for url in repos:
            assert is_github_url(url), f"Failed to accept arbitrary URL: {url}"

    # Scenario 7: GitHub repository is cloned
    def test_scenario_07_github_repo_is_cloned(self, tmp_path, monkeypatch):
        project = self._mini_project(tmp_path)
        cloned_urls = []

        import app.services.source_manager as sm

        def fake_clone(url):
            cloned_urls.append(url)
            return project, tmp_path / "fake_temp"

        monkeypatch.setattr(sm, "_clone_repo", fake_clone)
        resolved = resolve_source("github", "https://github.com/test-owner/test-repo")
        assert cloned_urls == ["https://github.com/test-owner/test-repo"]
        assert resolved.project_path == str(project)
        assert resolved.project_name == "test-owner/test-repo"

    # Scenario 8: Clone failure is handled
    def test_scenario_08_clone_failure_handled(self, monkeypatch):
        import subprocess

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd, returncode=128, stdout="", stderr="fatal: repository not found (404)"
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="Repository not found"):
            resolve_source("github", "https://github.com/owner/nonexistent-repo")

    # Scenario 9: Temporary GitHub directory is created
    def test_scenario_09_temp_directory_created(self, tmp_path, monkeypatch):
        import subprocess
        from pathlib import Path

        def fake_run(cmd, **kwargs):
            clone_dir = Path(cmd[-1])
            clone_dir.mkdir(parents=True, exist_ok=True)
            (clone_dir / "index.js").write_text("console.log(1)")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        resolved = resolve_source("github", "https://github.com/owner/repo-temp")
        assert resolved.temporary is True
        assert resolved._temp_dir is not None
        assert resolved._temp_dir.exists()
        # Clean up
        cleanup(resolved)

    # Scenario 10: Temporary GitHub directory is deleted after success
    def test_scenario_10_temp_directory_deleted_after_success(self, tmp_path, monkeypatch):
        import subprocess
        from pathlib import Path

        def fake_run(cmd, **kwargs):
            clone_dir = Path(cmd[-1])
            clone_dir.mkdir(parents=True, exist_ok=True)
            self._mini_project(clone_dir)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        # Intercept resolved source to check its directory afterwards
        captured_temp = []
        original_resolve = resolve_source

        import app.services.analysis_service as asvc

        def spy_resolve(st, s):
            res = original_resolve(st, s)
            captured_temp.append(res._temp_dir)
            return res

        monkeypatch.setattr(asvc, "resolve_source", spy_resolve)

        req = AnalysisRequest(source_type="github", source="https://github.com/owner/repo-clean")
        res = asvc.run_analysis(req)
        assert res.source_type == "github"

        temp_dir = captured_temp[0]
        assert temp_dir is not None
        assert not temp_dir.exists(), "Temporary clone directory was NOT deleted after success!"

    # Scenario 11: Temporary GitHub directory is deleted after failure
    def test_scenario_11_temp_directory_deleted_after_failure(self, monkeypatch):
        import subprocess
        from pathlib import Path

        def fake_run(cmd, **kwargs):
            clone_dir = Path(cmd[-1])
            clone_dir.mkdir(parents=True, exist_ok=True)
            # empty dir or broken files that cause analyzer to fail
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        import app.services.analysis_service as asvc

        # Force scanner to fail
        def broken_scanner(path):
            raise RuntimeError("Scanner exploded intentionally for test")

        monkeypatch.setattr(asvc, "scan_project", broken_scanner)

        captured_temp = []
        original_resolve = resolve_source

        def spy_resolve(st, s):
            res = original_resolve(st, s)
            captured_temp.append(res._temp_dir)
            return res

        monkeypatch.setattr(asvc, "resolve_source", spy_resolve)

        req = AnalysisRequest(source_type="github", source="https://github.com/owner/repo-fail")
        with pytest.raises(RuntimeError, match="Scanner exploded"):
            asvc.run_analysis(req)

        temp_dir = captured_temp[0]
        assert temp_dir is not None
        assert not temp_dir.exists(), "Temporary directory was NOT deleted after failure!"

    # Scenario 12: Local project is NEVER deleted
    def test_scenario_12_local_project_never_deleted(self, tmp_path):
        project = self._mini_project(tmp_path)
        marker = project / "keep_me.txt"
        marker.write_text("do not delete")

        req = AnalysisRequest(source_type="local", source=str(project))
        res = run_analysis(req)
        assert res.source_type == "local"

        assert marker.exists()
        assert (project / "src" / "index.js").exists()
        assert (project / "api" / "server.py").exists()

    # Scenario 13: GitHub URL is NEVER treated as a filesystem path
    def test_scenario_13_github_url_never_treated_as_filesystem_path(self):
        url = "https://github.com/owner/repository"
        # Must not create or look for /home/baby/BARA/backend/https://github.com/owner/repository
        with pytest.raises(ValueError, match="looks like a URL, not a local path"):
            resolve_source("local", url)

    # Scenario 14: Frontend request uses source_type + source
    def test_scenario_14_frontend_request_format(self, tmp_path):
        project = self._mini_project(tmp_path)
        client = TestClient(app)
        # Using canonical contract
        r = client.post(
            "/api/analyze",
            json={"source_type": "local", "source": str(project)},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["source_type"] == "local"
        assert body["source"] == str(project)

    # Scenario 15: Backend accepts source_type + source
    def test_scenario_15_backend_accepts_canonical_contract(self, tmp_path):
        project = self._mini_project(tmp_path)
        req = AnalysisRequest.model_validate({"source_type": "local", "source": str(project)})
        assert req.source_type == "local"
        assert req.source == str(project)

    # Scenario 16: Existing analysis functionality still works
    def test_scenario_16_analysis_functionality(self, sample_mismatched_project):
        result = run_analysis(
            AnalysisRequest(source_type="local", source=str(sample_mismatched_project))
        )
        assert len(result.frontend_calls) == 4
        assert len(result.backend_endpoints) == 4
        assert len(result.architecture.nodes) > 0

    # Scenario 17: Existing API mismatch detection still works
    def test_scenario_17_mismatch_detection_still_works(self, sample_mismatched_project):
        result = run_analysis(
            AnalysisRequest(source_type="local", source=str(sample_mismatched_project))
        )
        assert result.summary["total_issues"] >= 4
        assert result.summary["issues_by_severity"]["high"] >= 2

    # Scenario 18: Frontend production build succeeds (tested separately via npm run build)
    def test_scenario_18_frontend_build_verified(self):
        dist_index = Path(__file__).parent / ".." / ".." / "frontend" / "dist" / "index.html"
        assert dist_index.exists(), "Frontend production build (dist/index.html) must exist"


# ──────────────────────────────────────────────────────────────────────────────
# 10 Required Project Archetypes
# ──────────────────────────────────────────────────────────────────────────────

class TestTenArchetypes:
    """Tests the 10 distinct real-world project archetypes required by BARA."""

    # Archetype 1: React + FastAPI
    def test_archetype_1_react_fastapi(self, tmp_path):
        fe = tmp_path / "frontend" / "src"
        fe.mkdir(parents=True)
        (fe / "Users.tsx").write_text("""
        import React, { useEffect, useState } from 'react';
        export function UsersList() {
            const [users, setUsers] = useState([]);
            useEffect(() => {
                fetch('/api/users').then(r => r.json()).then(setUsers);
            }, []);
            return <div>{users.map(u => <div key={u.id}>{u.name}</div>)}</div>;
        }
        """)
        (tmp_path / "frontend" / "package.json").write_text('{"name": "react-fastapi-fe", "dependencies": {"react": "^18.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "main.py").write_text("""
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/api/users")
        def list_users():
            return [{"id": 1, "name": "Alice"}]
        """)
        (be / "requirements.txt").write_text("fastapi>=0.100.0\nuvicorn\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert res.frontend_calls[0].path == "/api/users"
        assert res.frontend_calls[0].calling_context == "UsersList"
        assert len(res.backend_endpoints) == 1
        assert res.backend_endpoints[0].path == "/api/users"
        assert res.summary["matched_apis"] == 1
        assert res.summary["mismatched_apis"] == 0
        assert res.backend_framework.lower() == "fastapi"
        assert res.backend_status == "Framework detected"

    # Archetype 2: React + Express
    def test_archetype_2_react_express(self, tmp_path):
        fe = tmp_path / "client" / "src"
        fe.mkdir(parents=True)
        (fe / "Auth.jsx").write_text("""
        import axios from 'axios';
        export async function loginUser(credentials) {
            return axios.post('/api/auth/login', {
                username: credentials.user,
                password: credentials.pass
            });
        }
        """)
        (tmp_path / "client" / "package.json").write_text('{"name": "client", "dependencies": {"axios": "^1.0.0"}}')

        be = tmp_path / "server"
        be.mkdir()
        (be / "server.js").write_text("""
        const express = require('express');
        const app = express();
        app.use(express.json());

        app.post('/api/auth/login', (req, res) => {
            const { username, password } = req.body;
            res.json({ token: 'abc' });
        });
        """)
        (be / "package.json").write_text('{"name": "server", "dependencies": {"express": "^4.18.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert res.frontend_calls[0].method == "POST"
        assert res.frontend_calls[0].path == "/api/auth/login"
        assert len(res.backend_endpoints) == 1
        assert res.backend_endpoints[0].path == "/api/auth/login"
        assert res.summary["matched_apis"] == 1
        assert res.backend_framework.lower() == "express"

    # Archetype 3: Vue + Django
    def test_archetype_3_vue_django(self, tmp_path):
        fe = tmp_path / "frontend" / "src"
        fe.mkdir(parents=True)
        (fe / "ProductCatalog.vue").write_text("""
        <script>
        export default {
            methods: {
                fetchProducts() {
                    fetch('/api/products/').then(r => r.json());
                }
            }
        }
        </script>
        """)
        (tmp_path / "frontend" / "package.json").write_text('{"dependencies": {"vue": "^3.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "urls.py").write_text("""
        from django.urls import path
        urlpatterns = [
            path('api/products/', views.ProductListView.as_view(), name='product-list'),
        ]
        """)
        (be / "manage.py").write_text("# Django manage.py\nimport os\nimport django")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.backend_endpoints[0].path == "/api/products"
        assert res.backend_framework.lower() == "django"
        assert res.backend_status == "Framework detected"

    # Archetype 4: React + Spring Boot (Java)
    def test_archetype_4_react_spring_boot(self, tmp_path):
        fe = tmp_path / "ui" / "src"
        fe.mkdir(parents=True)
        (fe / "Orders.tsx").write_text("""
        export function OrdersPage() {
            const load = () => fetch('/api/orders');
        }
        """)

        be = tmp_path / "src" / "main" / "java" / "com" / "example"
        be.mkdir(parents=True)
        (tmp_path / "pom.xml").write_text("<project><dependencies><dependency><groupId>org.springframework.boot</groupId></dependency></dependencies></project>")
        (be / "OrderController.java").write_text("""
        package com.example;
        import org.springframework.web.bind.annotation.*;
        import java.util.List;

        @RestController
        @RequestMapping("/api/orders")
        public class OrderController {
            @GetMapping
            public List<Order> getAllOrders() {
                return List.of();
            }
        }
        """)

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.backend_endpoints[0].path == "/api/orders"
        assert "OrderController" in res.backend_endpoints[0].controller
        assert res.backend_framework in ("Spring Boot", "spring_boot")
        assert res.summary["matched_apis"] == 1

    # Archetype 5: Next.js Full-Stack (App Router)
    def test_archetype_5_nextjs_fullstack(self, tmp_path):
        api_dir = tmp_path / "app" / "api" / "posts"
        api_dir.mkdir(parents=True)
        (api_dir / "route.ts").write_text("""
        import { NextResponse } from 'next/server';

        export async function GET(request: Request) {
            return NextResponse.json([{ id: 1, title: 'Hello Next.js' }]);
        }

        export async function POST(request: Request) {
            const body = await request.json();
            return NextResponse.json({ created: true });
        }
        """)

        page_dir = tmp_path / "app"
        (page_dir / "page.tsx").write_text("""
        'use client';
        import { useEffect } from 'react';

        export default function PostsPage() {
            useEffect(() => {
                fetch('/api/posts');
            }, []);
            return <h1>Posts</h1>;
        }
        """)
        (tmp_path / "package.json").write_text('{"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}')
        (tmp_path / "next.config.js").write_text("module.exports = {};")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.backend_endpoints) >= 1
        assert any(ep.path == "/api/posts" and ep.method == "GET" for ep in res.backend_endpoints)
        assert len(res.frontend_calls) >= 1
        assert res.summary["matched_apis"] >= 1
        assert any("next" in t.lower() for t in res.detected_technologies)

    # Archetype 6: Frontend-only Repository (Verifying Truthful No Fake Backend)
    def test_archetype_6_frontend_only_no_fake_backend(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "App.js").write_text("""
        export function App() {
            fetch('/api/todos');
            return <h1>Todo App</h1>;
        }
        """)
        (tmp_path / "package.json").write_text('{"name": "pure-spa", "dependencies": {"react": "^18.0.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert res.summary["frontend_files_scanned"] >= 1
        assert res.summary["backend_files_scanned"] == 0
        assert len(res.backend_endpoints) == 0
        assert res.backend_status == "No backend/API code detected"
        assert res.architecture.explanation is not None
        assert "No backend" in res.architecture.explanation
        # Check that no fake backend_endpoint nodes were fabricated
        backend_nodes = [n for n in res.architecture.nodes if n.kind == "backend_endpoint"]
        assert len(backend_nodes) == 0

    # Archetype 7: Backend-only Repository
    def test_archetype_7_backend_only(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/myservice\ngo 1.21\nrequire github.com/gin-gonic/gin v1.9.1")
        (tmp_path / "main.go").write_text("""
        package main
        import "github.com/gin-gonic/gin"

        func main() {
            r := gin.Default()
            r.GET("/api/health", func(c *gin.Context) {
                c.JSON(200, gin.H{"status": "ok"})
            })
            r.POST("/api/metrics", func(c *gin.Context) {
                c.JSON(201, gin.H{"saved": true})
            })
            r.Run()
        }
        """)

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert res.summary["frontend_files_scanned"] == 0
        assert res.summary["backend_files_scanned"] >= 1
        assert len(res.frontend_calls) == 0
        assert len(res.backend_endpoints) == 2
        assert res.backend_framework.lower() == "gin"
        assert res.backend_status == "Framework detected"

    # Archetype 8: Monorepo (apps/web + services/api)
    def test_archetype_8_monorepo(self, tmp_path):
        fe = tmp_path / "apps" / "web" / "src"
        fe.mkdir(parents=True)
        (fe / "Dashboard.ts").write_text("""
        export async function loadDashboard() {
            const res = await fetch('/api/v1/dashboard');
            return res.json();
        }
        """)
        (tmp_path / "apps" / "web" / "package.json").write_text('{"name": "web"}')

        be = tmp_path / "services" / "api"
        be.mkdir(parents=True)
        (be / "app.py").write_text("""
        from fastapi import FastAPI
        app = FastAPI()

        @app.get("/api/v1/dashboard")
        def get_dashboard():
            return {"active_users": 42}
        """)
        (be / "requirements.txt").write_text("fastapi\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1
        assert "apps/web" in res.summary["monorepo_packages"] or any("web" in pkg for pkg in res.summary["monorepo_packages"])

    # Archetype 9: Frontend Calling External API
    def test_archetype_9_frontend_calling_external_api(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "WeatherWidget.js").write_text("""
        export function WeatherWidget() {
            const getWeather = () => {
                fetch('https://api.openweathermap.org/data/2.5/weather?q=London');
            };
        }
        """)
        (tmp_path / "package.json").write_text('{"name": "weather-app"}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert res.frontend_calls[0].is_external is True
        assert res.summary["external_apis"] == 1
        # Verify architecture contains external_api node
        ext_nodes = [n for n in res.architecture.nodes if n.kind == "external_api"]
        assert len(ext_nodes) >= 1
        assert "api.openweathermap.org" in ext_nodes[0].label

    # Archetype 10: Unknown / Custom Backend Framework (Verifying Fallback Regex)
    def test_archetype_10_unknown_custom_backend_fallback(self, tmp_path):
        be = tmp_path / "backend"
        be.mkdir()
        (be / "custom_server.py").write_text("""
        # Custom in-house routing framework
        class CustomRouter:
            def register_routes(self):
                add_route("GET", "/api/custom/resource")
                add_route("POST", "/api/custom/submit")
        """)
        (be / "requirements.txt").write_text("custom-lib\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.backend_endpoints) >= 1
        assert res.backend_status == "Unknown backend/API framework"
        assert any(ep.path == "/api/custom/resource" for ep in res.backend_endpoints)


# ──────────────────────────────────────────────────────────────────────────────
# 11. Section 18: Sixteen Project Archetypes Test Suite
# ──────────────────────────────────────────────────────────────────────────────

class TestSixteenArchetypes:
    """
    Directly tests all 16 specific project archetypes required by Section 18:
    1. React + FastAPI
    2. React + Flask
    3. React + Django
    4. React + Express
    5. React + NestJS
    6. Vue + FastAPI
    7. Angular + Spring Boot
    8. Next.js full-stack
    9. Laravel + React
    10. Django REST + React
    11. GraphQL frontend + GraphQL backend
    12. WebSocket frontend + backend
    13. Backend-only project
    14. Frontend-only project
    15. Monorepo
    16. Repository with intentionally broken API connections
    """

    def test_arch_1_react_fastapi(self, tmp_path):
        fe = tmp_path / "src"
        fe.mkdir()
        (fe / "Users.tsx").write_text("fetch('/api/v1/users');\n")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "router.py").write_text("""
from fastapi import APIRouter
router = APIRouter(prefix="/api/v1")
@router.get("/users")
def get_users():
    return []
""")
        (be / "requirements.txt").write_text("fastapi\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1
        assert any(c.status == "MATCHED" for c in res.api_connections)

    def test_arch_2_react_flask(self, tmp_path):
        fe = tmp_path / "src"
        fe.mkdir()
        (fe / "App.jsx").write_text("axios.get('/api/items');\n")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0", "axios": "^1.0.0"}}')

        be = tmp_path / "app"
        be.mkdir()
        (be / "views.py").write_text("""
from flask import Blueprint
bp = Blueprint('items', __name__, url_prefix='/api')
@bp.route('/items', methods=['GET'])
def list_items():
    return []
""")
        (be / "requirements.txt").write_text("flask\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_3_react_django(self, tmp_path):
        fe = tmp_path / "frontend"
        fe.mkdir()
        (fe / "List.tsx").write_text("fetch('/api/articles');\n")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "urls.py").write_text("path('api/articles', views.article_list)\n")
        (be / "manage.py").write_text("# django\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_4_react_express(self, tmp_path):
        fe = tmp_path / "client"
        fe.mkdir()
        (fe / "Orders.js").write_text("axios.post('/api/orders', { total: 100 });\n")
        (fe / "package.json").write_text('{"dependencies": {"react": "^18.0.0", "axios": "^1.0.0"}}')

        be = tmp_path / "server"
        be.mkdir()
        (be / "routes.js").write_text("""
const express = require('express');
const router = express.Router();
router.post('/api/orders', (req, res) => {
    const { total } = req.body;
    res.json({ id: 1, total });
});
""")
        (be / "package.json").write_text('{"dependencies": {"express": "^4.18.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_5_react_nestjs(self, tmp_path):
        fe = tmp_path / "src"
        fe.mkdir()
        (fe / "Cats.tsx").write_text("fetch('/api/cats');\n")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

        be = tmp_path / "server"
        be.mkdir()
        (be / "cats.controller.ts").write_text("""
import { Controller, Get } from '@nestjs/common';
@Controller('api/cats')
export class CatsController {
    @Get()
    findAll() { return []; }
}
""")
        (be / "package.json").write_text('{"dependencies": {"@nestjs/core": "^9.0.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_6_vue_fastapi(self, tmp_path):
        fe = tmp_path / "frontend"
        fe.mkdir()
        (fe / "Profile.vue").write_text("<template><div>{{ user }}</div></template>\n<script>\nfetch('/api/profile');\n</script>")
        (fe / "package.json").write_text('{"dependencies": {"vue": "^3.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "main.py").write_text("""
from fastapi import FastAPI
app = FastAPI()
@app.get('/api/profile')
def profile(): return {'name': 'Alice'}
""")
        (be / "requirements.txt").write_text("fastapi\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_7_angular_spring_boot(self, tmp_path):
        fe = tmp_path / "angular-client"
        fe.mkdir()
        (fe / "customer.service.ts").write_text("this.http.get('/api/v1/customers');\n")
        (fe / "package.json").write_text('{"dependencies": {"@angular/core": "^15.0.0"}}')

        be = tmp_path / "spring-server"
        be.mkdir()
        (be / "CustomerController.java").write_text("""
package com.example.demo;
@RestController
@RequestMapping("/api/v1")
public class CustomerController {
    @GetMapping("/customers")
    public List<Customer> getAll() { return List.of(); }
}
""")
        (be / "pom.xml").write_text("<project><dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency></dependencies></project>")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_8_nextjs_fullstack(self, tmp_path):
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "page.tsx").write_text("fetch('/api/notifications');\n")

        api_dir = app_dir / "api" / "notifications"
        api_dir.mkdir(parents=True)
        (api_dir / "route.ts").write_text("""
export async function GET(request: Request) {
    return Response.json({ unread: 5 });
}
""")
        (tmp_path / "package.json").write_text('{"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_9_laravel_react(self, tmp_path):
        fe = tmp_path / "resources" / "js"
        fe.mkdir(parents=True)
        (fe / "App.jsx").write_text("axios.get('/api/products');\n")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

        routes_dir = tmp_path / "routes"
        routes_dir.mkdir()
        (routes_dir / "api.php").write_text("Route::get('/api/products', [ProductController::class, 'index']);\n")
        (tmp_path / "composer.json").write_text('{"require": {"laravel/framework": "^10.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1

    def test_arch_10_django_rest_react(self, tmp_path):
        fe = tmp_path / "frontend"
        fe.mkdir()
        (fe / "App.tsx").write_text("fetch('/api/books');\n")
        (fe / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "urls.py").write_text("router.register(r'api/books', BookViewSet)\n")
        (be / "requirements.txt").write_text("djangorestframework\ndjango\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) >= 1
        assert res.summary["matched_apis"] == 1

    def test_arch_11_graphql_frontend_backend(self, tmp_path):
        fe = tmp_path / "frontend"
        fe.mkdir()
        (fe / "queries.ts").write_text("""
import { request } from 'graphql-request';
const query = `query GetUsers { users { id name } }`;
request('/graphql', query);
""")
        (fe / "package.json").write_text('{"dependencies": {"graphql-request": "^6.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "server.ts").write_text("""
const server = new ApolloServer({ typeDefs, resolvers });
server.applyMiddleware({ app, path: '/graphql' });
""")
        (be / "package.json").write_text('{"dependencies": {"apollo-server": "^3.0.0", "graphql": "^16.0.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1
        assert any(c.protocol == "graphql" for c in res.api_connections)

    def test_arch_12_websocket_frontend_backend(self, tmp_path):
        fe = tmp_path / "src"
        fe.mkdir()
        (fe / "Chat.tsx").write_text("""
const socket = new WebSocket('ws://localhost:8000/ws/chat');
""")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "main.py").write_text("""
from fastapi import FastAPI, WebSocket
app = FastAPI()
@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
""")
        (be / "requirements.txt").write_text("fastapi\nwebsockets\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert any(c.protocol == "websocket" for c in res.api_connections)

    def test_arch_13_backend_only(self, tmp_path):
        be = tmp_path / "api"
        be.mkdir()
        (be / "app.py").write_text("""
from fastapi import FastAPI
app = FastAPI()
@app.get("/health")
def health(): return {"status": "ok"}
""")
        (be / "requirements.txt").write_text("fastapi\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 0
        assert len(res.backend_endpoints) == 1
        assert res.project_type == "backend_only"
        assert any(c.status == "UNUSED_BACKEND_ENDPOINT" for c in res.api_connections)

    def test_arch_14_frontend_only(self, tmp_path):
        fe = tmp_path / "src"
        fe.mkdir()
        (fe / "App.jsx").write_text("fetch('/api/data');\n")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 0
        assert res.project_type == "frontend_only"
        assert any(c.status in ("UNKNOWN_BACKEND", "MISSING_BACKEND_ENDPOINT") for c in res.api_connections)

    def test_arch_15_monorepo(self, tmp_path):
        (tmp_path / "apps" / "client" / "src").mkdir(parents=True)
        (tmp_path / "apps" / "client" / "src" / "App.tsx").write_text("fetch('/api/ping');\n")
        (tmp_path / "apps" / "client" / "package.json").write_text('{"name": "client"}')

        (tmp_path / "services" / "server").mkdir(parents=True)
        (tmp_path / "services" / "server" / "main.py").write_text("""
from fastapi import FastAPI
app = FastAPI()
@app.get("/api/ping")
def ping(): return "pong"
""")
        (tmp_path / "services" / "server" / "requirements.txt").write_text("fastapi\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["matched_apis"] == 1
        assert len(res.summary["monorepo_packages"]) >= 2

    def test_arch_16_intentionally_broken_api_connections(self, tmp_path):
        fe = tmp_path / "src"
        fe.mkdir()
        (fe / "Auth.tsx").write_text("axios.post('/api/login', { username: 'test' });\n")
        (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0", "axios": "^1.0.0"}}')

        be = tmp_path / "backend"
        be.mkdir()
        (be / "app.py").write_text("""
from fastapi import FastAPI
app = FastAPI()
# Backend only accepts GET for /api/login, causing METHOD_MISMATCH
@app.get("/api/login")
def login(): return {}
""")
        (be / "requirements.txt").write_text("fastapi\n")

        res = run_analysis(AnalysisRequest(source_type="local", source=str(tmp_path)))
        assert len(res.frontend_calls) == 1
        assert len(res.backend_endpoints) == 1
        assert res.summary["mismatched_apis"] == 1
        assert any(i.issue_type == "METHOD_MISMATCH" for i in res.issues)
        assert any(c.status == "METHOD_MISMATCH" for c in res.api_connections)


class TestFolderUpload:
    """Tests for browser folder-selection upload workflow."""

    def test_upload_fullstack_project(self):
        client = TestClient(app)
        files = [
            ("files", ("App.tsx", b"fetch('/api/todos');\n", "text/plain")),
            ("files", ("package.json", b'{"dependencies": {"react": "^18.0.0"}}\n', "application/json")),
            ("files", ("main.py", b"from fastapi import FastAPI\napp = FastAPI()\n@app.get('/api/todos')\ndef todos(): return []\n", "text/plain")),
            ("files", ("requirements.txt", b"fastapi\n", "text/plain")),
        ]
        paths = ["src/App.tsx", "package.json", "backend/main.py", "backend/requirements.txt"]
        data = {
            "folder_name": "my-cool-app",
            "paths": json.dumps(paths),
        }
        response = client.post("/api/analyze/upload", data=data, files=files)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["source_type"] == "local"
        assert body["project_name"] == "my-cool-app"
        assert body["summary"]["frontend_files_scanned"] >= 1
        assert body["summary"]["backend_files_scanned"] >= 1
        assert len(body["frontend_calls"]) == 1
        assert len(body["backend_endpoints"]) == 1
        assert body["summary"]["matched_apis"] == 1

    def test_upload_empty_files_rejected(self):
        client = TestClient(app)
        response = client.post("/api/analyze/upload", data={"folder_name": "empty", "paths": "[]"}, files=[])
        assert response.status_code in (400, 422)



