// Mirrors backend/app/models/enums.py and backend/app/schemas/*.py.
// Keep in sync manually for now (no shared codegen in MVP).

export type ItemType = "markdown" | "json" | "docx_template";

export type StructureMode =
  | "connected_no_modules"
  | "connected_modules_with_bridge_projects";

export type ExplanationLevel = "final_only" | "short_summary" | "full_report";

export type SourceCategory =
  | "main_content"
  | "supporting"
  | "spoken_style"
  | "old_course"
  | "notes";

export type Priority = "high" | "medium" | "low";

export type JobStatus = "pending" | "running" | "completed" | "failed";

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

export interface GenerationJob {
  id: number;
  course_id: number;
  status: JobStatus;
  current_stage: string | null;
  progress_percent: number;
  output_docx_path: string | null;
  error_message: string | null;
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
