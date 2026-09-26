# BARA Demo Project – Intentional Bugs

This project is **intentionally broken** to demonstrate BARA's detection capabilities.

## Intentional Bugs

| # | Bug Type | Frontend | Backend | Description |
|---|----------|----------|---------|-------------|
| 1 | PATH_MISMATCH | `fetch("/api/users")` | `@app.get("/api/user")` | Singular vs plural path |
| 2 | METHOD_MISMATCH | `fetch("/api/login", {method: "POST"})` | `@app.get("/api/login")` | POST vs GET |
| 3 | REQUEST_FIELD_MISMATCH | `body: {username, email}` | `class CreateUserRequest: name: str` | 'username' vs 'name' |
| 4 | RESPONSE_FIELD_MISMATCH | `data.name` | `class UserResponse: full_name: str` | 'name' vs 'full_name' |
| 5 | QUERY_PARAM_MISMATCH | `fetch("/api/todos?limit=10")` | `def get_todos(page_size: int)` | 'limit' vs 'page_size' |

## Running BARA on This Project

```bash
# From the BARA root directory
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/path/to/BARA/examples/demo-project"}'
```

BARA should detect all 5 bugs above.
