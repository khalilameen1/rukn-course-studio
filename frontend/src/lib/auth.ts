// Auth token + capability scopes for the internal MVP.

const TOKEN_KEY = "rukn_auth_token";
const SCOPES_KEY = "rukn_auth_scopes";

export const SCOPE_COURSES = "courses:*";
export const SCOPE_ADMIN_KNOWLEDGE = "admin_knowledge:*";
export const SCOPE_AI_USAGE = "ai_usage:*";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string, scopes?: string[]): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  if (scopes) {
    window.localStorage.setItem(SCOPES_KEY, JSON.stringify(scopes));
  }
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(SCOPES_KEY);
}

export function getScopes(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(SCOPES_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed.filter((s) => typeof s === "string");
    }
  } catch {
    /* ignore */
  }
  // Fallback: decode payload without verifying (server still enforces).
  const token = getToken();
  if (!token) return [];
  try {
    const payloadB64 = token.split(".")[0];
    if (!payloadB64) return [];
    const padded = payloadB64 + "=".repeat((4 - (payloadB64.length % 4)) % 4);
    const json = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    const payload = JSON.parse(json);
    if (Array.isArray(payload.scopes)) return payload.scopes;
  } catch {
    /* ignore */
  }
  // Fail closed: missing scopes → courses only (never assume admin).
  return [SCOPE_COURSES];
}

export function hasScope(scope: string): boolean {
  return getScopes().includes(scope);
}
