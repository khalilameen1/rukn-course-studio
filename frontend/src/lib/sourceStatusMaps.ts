/** Human-readable labels for source extraction status codes (fallback when API omits status_message). */

const SOURCE_STATUS_LABEL: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  ready: "Ready",
  pending: "Processing",
  poor_extraction: "Poor extraction",
  password_required: "Password required",
  extraction_blocked: "Extraction blocked",
  scanned_no_text: "Scanned / no text",
  empty: "Empty",
  failed: "Processing failed",
  processing_failed: "Processing failed",
};

export function sourceStatusLabel(source: { status: string; status_message?: string }): string {
  return source.status_message ?? SOURCE_STATUS_LABEL[source.status] ?? source.status;
}
