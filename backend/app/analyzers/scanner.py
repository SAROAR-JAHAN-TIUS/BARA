"""
BARA Backend – Project Scanner.

Walks a project directory and classifies source files as frontend or backend.
"""
from __future__ import annotations
import os
from typing import List

from app.models.analysis import ScannedFile, ScanResult

# Directories to skip during scanning
SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "ENV",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    "htmlcov",
    ".pytest_cache",
}

FRONTEND_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
BACKEND_EXTENSIONS = {".py"}

# Strong indicators of frontend/backend context
FRONTEND_MARKERS = {
    "package.json",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "next.config.ts",
    "react-scripts",
}

BACKEND_MARKERS = {
    "requirements.txt",
    "setup.py",
    "pyproject.toml",
    "Pipfile",
    "manage.py",  # Django
    "app.py",
    "main.py",
}


def _classify_file(filepath: str, root_type_map: dict) -> str:
    """Return 'frontend', 'backend', or 'unknown' for a file."""
    ext = os.path.splitext(filepath)[1].lower()
    # Walk up the directory tree to find the closest root hint
    parts = filepath.replace("\\", "/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        candidate_root = "/".join(parts[:i])
        if candidate_root in root_type_map:
            return root_type_map[candidate_root]

    # Fallback: classify by extension
    if ext in FRONTEND_EXTENSIONS:
        return "frontend"
    if ext in BACKEND_EXTENSIONS:
        return "backend"
    return "unknown"


def scan_project(project_path: str) -> ScanResult:
    """
    Recursively scan *project_path* and return a ScanResult.
    """
    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        raise ValueError(f"Project path is not a directory: {project_path}")

    # First pass: detect marker files to build a root-type map
    root_type_map: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(project_path):
        # Prune skipped dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in filenames:
            if fname in FRONTEND_MARKERS:
                root_type_map[dirpath] = "frontend"
                break
            if fname in BACKEND_MARKERS:
                root_type_map[dirpath] = "backend"
                break

    # Second pass: collect source files
    scanned: List[ScannedFile] = []
    frontend_files: List[str] = []
    backend_files: List[str] = []

    for dirpath, dirnames, filenames in os.walk(project_path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in FRONTEND_EXTENSIONS and ext not in BACKEND_EXTENSIONS:
                continue

            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, project_path)

            # Language
            if ext == ".py":
                lang = "py"
            elif ext in {".ts", ".tsx"}:
                lang = "ts"
            else:
                lang = "js"

            # File type: use marker-based classification first
            file_type = _classify_file(dirpath, root_type_map)
            # If still unknown, guess from the extension
            if file_type == "unknown":
                file_type = "frontend" if ext in FRONTEND_EXTENSIONS else "backend"

            sf = ScannedFile(path=rel_path, language=lang, file_type=file_type)
            scanned.append(sf)
            if file_type == "frontend":
                frontend_files.append(rel_path)
            elif file_type == "backend":
                backend_files.append(rel_path)

    return ScanResult(
        root=project_path,
        files=scanned,
        frontend_files=frontend_files,
        backend_files=backend_files,
    )
