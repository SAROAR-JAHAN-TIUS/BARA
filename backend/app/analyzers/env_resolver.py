"""
BARA Backend – Environment & Base URL Resolver.

Inspects environment files (.env, .env.local, .env.development, etc.),
config files (vite.config, next.config), and client setups (axios.create, ky.create)
to extract base URLs and API prefixes.
"""
from __future__ import annotations
import os
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

ENV_FILE_PATTERNS = [
    ".env",
    ".env.local",
    ".env.development",
    ".env.dev",
    ".env.production",
    ".env.staging",
    ".env.example",
]

API_URL_KEYS = [
    "VITE_API_URL",
    "NEXT_PUBLIC_API_URL",
    "REACT_APP_API_URL",
    "API_URL",
    "BACKEND_URL",
    "BASE_URL",
    "SERVER_URL",
    "API_BASE_URL",
    "PUBLIC_API_URL",
]


class EnvResolver:
    """Extracts base URLs and environment configurations for frontend-backend connection."""

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.env_vars: Dict[str, str] = {}
        self.client_base_urls: Dict[str, str] = {}  # file_path or client_name -> base_url
        self.discovered_base_urls: List[str] = []

    def resolve_all(self, frontend_files: Optional[List[str]] = None) -> Dict[str, str]:
        """Scan project for environment variables and client base URLs."""
        self._scan_env_files()
        if frontend_files:
            self._scan_client_files(frontend_files)
        return self.env_vars

    def _scan_env_files(self) -> None:
        """Find and parse all .env* files in project."""
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "dist", "build", ".venv"}]
            for fname in files:
                if fname in ENV_FILE_PATTERNS or fname.startswith(".env."):
                    fpath = os.path.join(root, fname)
                    self._parse_env_file(fpath)

    def _parse_env_file(self, file_path: str) -> None:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        key = k.strip()
                        val = v.strip().strip("'\"")
                        if key:
                            self.env_vars[key] = val
                            if any(target in key.upper() for target in ["API", "BACKEND", "BASE_URL", "SERVER"]):
                                norm_val = self._extract_path_or_url(val)
                                if norm_val and norm_val not in self.discovered_base_urls:
                                    self.discovered_base_urls.append(norm_val)
        except Exception:
            pass

    def _scan_client_files(self, frontend_files: List[str]) -> None:
        """Inspect frontend files for axios.create / ky.create / BASE_URL declarations."""
        axios_re = re.compile(
            r"""axios\.create\s*\(\s*\{[^}]*baseURL\s*:\s*['"`]([^'"`]+)['"`]""",
            re.MULTILINE | re.DOTALL,
        )
        axios_env_re = re.compile(
            r"""axios\.create\s*\(\s*\{[^}]*baseURL\s*:\s*(?:process\.env\.|import\.meta\.env\.)([A-Za-z0-9_]+)""",
            re.MULTILINE | re.DOTALL,
        )
        base_const_re = re.compile(
            r"""(?:const|let|var)\s+(?:API_BASE_URL|BASE_URL|API_URL)\s*=\s*['"`]([^'"`]+)['"`]""",
            re.IGNORECASE,
        )

        for rel_file in frontend_files:
            abs_path = os.path.join(self.project_path, rel_file)
            if not os.path.exists(abs_path):
                continue
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Literal baseURL in axios.create
                for m in axios_re.finditer(content):
                    b_url = self._extract_path_or_url(m.group(1))
                    if b_url:
                        self.client_base_urls[rel_file] = b_url
                        if b_url not in self.discovered_base_urls:
                            self.discovered_base_urls.append(b_url)

                # Env variable baseURL in axios.create
                for m in axios_env_re.finditer(content):
                    env_name = m.group(1)
                    if env_name in self.env_vars:
                        b_url = self._extract_path_or_url(self.env_vars[env_name])
                        if b_url:
                            self.client_base_urls[rel_file] = b_url
                            if b_url not in self.discovered_base_urls:
                                self.discovered_base_urls.append(b_url)

                # Constant definitions
                for m in base_const_re.finditer(content):
                    b_url = self._extract_path_or_url(m.group(1))
                    if b_url:
                        self.client_base_urls[rel_file] = b_url
                        if b_url not in self.discovered_base_urls:
                            self.discovered_base_urls.append(b_url)

            except Exception:
                pass

    def _extract_path_or_url(self, val: str) -> str:
        """Extracts pathname or clean relative prefix from a URL string."""
        val = val.strip()
        if not val:
            return ""
        if val.startswith("http://") or val.startswith("https://"):
            parsed = urlparse(val)
            path = parsed.path.rstrip("/")
            return path if path else "/"
        # Already a relative path like /api or /api/v1
        if val.startswith("/"):
            return val.rstrip("/")
        return "/" + val.rstrip("/")

    def resolve_call_path(self, raw_path: str, source_file: Optional[str] = None) -> str:
        """Applies base URL prefix to a relative call path if needed."""
        raw = raw_path.strip()
        if not raw:
            return "/"

        # If it's an absolute URL
        if raw.startswith("http://") or raw.startswith("https://"):
            parsed = urlparse(raw)
            return parsed.path if parsed.path else "/"

        # Check if caller file has a specific baseURL
        base = None
        if source_file and source_file in self.client_base_urls:
            base = self.client_base_urls[source_file]
        elif self.discovered_base_urls:
            # Use most common base url if available
            base = self.discovered_base_urls[0]

        if base and base != "/" and not raw.startswith(base):
            joined = f"{base.rstrip('/')}/{raw.lstrip('/')}"
            return joined

        return raw
