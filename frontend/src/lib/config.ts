// NEXT_PUBLIC_API_BASE_URL is the canonical name (set this on Render).
// NEXT_PUBLIC_API_URL is kept as a fallback for any deploy still using the
// older name from before auth was added, so a stale env var name doesn't
// silently fall back to localhost in production.
const rawBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

// Strip trailing slash(es) so `${API_BASE_URL}${path}` (path always starts
// with "/") never produces a double slash - a double slash in the request
// path would otherwise cause the backend's public-route allowlist (health,
// login) to reject it as unauthenticated.
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");
