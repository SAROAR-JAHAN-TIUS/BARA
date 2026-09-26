// BARA Demo Project – Frontend API calls
//
// This is INTENTIONALLY BROKEN code to demonstrate BARA's detection capabilities.
//
// Intentional bugs:
//   BUG 1: Calls /api/users (plural) — backend only provides /api/user (singular)
//   BUG 2: Sends POST /api/login — backend only accepts GET /api/login
//   BUG 3: Sends body field 'username' — backend expects 'name'
//   BUG 4: Reads response field 'name' — backend returns 'full_name'
//   BUG 5: Sends query param ?limit=10 — backend expects ?page_size

// BUG 1: Wrong API path — /api/users vs /api/user
async function getUsers() {
  const response = await fetch("/api/users");   // BUG 1
  const data = await response.json();
  return data.map((u) => u.name);               // BUG 4: reads .name, backend returns .full_name
}

// BUG 2: Method mismatch — frontend uses POST, backend only has GET
async function login(email, password) {
  const response = await fetch("/api/login", {  // BUG 2
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await response.json();
  return data.token;
}

// BUG 3 + BUG 4: Request field mismatch + response field mismatch
async function registerUser(username, email) {
  const response = await fetch("/api/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email }),   // BUG 3: sends 'username', backend expects 'name'
  });
  const data = await response.json();
  console.log(data.name);                        // BUG 4: reads 'name', backend returns 'full_name'
}

// BUG 5: Query param mismatch — frontend sends ?limit, backend expects ?page_size
async function getTodos() {
  const response = await fetch("/api/todos?limit=10");  // BUG 5
  const data = await response.json();
  return data;
}

// This one is CORRECT — matches the backend exactly
async function getTodo(id) {
  const response = await fetch(`/api/todos/${id}`);
  const data = await response.json();
  return data;
}

export { getUsers, login, registerUser, getTodos, getTodo };
