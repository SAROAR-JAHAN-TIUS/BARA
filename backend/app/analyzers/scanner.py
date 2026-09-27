"""
BARA Backend – Project Scanner.

Walks a project directory and classifies source files as frontend or backend.
Detects tech stack (React, Vue, Vite, Express, FastAPI, Flask, Django, etc.).
"""
from __future__ import annotations
import os
import json
import re
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
    "target",  # Java maven/gradle/cargo build target
    "bin",
    "obj",  # C# / .NET build
    ".next",
    ".nuxt",
    ".svelte-kit",
    "coverage",
    "htmlcov",
    ".pytest_cache",
    ".idea",
    ".vscode",
}

FRONTEND_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html"}
BACKEND_EXTENSIONS = {
    ".py",
    ".java",
    ".go",
    ".cs",
    ".rb",
    ".php",
    ".rs",
    ".js",
    ".ts",
    ".mjs",
    ".cjs",
}

# Strong indicators of frontend/backend context
FRONTEND_MARKERS = {
    "package.json",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "next.config.ts",
    "next.config.mjs",
    "nuxt.config.ts",
    "nuxt.config.js",
    "svelte.config.js",
    "react-scripts",
    "angular.json",
}

BACKEND_MARKERS = {
    "requirements.txt",
    "setup.py",
    "pyproject.toml",
    "Pipfile",
    "manage.py",  # Django
    "app.py",
    "main.py",
    "pom.xml",  # Java Maven
    "build.gradle",  # Java Gradle
    "build.gradle.kts",
    "go.mod",  # Go
    "Cargo.toml",  # Rust
    "composer.json",  # PHP
    "Gemfile",  # Ruby
    "routes.rb",
}

RECOGNIZED_BACKEND_FRAMEWORKS = {
    "FastAPI",
    "Flask",
    "Django",
    "Django REST Framework",
    "Express",
    "Fastify",
    "NestJS",
    "Koa",
    "Hono",
    "Hapi",
    "Spring Boot",
    "Spring MVC",
    "Gin",
    "Echo",
    "Fiber",
    "Rails",
    "Laravel",
    "Symfony",
    "ASP.NET Core",
    "Next.js API",
    "Nuxt Server",
}


def _detect_language(ext: str) -> str:
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".rs": "rust",
        ".vue": "vue",
        ".svelte": "svelte",
        ".html": "html",
    }
    return ext_map.get(ext, "unknown")


def _categorize_file(rel_path: str) -> Optional[str]:
    norm = rel_path.replace("\\", "/").lower()
    if any(p in norm for p in ["/pages/", "/app/", "/views/"]):
        return "page"
    if any(c in norm for c in ["/components/", "/widgets/", "/ui/"]):
        return "component"
    if any(s in norm for s in ["/services/", "/client/", "/clients/"]):
        return "service"
    if any(ctl in norm for ctl in ["/controllers/", "/handlers/"]):
        return "controller"
    if any(r in norm for r in ["/routes/", "/endpoints/", "/api/"]):
        return "route"
    if any(m in norm for m in ["/models/", "/schemas/", "/entities/"]):
        return "model"
    if any(d in norm for d in ["/db/", "/database/", "/migrations/", "/repositories/", "/dao/"]):
        return "db"
    if any(cfg in norm for cfg in ["config", "settings"]):
        return "config"
    return None


def detect_technologies(
    project_path: str,
    frontend_files: Optional[List[str]] = None,
    backend_files: Optional[List[str]] = None,
) -> List[str]:
    """Inspect configuration files and code to detect libraries and frameworks."""
    techs: List[str] = []

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        # 1. Inspect package.json (Node.js / JS / TS)
        if "package.json" in files:
            pkg_path = os.path.join(root, "package.json")
            try:
                with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }
                if "react" in deps or "react-dom" in deps:
                    techs.append("React")
                if "vue" in deps:
                    techs.append("Vue")
                if "solid-js" in deps:
                    techs.append("Solid")
                if "astro" in deps:
                    techs.append("Astro")
                if "express" in deps:
                    techs.append("Express")
                if "fastify" in deps:
                    techs.append("Fastify")
                if "nestjs" in deps or "@nestjs/core" in deps:
                    techs.append("NestJS")
                if "koa" in deps:
                    techs.append("Koa")
                if "hono" in deps:
                    techs.append("Hono")
                if "@hapi/hapi" in deps or "hapi" in deps:
                    techs.append("Hapi")
                if "next" in deps:
                    techs.append("Next.js")
                if "nuxt" in deps:
                    techs.append("Nuxt")
                if "vite" in deps:
                    techs.append("Vite")
                if "react-scripts" in deps:
                    techs.append("Create React App")
                if "axios" in deps:
                    techs.append("Axios")
                if "ky" in deps:
                    techs.append("Ky")
                if "got" in deps:
                    techs.append("Got")
                if "superagent" in deps:
                    techs.append("SuperAgent")
                if "@tanstack/react-query" in deps or "react-query" in deps:
                    techs.append("TanStack Query")
                if "swr" in deps:
                    techs.append("SWR")
                if "@apollo/client" in deps or "apollo-boost" in deps or "graphql" in deps or "graphql-request" in deps:
                    techs.append("GraphQL")
                if "relay-runtime" in deps or "react-relay" in deps:
                    techs.append("Relay")
                if "@trpc/client" in deps or "@trpc/server" in deps:
                    techs.append("tRPC")
                if "ws" in deps or "websocket" in deps:
                    techs.append("WebSocket")
                if "socket.io" in deps or "socket.io-client" in deps:
                    techs.append("Socket.IO")
                if "typescript" in deps:
                    techs.append("TypeScript")
                if "angular" in deps or "@angular/core" in deps:
                    techs.append("Angular")
                if "svelte" in deps:
                    techs.append("Svelte")
                if "prisma" in deps or "@prisma/client" in deps:
                    techs.append("Prisma")
                if "mongoose" in deps:
                    techs.append("Mongoose")
                if "typeorm" in deps:
                    techs.append("TypeORM")
                if "sequelize" in deps:
                    techs.append("Sequelize")
                if "pg" in deps or "postgres" in deps:
                    techs.append("PostgreSQL")
                if "mysql" in deps or "mysql2" in deps:
                    techs.append("MySQL")
                if "redis" in deps or "ioredis" in deps:
                    techs.append("Redis")
                if "sqlite3" in deps or "better-sqlite3" in deps:
                    techs.append("SQLite")
                if "stripe" in deps or "@stripe/stripe-js" in deps:
                    techs.append("Stripe")
                if "openai" in deps:
                    techs.append("OpenAI")
                if any("@aws-sdk" in d or "aws-sdk" in d for d in deps):
                    techs.append("AWS SDK")
                if "@octokit/rest" in deps or "@octokit/core" in deps:
                    techs.append("GitHub API")
                if "firebase" in deps or "firebase-admin" in deps:
                    techs.append("Firebase")
                if "@supabase/supabase-js" in deps:
                    techs.append("Supabase")
            except Exception:
                pass

        # 2. Inspect Python requirements / configs
        for fname in files:
            if (fname.startswith("requirements") and fname.endswith(".txt")) or fname in (
                "Pipfile",
                "pyproject.toml",
            ):
                req_path = os.path.join(root, fname)
                try:
                    with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                    if "fastapi" in content:
                        techs.append("FastAPI")
                    if "flask" in content:
                        techs.append("Flask")
                    if "djangorestframework" in content or "rest_framework" in content:
                        techs.append("Django REST Framework")
                    elif "django" in content:
                        techs.append("Django")
                    if "strawberry" in content or "graphene" in content or "ariadne" in content:
                        techs.append("GraphQL")
                    if "websockets" in content or "flask-sock" in content or "flask-socketio" in content:
                        techs.append("WebSocket")
                    if "sqlalchemy" in content:
                        techs.append("SQLAlchemy")
                    if "psycopg2" in content or "asyncpg" in content:
                        techs.append("PostgreSQL")
                    if "pymongo" in content or "motor" in content:
                        techs.append("MongoDB")
                    if "redis" in content:
                        techs.append("Redis")
                    if "sqlite3" in content or "aiosqlite" in content:
                        techs.append("SQLite")
                    if "pydantic" in content:
                        techs.append("Pydantic")
                    if "stripe" in content:
                        techs.append("Stripe")
                    if "openai" in content:
                        techs.append("OpenAI")
                    if "boto3" in content:
                        techs.append("AWS SDK")
                    if "github" in content or "pygithub" in content:
                        techs.append("GitHub API")
                except Exception:
                    pass

        if "manage.py" in files:
            if "Django" not in techs:
                techs.append("Django")

        # 3. Inspect Java configs (pom.xml, build.gradle)
        if "pom.xml" in files:
            pom_path = os.path.join(root, "pom.xml")
            try:
                with open(pom_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                if "spring-boot" in content or "org.springframework.boot" in content:
                    techs.append("Spring Boot")
                elif "spring-web" in content:
                    techs.append("Spring MVC")
                if "hibernate" in content:
                    techs.append("Hibernate")
            except Exception:
                pass

        if "build.gradle" in files or "build.gradle.kts" in files:
            for gname in ("build.gradle", "build.gradle.kts"):
                if gname in files:
                    g_path = os.path.join(root, gname)
                    try:
                        with open(g_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read().lower()
                        if "org.springframework.boot" in content or "spring-boot" in content:
                            techs.append("Spring Boot")
                        elif "spring" in content:
                            techs.append("Spring MVC")
                    except Exception:
                        pass

        # 4. Inspect Go configs (go.mod)
        if "go.mod" in files:
            mod_path = os.path.join(root, "go.mod")
            try:
                with open(mod_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                if "github.com/gin-gonic/gin" in content:
                    techs.append("Gin")
                elif "github.com/labstack/echo" in content:
                    techs.append("Echo")
                elif "github.com/gofiber/fiber" in content:
                    techs.append("Fiber")
                elif "net/http" in content:
                    techs.append("net/http")
                else:
                    techs.append("Go HTTP")
                if "gorm.io" in content:
                    techs.append("GORM")
            except Exception:
                pass

        # 5. Inspect Ruby configs (Gemfile)
        if "Gemfile" in files:
            gem_path = os.path.join(root, "Gemfile")
            try:
                with open(gem_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                if "'rails'" in content or '"rails"' in content:
                    techs.append("Rails")
                if "'sinatra'" in content or '"sinatra"' in content:
                    techs.append("Sinatra")
            except Exception:
                pass

        # 6. Inspect PHP configs (composer.json)
        if "composer.json" in files:
            comp_path = os.path.join(root, "composer.json")
            try:
                with open(comp_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()
                if "laravel/framework" in content:
                    techs.append("Laravel")
                if "symfony/" in content:
                    techs.append("Symfony")
            except Exception:
                pass

        # 7. Inspect C# configs (*.csproj)
        for fname in files:
            if fname.endswith(".csproj"):
                cs_path = os.path.join(root, fname)
                try:
                    with open(cs_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                    if "microsoft.aspnetcore" in content or "web" in content:
                        techs.append("ASP.NET Core")
                    if "entityframeworkcore" in content:
                        techs.append("Entity Framework")
                except Exception:
                    pass

    # Inspect file lists for TypeScript, Next.js, etc.
    if frontend_files:
        if any(f.endswith((".ts", ".tsx")) for f in frontend_files):
            techs.append("TypeScript")
        if any("pages/api/" in f or "app/api/" in f for f in frontend_files):
            techs.append("Next.js API")
    if backend_files:
        if any(f.endswith((".ts", ".tsx")) for f in backend_files):
            techs.append("TypeScript")

    return list(dict.fromkeys(techs))


def _classify_file(filepath: str, root_type_map: dict) -> str:
    """Return 'frontend', 'backend', or 'unknown' for a file."""
    ext = os.path.splitext(filepath)[1].lower()
    norm = filepath.replace("\\", "/").lower()

    # Clear non-JS/TS backend language extensions
    if ext in {".py", ".java", ".go", ".cs", ".rb", ".php", ".rs"}:
        return "backend"

    # Vue / Svelte / HTML are always frontend
    if ext in {".vue", ".svelte", ".html"}:
        return "frontend"

    # Clear directory keywords for monorepos and standard layouts
    backend_keywords = {
        "/backend/", "/server/", "/routes/", "/controllers/", "/handlers/",
        "/services/backend/", "/packages/server/", "/apps/backend/", "/apps/server/",
        "/apps/api/", "/services/api/",
    }
    frontend_keywords = {
        "/frontend/", "/client/", "/web/", "/ui/", "/pages/", "/components/",
        "/packages/client/", "/apps/frontend/", "/apps/client/", "/apps/web/",
    }

    for bk in backend_keywords:
        if bk in norm or norm.startswith(bk.lstrip("/")):
            return "backend"

    for fk in frontend_keywords:
        if fk in norm or norm.startswith(fk.lstrip("/")):
            return "frontend"

    # Next.js API routes or Nuxt server routes
    if "pages/api/" in norm or "app/api/" in norm or "server/api/" in norm:
        return "backend"

    # Walk up the directory tree to find the closest root hint
    parts = norm.split("/")
    for i in range(len(parts) - 1, 0, -1):
        candidate_root = "/".join(parts[:i])
        if candidate_root in root_type_map:
            return root_type_map[candidate_root]

    # For .js/.ts files, check content for backend router signatures
    return "unknown"


def scan_project(project_path: str) -> ScanResult:
    """
    Recursively scan *project_path* and return a ScanResult.
    """
    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        raise ValueError(f"Project path is not a directory: {project_path}")

    # First pass: detect marker files and monorepo packages
    root_type_map: dict[str, str] = {}
    monorepo_packages: List[str] = []

    for dirpath, dirnames, filenames in os.walk(project_path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        # Check monorepo packages (e.g. apps/*, packages/*, services/*)
        rel_dir = os.path.relpath(dirpath, project_path).replace("\\", "/")
        if rel_dir != "." and ("package.json" in filenames or "pom.xml" in filenames or "go.mod" in filenames or "Cargo.toml" in filenames or "pyproject.toml" in filenames or "requirements.txt" in filenames or "Pipfile" in filenames):
            monorepo_packages.append(rel_dir)

        for fname in filenames:
            if fname in FRONTEND_MARKERS:
                root_type_map[dirpath] = "frontend"
                break
            if fname in BACKEND_MARKERS or fname.endswith(".csproj"):
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

            lang = _detect_language(ext)
            file_type = _classify_file(rel_path, root_type_map)

            # Node.js backend check: if JS/TS file is unknown, inspect snippet
            if ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"} and file_type == "unknown":
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        snippet = f.read(2048)
                    backend_patterns = [
                        r"\b(?:express|Router\(\)|fastify|koa|hono|nest)\b",
                        r"\b(?:app|router|server)\.(?:get|post|put|delete|patch)\b",
                        r"\b(?:NextResponse|defineEventHandler)\b",
                        r"@(?:Get|Post|Put|Delete|Patch|Controller)\b",
                        r"export\s+async\s+function\s+(?:GET|POST|PUT|DELETE|PATCH)\b",
                    ]
                    if any(re.search(pat, snippet, re.IGNORECASE) for pat in backend_patterns):
                        file_type = "backend"
                    else:
                        file_type = "frontend"
                except Exception:
                    file_type = "frontend"

            if file_type == "unknown":
                file_type = "backend" if ext in {".py", ".java", ".go", ".cs", ".rb", ".php", ".rs"} else "frontend"

            category = _categorize_file(rel_path)
            sf = ScannedFile(path=rel_path, language=lang, file_type=file_type, category=category)
            scanned.append(sf)

            if file_type == "frontend":
                frontend_files.append(rel_path)
            elif file_type == "backend":
                backend_files.append(rel_path)

    # Detect technologies
    technologies = detect_technologies(project_path, frontend_files, backend_files)

    # Determine backend framework and backend status (Step 4 requirement)
    backend_framework = None
    for tech in technologies:
        if tech in RECOGNIZED_BACKEND_FRAMEWORKS:
            backend_framework = tech
            break

    if backend_framework:
        backend_status = "Framework detected"
    elif len(backend_files) > 0:
        backend_status = "Unknown backend/API framework"
    else:
        backend_status = "No backend/API code detected"

    # Determine project type
    if len(frontend_files) > 0 and len(backend_files) > 0:
        project_type = "fullstack"
    elif len(frontend_files) > 0:
        project_type = "frontend_only"
    elif len(backend_files) > 0:
        project_type = "backend_only"
    else:
        project_type = "documentation_only"

    return ScanResult(
        root=project_path,
        files=scanned,
        frontend_files=frontend_files,
        backend_files=backend_files,
        detected_technologies=technologies,
        project_type=project_type,
        backend_framework=backend_framework,
        backend_status=backend_status,
        monorepo_packages=monorepo_packages,
    )
