const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");
let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let epoch = 0;
export interface AuthUser {
  id: string;
  email: string;
  name: string;
}
export function setAccessToken(token: string | null) {
  epoch++;
  accessToken = token;
}
export function getAccessToken() {
  return accessToken;
}
async function authError(response: Response, fallback: string) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return new Error(body.detail);
  } catch {}
  return new Error(fallback);
}
export async function login(email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await authError(response, "Login failed");
  setAccessToken((await response.json()).access_token);
}
export async function register(name: string, email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password }),
  });
  if (!response.ok) throw await authError(response, "Registration failed");
  await login(email, password);
}
export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    const started = epoch;
    refreshPromise = (async () => {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        accessToken = null;
        throw new Error("Session expired. Please sign in.");
      }
      const data = await response.json();
      if (epoch !== started) throw new Error("Session changed");
      accessToken = data.access_token;
      return data.access_token as string;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}
export async function authenticatedFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  if (!accessToken) await refreshAccessToken();
  const sent = accessToken;
  const send = (token: string | null) => {
    const headers = new Headers(options.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(`${API_URL}${path}`, {
      ...options,
      credentials: "include",
      headers,
    });
  };
  let response = await send(sent);
  if (response.status === 401) {
    const token =
      accessToken !== sent && accessToken
        ? accessToken
        : await refreshAccessToken();
    response = await send(token);
  }
  return response;
}
export async function currentUser(): Promise<AuthUser> {
  const response = await authenticatedFetch("/users/me");
  if (!response.ok) throw new Error("Session expired");
  return response.json();
}
export async function logout() {
  try {
    const response = await fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok)
      throw new Error("Unable to revoke session. Please retry logout.");
  } finally {
    setAccessToken(null);
  }
}
