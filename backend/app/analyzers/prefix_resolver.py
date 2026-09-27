"""
BARA Backend – Route Prefix Resolver.

Resolves hierarchical route prefixes across major backend frameworks:
- FastAPI: APIRouter(prefix="...") and app.include_router(..., prefix="...")
- Flask: Blueprint(..., url_prefix="...") and app.register_blueprint(..., url_prefix="...")
- Express: app.use('/prefix', router)
- NestJS: @Controller('prefix')
- Django: path('prefix/', include('app.urls'))
- Spring Boot: @RequestMapping("prefix") at class level
- Laravel: Route::prefix('prefix')->group(...)
"""
from __future__ import annotations
import os
import re
from typing import Dict, List, Optional, Tuple


class RoutePrefixResolver:
    """Detects and tracks router prefixes across backend files."""

    def __init__(self, project_path: str):
        self.project_path = project_path
        # Map: filename or router variable name -> route prefix string
        self.file_prefixes: Dict[str, str] = {}
        self.router_var_prefixes: Dict[str, str] = {}
        self.express_mounts: Dict[str, str] = {}  # router variable -> mount prefix

    def scan_all(self, backend_files: List[str]) -> None:
        """Scan all backend files to extract prefixes and mounts."""
        for rel_file in backend_files:
            abs_path = os.path.join(self.project_path, rel_file)
            if not os.path.exists(abs_path):
                continue
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self._scan_file_content(rel_file, content)
            except Exception:
                pass

    def _scan_file_content(self, rel_file: str, content: str) -> None:
        lower_file = rel_file.lower()

        # 1. FastAPI / Starlette
        # APIRouter(prefix="/api/v1")
        for m in re.finditer(r"""(\w+)\s*=\s*APIRouter\s*\([^)]*prefix\s*=\s*['"]([^'"]+)['"]""", content):
            var_name, prefix = m.group(1), m.group(2)
            self.router_var_prefixes[var_name] = prefix
            self.file_prefixes[rel_file] = prefix

        # app.include_router(router, prefix="/api/v1")
        for m in re.finditer(r"""\.include_router\s*\(\s*(\w+)[^)]*prefix\s*=\s*['"]([^'"]+)['"]""", content):
            router_var, prefix = m.group(1), m.group(2)
            self.router_var_prefixes[router_var] = prefix

        # 2. Flask Blueprint
        # Blueprint('users', __name__, url_prefix='/api/users')
        for m in re.finditer(r"""(\w+)\s*=\s*Blueprint\s*\([^)]*url_prefix\s*=\s*['"]([^'"]+)['"]""", content):
            var_name, prefix = m.group(1), m.group(2)
            self.router_var_prefixes[var_name] = prefix
            self.file_prefixes[rel_file] = prefix

        # app.register_blueprint(bp, url_prefix='/api/v1')
        for m in re.finditer(r"""\.register_blueprint\s*\(\s*(\w+)[^)]*url_prefix\s*=\s*['"]([^'"]+)['"]""", content):
            var_name, prefix = m.group(1), m.group(2)
            self.router_var_prefixes[var_name] = prefix

        # 3. Express
        # app.use('/api/v1', userRouter) or app.use('/api', router)
        for m in re.finditer(r"""(?:app|server)\.use\s*\(\s*['"]([^'"]+)['"]\s*,\s*(\w+)""", content):
            prefix, router_var = m.group(1), m.group(2)
            self.express_mounts[router_var] = prefix
            self.router_var_prefixes[router_var] = prefix

        # 4. NestJS
        # @Controller('api/users') or @Controller('/api/v1')
        nest_match = re.search(r"""@Controller\s*\(\s*['"]([^'"]*)['"]\s*\)""", content)
        if nest_match:
            ctrl_prefix = nest_match.group(1).strip()
            if ctrl_prefix:
                if not ctrl_prefix.startswith("/"):
                    ctrl_prefix = "/" + ctrl_prefix
                self.file_prefixes[rel_file] = ctrl_prefix

        # 5. Spring Boot
        # @RequestMapping("/api/v1") or @RestController @RequestMapping("/users")
        spring_match = re.search(r"""@RequestMapping\s*\(\s*(?:value\s*=\s*)?['"]([^'"]+)['"]""", content)
        if spring_match and ("@RestController" in content or "@Controller" in content):
            prefix = spring_match.group(1).strip()
            if not prefix.startswith("/"):
                prefix = "/" + prefix
            self.file_prefixes[rel_file] = prefix

        # 6. Django include
        # path('api/', include('users.urls'))
        for m in re.finditer(r"""path\s*\(\s*['"]([^'"]+)['"]\s*,\s*include\s*\(\s*['"]([^'"]+)['"]""", content):
            path_prefix, module_name = m.group(1), m.group(2)
            # map module_name to prefix
            self.router_var_prefixes[module_name] = "/" + path_prefix.strip("/")

        # 7. Laravel Route::prefix('api')->group(...)
        for m in re.finditer(r"""Route::prefix\s*\(\s*['"]([^'"]+)['"]\s*\)""", content):
            prefix = "/" + m.group(1).strip("/")
            self.file_prefixes[rel_file] = prefix

    def resolve_endpoint_path(
        self,
        raw_path: str,
        source_file: str,
        router_var: Optional[str] = None,
    ) -> str:
        """Combine prefix with endpoint path."""
        prefix = ""

        # Check router var first
        if router_var and router_var in self.router_var_prefixes:
            prefix = self.router_var_prefixes[router_var]
        # Then check file prefix
        elif source_file in self.file_prefixes:
            prefix = self.file_prefixes[source_file]

        clean_path = raw_path.strip()
        if not clean_path.startswith("/") and not clean_path.startswith("^"):
            clean_path = "/" + clean_path

        if prefix:
            prefix = "/" + prefix.strip("/")
            if not clean_path.startswith(prefix):
                return f"{prefix}{clean_path}".rstrip("/") if f"{prefix}{clean_path}" != "/" else "/"

        return clean_path if clean_path else "/"
