/** Human-readable labels for source extraction status codes (fallback when API omits status_message). */

const SOURCE_STATUS_LABEL: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  ready: "Ready",
  pending: "Processing",
  poor_extraction: "Poor extraction",
  password_required: "Password required — Unlock",
  extraction_blocked: "Extraction blocked — Retry",
  scanned_no_text: "Scanned / no text — upload a text PDF",
  empty: "Empty",
  failed: "Processing failed — Retry",
  processing_failed: "Processing failed — Retry",
};

export function sourceStatusLabel(source: { status: string; status_message?: string }): string {
  return source.status_message ?? SOURCE_STATUS_LABEL[source.status] ?? source.status;
}
