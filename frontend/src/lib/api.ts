import { API_BASE_URL } from "@/lib/config";
import { clearToken, getToken } from "@/lib/auth";
import type {
  AdminKnowledgeCreateInput,
  AdminKnowledgeItem,
  AdminKnowledgeUpdateInput,
  BuildInfoResponse,
  Course,
  CourseCreateInput,
  CourseSource,
  CourseSourceNotesInput,
  CourseUpdateInput,
  CourseVersion,
  DiagnosticsResponse,
  GenerationJob,
  HealthResponse,
  LoginResponse,
  Priority,
  SourceCategory,
  AIUsageSummary,
  CourseAIUsage,
} from "@/lib/types";

// `status` is set for any real HTTP response (even error ones), so callers
// (e.g. /login's diagnostics block) can show the exact status code.
// `isNetworkError` distinguishes "fetch() itself rejected" - almost always
// a wrong/unreachable API_BASE_URL or a CORS rejection at the browser level
// - from a normal HTTP error response, since the browser gives no further
// detail (no status code, no body) in that case.
export class ApiError extends Error {
  status?: number;
  isNetworkError: boolean;
  method: string;
  path: string;
  tokenPresent: boolean;

  constructor(
    message: string,
    options?: {
      status?: number;
      isNetworkError?: boolean;
      method?: string;
      path?: string;
      tokenPresent?: boolean;
    },
  ) {
    super(message);
    this.status = options?.status;
    this.isNetworkError = options?.isNetworkError ?? false;
    this.method = options?.method ?? "GET";
    this.path = options?.path ?? "";
    this.tokenPresent = options?.tokenPresent ?? false;
  }
}

/**
 * User-facing diagnostics for Generation / AI Usage failures.
 * Never includes token values or secrets — only whether a token was present.
 */
export function formatApiErrorForDisplay(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) {
      return "Session expired or not authenticated. Please log in again.";
    }
    if (err.status === 404) {
      return `API route not found: ${err.method} ${err.path}`;
    }
    if (err.isNetworkError) {
      return (
        `Browser could not reach this endpoint. Check CORS/preflight for ` +
        `${err.method} ${err.path}. (token=${err.tokenPresent})`
      );
    }
    const statusPart = err.status != null ? `status ${err.status}` : "no status";
    const detail = err.message?.trim() ? err.message : "Request failed";
    return (
      `${err.method} ${err.path} — ${statusPart} — token=${err.tokenPresent} — ${detail}`
    );
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "Request failed";
}

const LOGIN_PATH = "/auth/login";
const NETWORK_ERROR_MESSAGE = "Network/CORS/API URL error";

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const method = (init.method ?? "GET").toUpperCase();
  const token = getToken();
  const tokenPresent = Boolean(token);
  // Only set JSON Content-Type when we actually send a JSON body. Putting
  // application/json on bare GETs forces an unnecessary CORS preflight.
  const hasJsonBody = init.body != null && !isFormData;

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      method,
      headers: {
        ...(hasJsonBody ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    // fetch() rejects (rather than resolving with an error response) for
    // network failures, a wrong/unreachable host, and CORS rejections at
    // the browser level - the browser deliberately gives no more detail
    // than this for CORS failures.
    throw new ApiError(NETWORK_ERROR_MESSAGE, {
      isNetworkError: true,
      method,
      path,
      tokenPresent,
    });
  }

  if (res.status === 401 && path !== LOGIN_PATH) {
    // Expired/invalid session - drop the stale token and send the user
    // back to /login instead of surfacing a confusing API error.
    clearToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // response body wasn't JSON; keep statusText
    }
    throw new ApiError(detail, {
      status: res.status,
      method,
      path,
      tokenPresent,
    });
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// Every download route requires the same Bearer token as any other API
// call (see backend/app/auth/middleware.py `PUBLIC_ROUTES` - downloads are
// not in it), so a plain `<a href>` pointing at these URLs would always
// 401 in the browser instead of downloading anything. This fetches the
// file with the same auth header apiFetch uses, then triggers a save via
// a throwaway object URL - which also means a missing-file 404 or an
// expired session surfaces as a normal in-app error instead of a raw
// browser error page.
async function downloadFile(path: string, filename: string): Promise<void> {
  const method = "GET";
  const token = getToken();
  const tokenPresent = Boolean(token);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new ApiError(NETWORK_ERROR_MESSAGE, {
      isNetworkError: true,
      method,
      path,
      tokenPresent,
    });
  }

  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new ApiError("Session expired - redirecting to login", {
      status: 401,
      method,
      path,
      tokenPresent,
    });
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data?.detail) detail = data.detail;
    } catch {
      // response body wasn't JSON; keep statusText
    }
    throw new ApiError(detail, {
      status: res.status,
      method,
      path,
      tokenPresent,
    });
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    apiFetch<LoginResponse>(LOGIN_PATH, {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  // Public, unauthenticated status checks - used by /login's diagnostics
  // block (see app/login/page.tsx) to self-diagnose deployment
  // misconfiguration instead of just showing a generic failure.
  health: () => apiFetch<HealthResponse>("/health"),
  buildInfo: () => apiFetch<BuildInfoResponse>("/build-info"),
  diagnostics: () => apiFetch<DiagnosticsResponse>("/auth/diagnostics"),

  // Admin knowledge (default: active primary only)
  listKnowledgeItems: (opts?: { includeInactive?: boolean }) =>
    apiFetch<AdminKnowledgeItem[]>(
      opts?.includeInactive
        ? "/admin/knowledge?active_only=false&include_inactive=true"
        : "/admin/knowledge",
    ),
  cleanupKnowledgeDuplicates: (opts?: { dryRun?: boolean; confirm?: boolean }) => {
    const dryRun = opts?.dryRun ?? true;
    const confirm = opts?.confirm ?? false;
    const qs = new URLSearchParams({
      dry_run: String(dryRun),
      confirm: String(confirm),
    });
    return apiFetch<{
      deactivated_count?: number;
      would_deactivate_count?: number;
      message: string;
      deactivated?: unknown[];
      would_deactivate?: unknown[];
      kept_active: unknown[];
      applied?: boolean;
      dry_run?: boolean;
      backup?: { path: string } | null;
    }>(`/admin/knowledge/cleanup-duplicates?${qs}`, { method: "POST" });
  },
  createKnowledgeItem: (payload: AdminKnowledgeCreateInput) =>
    apiFetch<AdminKnowledgeItem>("/admin/knowledge", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateKnowledgeItem: (id: number, payload: AdminKnowledgeUpdateInput) =>
    apiFetch<AdminKnowledgeItem>(`/admin/knowledge/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteKnowledgeItem: (
    id: number,
    opts?: { dryRun?: boolean; confirm?: boolean; purge?: boolean },
  ) => {
    const qs = new URLSearchParams({
      dry_run: String(opts?.dryRun ?? false),
      confirm: String(opts?.confirm ?? true),
      purge: String(opts?.purge ?? false),
    });
    return apiFetch<{ message: string; applied?: boolean; action?: string }>(
      `/admin/knowledge/${id}?${qs}`,
      { method: "DELETE" },
    );
  },
  activateKnowledgeItem: (id: number) =>
    apiFetch<AdminKnowledgeItem>(
      `/admin/knowledge/${id}/activate?dry_run=false&confirm=true`,
      { method: "POST" },
    ),

  // Courses
  listCourses: () => apiFetch<Course[]>("/courses"),
  createCourse: (payload: CourseCreateInput) =>
    apiFetch<Course>("/courses", { method: "POST", body: JSON.stringify(payload) }),
  getCourse: (id: number) => apiFetch<Course>(`/courses/${id}`),
  updateCourse: (id: number, payload: CourseUpdateInput) =>
    apiFetch<Course>(`/courses/${id}`, { method: "PUT", body: JSON.stringify(payload) }),

  // Sources
  listSources: (courseId: number) =>
    apiFetch<CourseSource[]>(`/courses/${courseId}/sources`),
  uploadSource: (
    courseId: number,
    file: File,
    sourceCategory: SourceCategory,
    priority: Priority,
    opts?: { title?: string; include_in_generation?: boolean },
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source_category", sourceCategory);
    form.append("priority", priority);
    if (opts?.title) form.append("source_title", opts.title);
    if (opts?.include_in_generation !== undefined) {
      form.append("include_in_generation", String(opts.include_in_generation));
    }
    return apiFetch<CourseSource>(`/courses/${courseId}/sources/upload`, {
      method: "POST",
      body: form,
    });
  },
  addNotesSource: (courseId: number, payload: CourseSourceNotesInput) =>
    apiFetch<CourseSource>(`/courses/${courseId}/sources/notes`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteSource: (courseId: number, sourceId: number) =>
    apiFetch<{ message: string; applied?: boolean }>(
      `/courses/${courseId}/sources/${sourceId}?dry_run=false&confirm=true`,
      { method: "DELETE" },
    ),
  updateSourceCategory: (courseId: number, sourceId: number, sourceCategory: SourceCategory) =>
    apiFetch<CourseSource>(`/courses/${courseId}/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify({ source_category: sourceCategory }),
    }),

  // Generation — paths must stay aligned with backend/app/routers/generation.py + jobs.py
  generateCourseMap: (courseId: number) =>
    apiFetch<Course>(`/courses/${courseId}/generate-map`, { method: "POST" }),
  generateCourse: (
    courseId: number,
    body?: { generation_quality_mode?: "preview" | "premium" },
  ) =>
    apiFetch<GenerationJob>(`/courses/${courseId}/generate`, {
      method: "POST",
      body: JSON.stringify(body ?? { generation_quality_mode: "premium" }),
    }),
  getJob: (jobId: number) => apiFetch<GenerationJob>(`/jobs/${jobId}`),
  listVersions: (courseId: number) =>
    apiFetch<CourseVersion[]>(`/courses/${courseId}/versions`),
  downloadLatestDocx: (courseId: number, filename: string) =>
    downloadFile(`/courses/${courseId}/download/latest`, filename),
  // Only meaningful once a job has a `partial_docx_path` set (status
  // "partial", occasionally "failed" if one was saved just before the
  // final failure) - see backend/app/routers/jobs.py `download_partial`.
  downloadPartialDocx: (jobId: number, filename: string) =>
    downloadFile(`/jobs/${jobId}/download-partial`, filename),

  // AI Usage Center — estimated app usage only (backend labels it the same way)
  // Paths: GET /ai-usage/summary, GET /courses/{id}/ai-usage
  getAIUsageSummary: () => apiFetch<AIUsageSummary>("/ai-usage/summary"),
  getCourseAIUsage: (courseId: number) =>
    apiFetch<CourseAIUsage>(`/courses/${courseId}/ai-usage`),
};
