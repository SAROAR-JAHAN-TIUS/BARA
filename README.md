# BARA – Backend Architecture & API Analyzer

<div align="center">
  <h2>🔍 Find API integration bugs before they crash your app.</h2>
  <p>BARA scans your frontend and backend source code, compares API contracts, and explains every mismatch in plain language.</p>
</div>

---

## The Problem

Beginner developers often spend hours debugging integration failures:

- Frontend calls `/api/users`, backend provides `/api/user`
- Frontend sends `POST`, backend only accepts `GET`
- Frontend sends `username`, backend expects `name`
- Response field is `full_name`, but the frontend reads `name`

These mistakes are invisible until runtime — and the error messages are cryptic.

## The Solution

BARA **statically analyzes** your project directory, extracts every API call and route definition, then compares them automatically.

Every detected problem comes with:
- 📍 The exact source file and line number on both sides
- 📝 A plain-language explanation (suitable for beginners)
- 💡 A concrete suggested fix

---

## Target Users

- Beginner web developers learning frontend/backend integration
- Students in bootcamps or courses building full-stack projects
- Developers debugging mysterious 404 / 422 / 500 errors

---

## Features

| Feature | Status |
|---------|--------|
| Scan frontend JS/TS files | ✅ |
| Detect `fetch()` and `axios` calls | ✅ |
| Scan backend Python (FastAPI) routes | ✅ |
| Extract Pydantic request/response models | ✅ |
| Normalize API paths (`/api/users/` == `/api/users`) | ✅ |
| Detect missing backend endpoints | ✅ |
| Detect HTTP method mismatches | ✅ |
| Detect request field mismatches | ✅ |
| Detect response field mismatches | ✅ |
| Detect query parameter mismatches | ✅ |
| Architecture visualization | ✅ |
| Beginner-friendly explanations | ✅ |
| Suggested fixes | ✅ |
| Demo project with intentional bugs | ✅ |
| Automated test suite (47 tests) | ✅ |
| Optional AI explanation layer | 🔮 (future) |

---

## Architecture

```
User
 │
 ▼
BARA Frontend (React + Vite + TypeScript)
 │ HTTP POST /api/analyze
 ▼
BARA Backend (FastAPI / Python)
 ├── Project Scanner       (walks directory, classifies files)
 ├── Frontend Analyzer     (extracts fetch/axios calls)
 ├── Backend Analyzer      (extracts FastAPI route decorators)
 ├── API Normalizer        (canonicalizes paths for comparison)
 ├── Mismatch Detector     (compares contracts, generates Issues)
 └── Architecture Builder  (builds node/edge graph for visualization)
 │
 ▼
Structured JSON Analysis
 │
 ▼
Frontend Visualization (issues list, architecture diagram, detail panel)
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Analysis | Pure deterministic static analysis (regex + AST) |
| Tests | pytest |
| No AI required | ✅ Works fully offline |

---

## How BARA Works

### Main data flow

```
Project directory
  → Scan files (classify frontend vs backend)
  → Extract frontend API calls (fetch, axios)
  → Extract backend routes (@app.get, @app.post, …)
  → Normalize all paths
  → Compare contracts (path + method + fields + params)
  → Generate issues with explanations
  → Build architecture graph
  → Display in UI
```

### Example mismatch

**Frontend code** (`src/api.js`):
```js
// Calls /api/users (plural)
const response = await fetch("/api/users");
```

**Backend code** (`main.py`):
```python
# Only provides /api/user (singular)
@app.get("/api/user")
def get_users():
    return []
```

**BARA detects:**
```json
{
  "issue_type": "MISSING_BACKEND_ENDPOINT",
  "severity": "high",
  "frontend_location": { "file": "src/api.js", "line": 2 },
  "expected": "GET /api/users",
  "actual": "(not found)",
  "explanation": "The frontend is trying to call GET /api/users, but no matching endpoint exists in the backend…",
  "suggested_fix": "Add a GET endpoint at /api/users to the backend, or update the frontend to call an existing endpoint."
}
```

---

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

---

## Running Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

---

## Running Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Running the Demo

The demo project contains **5 intentional bugs**:

| Bug | Type | Frontend | Backend |
|-----|------|----------|---------|
| 1 | PATH_MISMATCH | `fetch("/api/users")` | `@app.get("/api/user")` |
| 2 | METHOD_MISMATCH | `fetch("/api/login", {method:"POST"})` | `@app.get("/api/login")` |
| 3 | REQUEST_FIELD_MISMATCH | `body: {username}` | `class Model: name: str` |
| 4 | RESPONSE_FIELD_MISMATCH | `data.name` | returns `full_name` |
| 5 | QUERY_PARAM_MISMATCH | `?limit=10` | `def fn(page_size: int)` |

**Via UI:** Click **"Run Demo Project Analysis"** on the home screen.

**Via API:**
```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/absolute/path/to/BARA/examples/demo-project"}'
```

---

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

Expected: **47 tests pass**.

Test coverage includes:
- Path normalization (9 tests)
- Frontend API extraction (8 tests)
- Backend route extraction (7 tests)
- Mismatch detection (9 tests)
- Demo project end-to-end (6 tests)
- Project scanner (3 tests)
- HTTP API (5 tests)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/analyze` | Analyze a project |
| `GET` | `/api/analysis/{id}` | Retrieve a cached analysis |

### POST /api/analyze

**Request:**
```json
{ "project_path": "/absolute/path/to/project" }
```

**Response:** `AnalysisResult` with `issues`, `frontend_calls`, `backend_endpoints`, `architecture`, and `summary`.

---

## Future Improvements

- [ ] Support Express.js (Node.js) backend routes
- [ ] Support Django REST Framework
- [ ] File upload / ZIP analysis (for projects not on the server filesystem)
- [ ] Optional IBM watsonx.ai enhanced explanations
- [ ] VS Code extension integration
- [ ] GitHub Actions CI integration
- [ ] Report export (PDF / HTML)
- [ ] Multi-file request body inference

---

## Known Limitations

- Only analyzes projects accessible on the **server filesystem** (not uploaded ZIPs)
- Frontend analysis uses regex (not full AST) — complex expressions may be missed
- Backend analysis supports **FastAPI** only (MVP scope)
- Response field detection relies on heuristic proximity scanning

---

## Project Structure

```
BARA/
├── frontend/           # React + Vite + TypeScript UI
│   └── src/
│       ├── pages/      # HomePage, ResultsPage
│       ├── components/ # ArchitectureDiagram, IssueList, IssueDetail
│       ├── api.ts      # Backend API client
│       └── types.ts    # Shared TypeScript types
├── backend/            # FastAPI backend
│   ├── app/
│   │   ├── main.py           # FastAPI app entry point
│   │   ├── routes/           # HTTP route handlers
│   │   ├── services/         # Analysis orchestration
│   │   ├── analyzers/        # Scanner, frontend/backend analyzers, mismatch detector
│   │   └── models/           # Pydantic data models
│   └── tests/                # pytest test suite (47 tests)
├── examples/
│   └── demo-project/   # Intentionally broken project for demo
│       ├── frontend/src/api.js
│       └── backend/main.py
├── .env.example        # Environment variable template
└── README.md
```
