// Single-admin-user auth token storage for this internal MVP - no
// multi-user sessions, just one token in localStorage. See
// backend/app/auth/ for the token itself.

const TOKEN_KEY = "rukn_auth_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}
