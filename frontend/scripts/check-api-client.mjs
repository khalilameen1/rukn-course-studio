/**
 * Lightweight contract check (no Jest): Generation + AI Usage pages must
 * call the authenticated `api` client with paths that match the backend.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

const apiTs = read("src/lib/api.ts");
const generatePanel = read("src/components/courses/GeneratePanel.tsx");
const aiUsagePage = read("src/app/ai-usage/page.tsx");

const requiredApiSnippets = [
  'apiFetch<GenerationJob>(`/courses/${courseId}/generate`',
  "apiFetch<GenerationJob>(`/jobs/${jobId}?course_id=${courseId}`)",
  "finalize-saved",
  'apiFetch<AIUsageSummary>("/ai-usage/summary")',
  'apiFetch<CourseAIUsage>(`/courses/${courseId}/ai-usage`)',
  "Authorization: `Bearer ${token}`",
  "export function formatApiErrorForDisplay",
];

for (const snip of requiredApiSnippets) {
  if (!apiTs.includes(snip)) {
    console.error("api.ts missing required snippet:", snip);
    process.exit(1);
  }
}

if (!generatePanel.includes("api.generateCourse") || !generatePanel.includes("formatApiErrorForDisplay")) {
  console.error("GeneratePanel must use api.generateCourse + formatApiErrorForDisplay");
  process.exit(1);
}
if (!generatePanel.includes("finalizeSavedJob") || !generatePanel.includes("Download completed")) {
  console.error("GeneratePanel must expose Finish export + Download completed recovery actions");
  process.exit(1);
}
if (generatePanel.includes("fetch(") && !generatePanel.includes("api.")) {
  console.error("GeneratePanel must not use raw fetch for API calls");
  process.exit(1);
}

if (!aiUsagePage.includes("getAIUsageSummary")) {
  console.error("AI Usage page must use api.getAIUsageSummary");
  process.exit(1);
}
if (aiUsagePage.includes("fetch(")) {
  console.error("AI Usage page must not use raw fetch");
  process.exit(1);
}

const errorCases = [
  "Session expired. Please sign in again.",
  "Could not reach the server. Check your connection or API URL.",
  "Too many requests. Please wait a moment and try again.",
];
for (const msg of errorCases) {
  if (!apiTs.includes(msg)) {
    console.error("formatApiErrorForDisplay missing branch text:", msg);
    process.exit(1);
  }
}

console.log("check-api-client: ok");
