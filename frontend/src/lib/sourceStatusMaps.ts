/** Human-readable labels for source extraction status codes (fallback when API omits status_message). */

const SOURCE_STATUS_LABEL: Record<string, string> = {
  ready: "Ready",
  pending: "Processing",
  poor_extraction: "Poor extraction",
  password_required: "Password required",
  empty: "Empty",
  failed: "Failed",
};

export function sourceStatusLabel(source: { status: string; status_message?: string }): string {
  return source.status_message ?? SOURCE_STATUS_LABEL[source.status] ?? source.status;
}
