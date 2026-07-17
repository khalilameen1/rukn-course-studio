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
  correlationId?: string;

  constructor(
    message: string,
    options?: {
      status?: number;
      isNetworkError?: boolean;
      method?: string;
      path?: string;
      tokenPresent?: boolean;
      correlationId?: string;
    },
  ) {
    super(message);
    this.status = options?.status;
    this.isNetworkError = options?.isNetworkError ?? false;
    this.method = options?.method ?? "GET";
    this.path = options?.path ?? "";
    this.tokenPresent = options?.tokenPresent ?? false;
    this.correlationId = options?.correlationId;
  }
}

const LOGIN_PATH = "/auth/login";
const NETWORK_ERROR_MESSAGE = "Network/CORS/API URL error";

function normalizeApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    if ("msg" in detail) return String((detail as { msg: unknown }).msg);
    if ("detail" in detail) return normalizeApiDetail((detail as { detail: unknown }).detail);
    return JSON.stringify(detail);
  }
  return "Request failed";
}

/**
 * Short, user-facing error copy for product surfaces (Generate, courses, AI usage).
 * Deployment diagnostics on /login keep richer detail via describeError().
 */
/** Arabic, user-facing copy for source upload failures (keeps real cause). */
export function formatUploadErrorForDisplay(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 400) {
      return err.message?.trim()
        ? `طلب غير صحيح: ${err.message}`
        : "طلب غير صحيح. تأكد من اختيار ملف صالح.";
    }
    if (err.status === 401) {
      return "انتهت الجلسة. سجّل الدخول ثم أعد رفع المصدر.";
    }
    if (err.status === 403) {
      return "ليست لديك صلاحية لرفع مصادر لهذا الكورس.";
    }
    if (err.status === 413) {
      return err.message?.trim()
        ? `الملف أكبر من الحد المسموح: ${err.message}`
        : "الملف أكبر من الحد المسموح للرفع.";
    }
    if (err.status === 415) {
      return err.message?.trim()
        ? `نوع الملف غير مدعوم: ${err.message}`
        : "نوع الملف غير مدعوم. المسموح: PDF، DOCX، TXT، MD.";
    }
    if (err.status === 404) {
      return "الكورس غير موجود. حدّث الصفحة أو أنشئ كورساً جديداً.";
    }
    if (err.isNetworkError) {
      return "تعذر الوصول إلى الخادم. تحقق من الاتصال وعنوان الـ API.";
    }
    if (err.status != null && err.status >= 500) {
      const ref = err.correlationId ? ` (مرجع: ${err.correlationId})` : "";
      return err.message?.includes("disk") || err.message?.includes("Storage")
        ? `${err.message}${ref}`
        : `خطأ غير متوقع في الخادم أثناء الرفع${ref}. إن استمر، راجع سجلات السيرفر.`;
    }
    return err.message || "فشل رفع المصدر.";
  }
  if (err instanceof Error) return err.message;
  return "فشل رفع المصدر.";
}

export function formatApiErrorForDisplay(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) {
      return "Session expired. Please sign in again.";
    }
    if (err.isNetworkError) {
      return "Could not reach the server. Check your connection or API URL.";
    }
    if (err.status === 403) {
      return err.message || "You do not have permission for this action.";
    }
    if (err.status === 404) {
      return err.message || "The requested item was not found.";
    }
    if (err.status === 409) {
      return err.message || "Another action is already in progress.";
    }
    if (err.status === 422) {
      return err.message || "Please check your input and try again.";
    }
    if (err.status === 429) {
      return "Too many requests. Please wait a moment and try again.";
    }
    if (err.status === 503) {
      return err.message || "The AI provider is not configured or unavailable.";
    }
    if (err.status != null && err.status >= 500) {
      if (err.correlationId) {
        return `Something went wrong on the server (ref: ${err.correlationId}). Try again in a moment.`;
      }
      // Prefer the API detail when it already includes a reference id.
      if (err.message && /reference id/i.test(err.message)) return err.message;
      return "Something went wrong on the server. Try again in a moment.";
    }
    return err.message || "Request failed";
  }
  if (err instanceof Error) {
    if (err.message === NETWORK_ERROR_MESSAGE) {
      return "Could not reach the server. Check your connection or API URL.";
    }
    return err.message;
  }
  return "Request failed";
}

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
    let correlationId: string | undefined;
    try {
      const data = await res.json();
      if (data?.detail != null) detail = normalizeApiDetail(data.detail);
      if (typeof data?.correlation_id === "string") correlationId = data.correlation_id;
    } catch {
      // response body wasn't JSON; keep statusText
    }
    throw new ApiError(detail, {
      status: res.status,
      method,
      path,
      tokenPresent,
      correlationId,
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
    let correlationId: string | undefined;
    try {
      const data = await res.json();
      if (data?.detail != null) detail = normalizeApiDetail(data.detail);
      if (typeof data?.correlation_id === "string") correlationId = data.correlation_id;
    } catch {
      // response body wasn't JSON; keep statusText
    }
    throw new ApiError(detail, {
      status: res.status,
      method,
      path,
      tokenPresent,
      correlationId,
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
  reprocessSource: (courseId: number, sourceId: number, password?: string) => {
    const form = new FormData();
    if (password) form.append("password", password);
    return apiFetch<CourseSource>(`/courses/${courseId}/sources/${sourceId}/reprocess`, {
      method: "POST",
      body: form,
    });
  },

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
  getLatestJob: (courseId: number) =>
    apiFetch<GenerationJob>(`/courses/${courseId}/generate/latest`),
  cancelGeneration: (courseId: number, jobId: number) =>
    apiFetch<GenerationJob>(`/courses/${courseId}/generate/${jobId}/cancel`, {
      method: "POST",
    }),
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
