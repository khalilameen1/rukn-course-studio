import { API_BASE_URL } from "@/lib/config";
import { clearToken, getToken } from "@/lib/auth";
import type {
  AdminKnowledgeCreateInput,
  AdminKnowledgeItem,
  AdminKnowledgeUpdateInput,
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

  constructor(message: string, status?: number, isNetworkError = false) {
    super(message);
    this.status = status;
    this.isNetworkError = isNetworkError;
  }
}

const LOGIN_PATH = "/auth/login";
const NETWORK_ERROR_MESSAGE = "Network/CORS/API URL error";

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const token = getToken();

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    // fetch() rejects (rather than resolving with an error response) for
    // network failures, a wrong/unreachable host, and CORS rejections at
    // the browser level - the browser deliberately gives no more detail
    // than this for CORS failures.
    throw new ApiError(NETWORK_ERROR_MESSAGE, undefined, true);
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
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export function latestDownloadUrl(courseId: number): string {
  return `${API_BASE_URL}/courses/${courseId}/download/latest`;
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
  diagnostics: () => apiFetch<DiagnosticsResponse>("/auth/diagnostics"),

  // Admin knowledge
  listKnowledgeItems: () => apiFetch<AdminKnowledgeItem[]>("/admin/knowledge"),
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
  deleteKnowledgeItem: (id: number) =>
    apiFetch<void>(`/admin/knowledge/${id}`, { method: "DELETE" }),
  activateKnowledgeItem: (id: number) =>
    apiFetch<AdminKnowledgeItem>(`/admin/knowledge/${id}/activate`, {
      method: "POST",
    }),

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
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source_category", sourceCategory);
    form.append("priority", priority);
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
    apiFetch<void>(`/courses/${courseId}/sources/${sourceId}`, { method: "DELETE" }),

  // Generation
  generateCourse: (courseId: number) =>
    apiFetch<GenerationJob>(`/courses/${courseId}/generate`, { method: "POST" }),
  getJob: (jobId: number) => apiFetch<GenerationJob>(`/jobs/${jobId}`),
  listVersions: (courseId: number) =>
    apiFetch<CourseVersion[]>(`/courses/${courseId}/versions`),
};
