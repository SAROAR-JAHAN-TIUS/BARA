"""
BARA Backend – Source Manager.

Converts a (source_type, source) pair into a resolved filesystem path.
The analysis engine only receives a real directory path.

    LOCAL  → validate path exists → return it (temporary=False)
    GITHUB → validate URL → shallow clone → return clone path (temporary=True)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


@dataclass
class ResolvedSource:
    """Result of resolving a source."""
    project_path: str       # absolute filesystem path for the analyzer
    source_type: str         # 'local' | 'github'
    source: str              # original user input
    project_name: str        # display name
    github_url: Optional[str] = None
    temporary: bool = False  # True if project_path should be cleaned up
    _temp_dir: Optional[Path] = None  # parent temp dir to delete


_lock = threading.Lock()
_active_temp_dir: Optional[Path] = None


def normalize_github_url(source: str) -> Optional[str]:
    """
    Extract a canonical https://github.com/<owner>/<repo> from arbitrary GitHub URL.
    Strips query parameters (?utm_source=...), fragments (#readme), .git suffix,
    and extra path segments like /tree/main or /blob/main/file.
    """
    url = source.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    if parsed.scheme.lower() != "https":
        return None

    if parsed.netloc.lower() not in ("github.com", "www.github.com"):
        return None

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) != 2:
        return None

    owner = parts[0]
    repo = parts[1].removesuffix(".git")

    if not re.match(r"^[A-Za-z0-9_.\-]+$", owner) or not re.match(r"^[A-Za-z0-9_.\-]+$", repo):
        return None

    return f"https://github.com/{owner}/{repo}"


def is_github_url(value: str) -> bool:
    """Return True if *value* looks like a public GitHub repository URL."""
    return normalize_github_url(value) is not None


def resolve_source(source_type: str, source: str) -> ResolvedSource:
    """Resolve a (source_type, source) pair into a ResolvedSource."""
    source = source.strip()
    if not source:
        raise ValueError("No source provided. Enter a local path or GitHub URL.")

    if source_type == "local":
        return _resolve_local(source)
    elif source_type == "github":
        return _resolve_github(source)
    else:
        raise ValueError(
            f"Invalid source_type: {source_type!r}. Must be 'local' or 'github'."
        )


def cleanup(resolved: ResolvedSource) -> None:
    """Delete the temporary workspace if this was a GitHub clone or folder upload. Never touches permanent local projects."""
    global _active_temp_dir
    if resolved.temporary and resolved._temp_dir is not None:
        temp_str = str(resolved._temp_dir)
        # Extra safety check: never delete anything that isn't a temporary directory
        if "bara_" in temp_str or temp_str.startswith(tempfile.gettempdir()):
            shutil.rmtree(resolved._temp_dir, ignore_errors=True)
            with _lock:
                if _active_temp_dir == resolved._temp_dir:
                    _active_temp_dir = None


async def resolve_uploaded_folder(
    folder_name: str,
    path_list: list[str],
    files: list[Any],
) -> ResolvedSource:
    """
    Write browser-uploaded folder files to a temporary workspace preserving structure.
    Returns a ResolvedSource ready for the unified analysis pipeline.
    """
    folder_name = folder_name.strip() or "uploaded_project"
    sanitized_name = re.sub(r"[^\w\-. ]", "_", folder_name)

    temp_dir = Path(tempfile.mkdtemp(prefix="bara_upload_"))
    project_dir = temp_dir / sanitized_name
    project_dir.mkdir(parents=True, exist_ok=True)

    for upload_file, rel_path in zip(files, path_list):
        # Normalize relative path and strip folder prefix if present
        clean_rel = rel_path.replace("\\", "/").strip("/")
        if clean_rel.startswith(f"{sanitized_name}/"):
            clean_rel = clean_rel[len(sanitized_name) + 1:]
        elif clean_rel.startswith(f"{folder_name}/"):
            clean_rel = clean_rel[len(folder_name) + 1:]
        elif "/" in clean_rel:
            first_seg = clean_rel.split("/")[0]
            if first_seg in (sanitized_name, folder_name):
                clean_rel = clean_rel[len(first_seg) + 1:]

        # Prevent directory traversal
        norm_path = os.path.normpath(clean_rel)
        if norm_path.startswith("..") or ".." in norm_path.split(os.sep):
            continue

        target_file = (project_dir / norm_path).resolve()
        # Verify file stays strictly inside project_dir
        if not str(target_file).startswith(str(project_dir.resolve())):
            continue

        target_file.parent.mkdir(parents=True, exist_ok=True)
        content = await upload_file.read()
        target_file.write_bytes(content)

    return ResolvedSource(
        project_path=str(project_dir),
        source_type="local",
        source=folder_name,
        project_name=folder_name,
        temporary=True,
        _temp_dir=temp_dir,
    )


def get_active_temp_dir() -> Optional[Path]:
    """Return the current active clone temp directory (for tests / introspection)."""
    return _active_temp_dir


def drop_active_clone() -> None:
    """Delete the active clone directory if one exists."""
    global _active_temp_dir
    with _lock:
        if _active_temp_dir is not None and _active_temp_dir.exists():
            shutil.rmtree(_active_temp_dir, ignore_errors=True)
        _active_temp_dir = None


# ── Local ──────────────────────────────────────────────────────────────────────

def _resolve_local(source: str) -> ResolvedSource:
    """Validate and resolve a local filesystem path."""
    # Reject URLs accidentally sent as local
    if source.startswith("http://") or source.startswith("https://"):
        raise ValueError(
            f"'{source}' looks like a URL, not a local path. "
            "Select 'GitHub Repository' as the source type."
        )

    abspath = os.path.abspath(os.path.expanduser(source))

    if not os.path.exists(abspath):
        raise ValueError(f"Path does not exist: {abspath}")
    if not os.path.isdir(abspath):
        raise ValueError(f"Path is not a directory: {abspath}")
    if not os.access(abspath, os.R_OK):
        raise ValueError(f"Permission denied: cannot read {abspath}")

    return ResolvedSource(
        project_path=abspath,
        source_type="local",
        source=source,
        project_name=os.path.basename(abspath.rstrip(os.sep)) or abspath,
        temporary=False,
    )


# ── GitHub ─────────────────────────────────────────────────────────────────────

def _resolve_github(source: str) -> ResolvedSource:
    """Validate URL, clone repo, return resolved source."""
    canonical_url = normalize_github_url(source)

    if not canonical_url:
        raise ValueError(
            f"Invalid GitHub URL: {source!r}\n"
            "Expected format: https://github.com/<owner>/<repo>"
        )

    # Extract owner/repo for display
    parsed = urlparse(canonical_url)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    owner = path_parts[0]
    repo = path_parts[1]
    project_name = f"{owner}/{repo}"

    # Clone into temp directory using canonical URL
    clone_path, temp_dir = _clone_repo(canonical_url)

    return ResolvedSource(
        project_path=str(clone_path),
        source_type="github",
        source=source,
        project_name=project_name,
        github_url=canonical_url,
        temporary=True,
        _temp_dir=temp_dir,
    )


def _clone_repo(url: str) -> tuple[Path, Path]:
    """Shallow-clone a GitHub repo. Returns (clone_path, temp_parent_dir)."""
    global _active_temp_dir

    with _lock:
        # Clean up previous active clone
        if _active_temp_dir is not None and _active_temp_dir.exists():
            shutil.rmtree(_active_temp_dir, ignore_errors=True)
        _active_temp_dir = None

        tmp = Path(tempfile.mkdtemp(prefix="bara_github_"))
        clone_target = tmp / "repo"

        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            result = subprocess.run(
                [
                    "git", "clone",
                    "--depth", "1",
                    "--single-branch",
                    url,
                    str(clone_target),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
        except subprocess.TimeoutExpired:
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError(
                f"git clone timed out after 120s for {url!r}"
            )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            shutil.rmtree(tmp, ignore_errors=True)
            # Provide user-friendly messages
            if "not found" in stderr.lower() or "404" in stderr:
                raise RuntimeError(
                    f"Repository not found: {url}\n"
                    "Check that the repository exists and is public."
                )
            if "authentication" in stderr.lower() or "403" in stderr:
                raise RuntimeError(
                    f"Cannot access repository: {url}\n"
                    "This may be a private repository. BARA only supports public repositories."
                )
            raise RuntimeError(
                f"Failed to clone {url}:\n{stderr}"
            )

        if not clone_target.is_dir():
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError(
                f"Clone completed but directory not found: {clone_target}"
            )

        _active_temp_dir = tmp
        return clone_target, tmp
