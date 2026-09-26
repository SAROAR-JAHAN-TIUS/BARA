"""
BARA Demo Project – Backend (FastAPI)

This is an INTENTIONALLY BROKEN backend for demonstrating BARA's detection capabilities.

Intentional bugs:
  BUG 1: Wrong path  – frontend calls /api/users, backend provides /api/user  (PATH_MISMATCH / MISSING)
  BUG 2: Method mismatch – frontend sends POST /api/login, backend only has GET /api/login
  BUG 3: Request field mismatch – frontend sends 'username', backend expects 'name'
  BUG 4: Response field mismatch – backend returns 'full_name', frontend reads 'name'
  BUG 5: Query param mismatch – frontend uses ?limit=10, backend expects ?page_size
"""
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Demo Todo API")


# ── Data Models ─────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    """BUG 3: Frontend sends 'username', but this model expects 'name'."""
    name: str          # <── backend expects 'name'
    email: str


class UserResponse(BaseModel):
    """BUG 4: Frontend reads 'name', but this model returns 'full_name'."""
    id: int
    full_name: str     # <── backend returns 'full_name'
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


# ── Endpoints ────────────────────────────────────────────────────────────────

# BUG 1: Path is /api/user  (singular) – frontend calls /api/users (plural)
@app.get("/api/user")
def get_users():
    """Get all users. BUG 1: path should be /api/users"""
    return [{"id": 1, "full_name": "Alice", "email": "alice@example.com"}]


# BUG 2: Method is GET – frontend sends POST /api/login
@app.get("/api/login")
def login(email: str, password: str):
    """Login endpoint. BUG 2: should be POST, not GET"""
    return {"token": "fake-token"}


# BUG 3 + BUG 4: Request field 'username' vs 'name'; response 'full_name' vs 'name'
@app.post("/api/register")
def register(body: CreateUserRequest):
    """Register a new user."""
    return UserResponse(id=1, full_name=body.name, email=body.email)


# BUG 5: Backend uses 'page_size' – frontend sends ?limit=10
@app.get("/api/todos")
def get_todos(page_size: int = 20):
    """Get todos. BUG 5: frontend uses ?limit, backend expects ?page_size"""
    return [{"id": 1, "title": "Buy groceries", "done": False}]


@app.get("/api/todos/{todo_id}")
def get_todo(todo_id: int):
    """Get a specific todo by ID."""
    return {"id": todo_id, "title": "Buy groceries", "done": False}
