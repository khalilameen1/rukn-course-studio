// NEXT_PUBLIC_API_BASE_URL is the canonical name (set this on Render).
// NEXT_PUBLIC_API_URL is kept as a fallback for any deploy still using the
// older name from before auth was added, so a stale env var name doesn't
// silently fall back to localhost in production.
const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL;

// Whether either env var was actually set - distinct from API_BASE_URL
// below, which always has a value (the localhost fallback). Used by
// /login's diagnostics block and submit handler to show "Backend API URL
// is not configured" instead of silently trying (and failing against) the
// localhost fallback in a deployed environment. next.config.ts already
// fails the production *build* if this is unset, so seeing this false at
// runtime in production means the currently-running build predates that
// check and should be redeployed.
export const API_BASE_URL_CONFIGURED = Boolean(configuredBaseUrl);

const rawBaseUrl = configuredBaseUrl ?? "http://localhost:8000";

/**
 * Backend origin only: strip trailing slashes and accidental `/health`
 * (or login) suffixes so fetch never hits `…/health/auth/login`.
 */
export function normalizeApiBaseUrl(raw: string): string {
  let url = raw.trim().replace(/\/+$/, "");
  const lower = url.toLowerCase();
  for (const suffix of ["/health", "/auth/login", "/auth/diagnostics"]) {
    if (lower.endsWith(suffix)) {
      url = url.slice(0, -suffix.length).replace(/\/+$/, "");
      break;
    }
  }
  return url;
}

// Strip trailing slash(es) so `${API_BASE_URL}${path}` (path always starts
// with "/") never produces a double slash - a double slash in the request
// path would otherwise cause the backend's public-route allowlist (health,
// login) to reject it as unauthenticated.
export const API_BASE_URL = normalizeApiBaseUrl(rawBaseUrl);
