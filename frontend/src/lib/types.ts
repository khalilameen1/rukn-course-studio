// Mirrors backend/app/models/enums.py and backend/app/schemas/*.py.
// Keep in sync manually for now (no shared codegen in MVP).

export type ItemType = "markdown" | "json" | "docx_template";

export type StructureMode =
  | "connected_no_modules"
  | "connected_modules_with_bridge_projects";

export type ExplanationLevel = "final_only" | "short_summary" | "full_report";

export type SourceCategory =
  | "scientific_reference"
  | "flow_reference"
  | "old_course"
  | "user_notes"
  | "raw_material";

export type GenerationPreset =
  | "conservative"
  | "balanced"
  | "creative"
  | "fusion"
  | "strict_teleprompter";

export type Priority = "high" | "medium" | "low";

export type JobStatus = "pending" | "running" | "partial" | "failed" | "completed";

export interface AdminKnowledgeItem {
  id: number;
  key: string;
  title: string;
  item_type: ItemType;
  content_text: string | null;
  file_path: string | null;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminKnowledgeCreateInput {
  key: string;
  title: string;
  item_type: ItemType;
  content_text?: string | null;
  file_path?: string | null;
  version?: number;
  is_active?: boolean;
}

export type AdminKnowledgeUpdateInput = Partial<AdminKnowledgeCreateInput>;

export interface Course {
  id: number;
  title: string;
  audience: string;
  outcome: string;
  special_notes: string | null;
  course_type: string;
  structure_mode: StructureMode;
  manual_map_text: string | null;
  explanation_level: ExplanationLevel;
  generation_preset: GenerationPreset;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CourseCreateInput {
  title: string;
  audience: string;
  outcome: string;
  special_notes?: string | null;
  structure_mode: StructureMode;
  manual_map_text?: string | null;
  explanation_level?: ExplanationLevel;
  generation_preset?: GenerationPreset;
}

export type CourseUpdateInput = Partial<CourseCreateInput> & { status?: string };

export interface CourseSource {
  id: number;
  course_id: number;
  source_category: SourceCategory;
  original_filename: string | null;
  file_path: string | null;
  mime_type: string | null;
  extracted_text: string | null;
  priority: Priority;
  status: string;
  created_at: string;
}

export interface CourseSourceNotesInput {
  text: string;
  source_category?: SourceCategory;
  priority?: Priority;
}

export interface CourseSourceCategoryUpdateInput {
  source_category: SourceCategory;
}

export interface GenerationJob {
  id: number;
  course_id: number;
  status: JobStatus;
  current_stage: string | null;
  progress_percent: number;
  output_docx_path: string | null;
  error_message: string | null;
  // Short, user-safe recovery signals (see backend/app/models/generation_job.py)
  // - only meaningful once a run has stopped (status "partial" or "failed").
  last_completed_step: string | null;
  completed_modules_count: number;
  completed_reels_count: number;
  error_category: string | null;
  partial_docx_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface CourseVersion {
  id: number;
  course_id: number;
  version_number: number;
  output_docx_path: string;
  summary_text: string | null;
  report_text: string | null;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface HealthResponse {
  status: string;
  environment: string;
}

// Mirrors backend/app/schemas/auth.py DiagnosticsResponse - see
// backend/app/auth/diagnostics.py for exactly what is/isn't returned
// (never a credential, connection string, or API key value).
export interface DiagnosticsResponse {
  auth_enabled: boolean;
  admin_username_configured: boolean;
  admin_password_configured: boolean;
  auth_secret_key_configured: boolean;
  frontend_origin_configured: boolean;
  frontend_origin_value: string | null;
  cors_origins: string[];
  database_backend: string;
  storage_dir_configured: boolean;
  storage_dir_exists: boolean;
  storage_dir_writable: boolean;
  // Raw AI_PROVIDER value ("fake"/"anthropic") - not a secret, just which
  // provider is selected. ai_provider_ready is the only readiness signal;
  // never a credential/key value.
  ai_provider: string;
  ai_provider_ready: boolean;
}

/** Estimated app usage only — never a real Anthropic account balance. */
export interface AIUsageSummary {
  provider: string;
  model: string;
  default_preset: string;
  last_request_status: string | null;
  last_request_at: string | null;
  estimated_cost_today_usd: number;
  estimated_cost_this_month_usd: number;
  last_error_category: string | null;
  last_error_message: string | null;
}

export interface CourseAIUsage {
  course_id: number;
  estimated_cost_usd: number;
  event_count: number;
}
