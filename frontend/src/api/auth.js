/**
 * api/auth.js — JWT authentication helpers for the React frontend.
 *
 * Design notes:
 * - SENTINELGRAPH_DEMO_MODE=true (the default) means the backend accepts
 *   every request without a token.  In this mode the frontend renders a
 *   "Demo Mode" banner and stores a synthetic token in localStorage so
 *   downstream components don't need to special-case it.
 * - When DEMO_MODE is false the user must provide username + password via
 *   the login page.  The returned JWT is persisted in localStorage and
 *   attached as a Bearer header by the API client.
 */

const AUTH_KEY = "sentinelgraph_token";
const USER_KEY = "sentinelgraph_user";

/* ------------------------------------------------------------------ */
/*  Token persistence                                                  */
/* ------------------------------------------------------------------ */

export function getToken() {
  try {
    return localStorage.getItem(AUTH_KEY) || null;
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    localStorage.setItem(AUTH_KEY, token);
  } catch { /* noop */ }
}

export function clearToken() {
  try {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(USER_KEY);
  } catch { /* noop */ }
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setUser(user) {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch { /* noop */ }
}

/* ------------------------------------------------------------------ */
/*  API calls                                                          */
/* ------------------------------------------------------------------ */

const API_BASE = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "";

/**
 * POST /api/auth/token  { username, password }
 * Returns { access_token, token_type } on success.
 */
export async function loginRequest(username, password) {
  const resp = await fetch(`${API_BASE}/api/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail || `Login failed (${resp.status})`);
  }
  return resp.json();
}

/**
 * Probe whether the backend is running in DEMO_MODE.
 * GET /api/auth/token does not exist, but the 405/200 response
 * tells us the server is alive.  A simpler heuristic: check
 * whether the demo login succeeds with dummy credentials.
 * This is called once on mount.
 */
export async function detectDemoMode() {
  try {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 3000);
    const resp = await fetch(`${API_BASE}/api/auth/token`, {
      method: 'POST',
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: '__probe__', password: '__probe__' }),
    });
    clearTimeout(tid);
    return resp.ok;
  } catch {
    return false; // unreachable or timed out → not demo
  }
}

/**
 * Returns true if the user has a valid-ish token in localStorage.
 */
export function isAuthenticated() {
  return !!getToken();
}
