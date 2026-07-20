"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { api, formatApiErrorForDisplay } from "@/lib/api";
import type { WriterTestJobRead, WriterTestReelPublic } from "@/lib/types";

const STORAGE_KEY = (courseId: number) => `rukn.writerTest.${courseId}`;

type Props = {
  courseId: number;
  courseFingerprintHint?: string | null;
};

export default function WriterTestPanel({ courseId, courseFingerprintHint }: Props) {
  const [seriesContext, setSeriesContext] = useState("");
  const [t1, setT1] = useState("");
  const [t2, setT2] = useState("");
  const [t3, setT3] = useState("");
  const [linked, setLinked] = useState(false);
  const [result, setResult] = useState<WriterTestJobRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openReport, setOpenReport] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const submitting = useRef(false);
  const idempotencyKey = useRef<string | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY(courseId));
      if (!raw) return;
      const parsed = JSON.parse(raw) as { jobId?: number };
      if (parsed.jobId) {
        api.getWriterTestJob(courseId, parsed.jobId).then(setResult).catch(() => {
          /* stale local key */
        });
      }
    } catch {
      /* ignore */
    }
  }, [courseId]);

  function persist(job: WriterTestJobRead) {
    setResult(job);
    localStorage.setItem(
      STORAGE_KEY(courseId),
      JSON.stringify({
        jobId: job.job.id,
        fingerprint: job.config_fingerprint,
      }),
    );
  }

  function handleGenerate() {
    if (submitting.current || pending) return;
    const topics = [t1, t2, t3].map((t) => t.trim());
    if (topics.some((t) => !t)) {
      setError("أدخل ثلاثة موضوعات بالضبط");
      return;
    }
    submitting.current = true;
    setError(null);
    if (!idempotencyKey.current) {
      idempotencyKey.current = `wt-${courseId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    }
    startTransition(async () => {
      try {
        const job = await api.writerTest3Reels(courseId, {
          topics: topics.map((title) => ({ title })),
          series_linked: linked,
          series_context: seriesContext,
          idempotency_key: idempotencyKey.current || undefined,
          generation_quality_mode: "premium",
        });
        persist(job);
      } catch (err) {
        setError(formatApiErrorForDisplay(err));
      } finally {
        submitting.current = false;
      }
    });
  }

  function handleRetry(reel: WriterTestReelPublic) {
    if (!result || submitting.current) return;
    submitting.current = true;
    setError(null);
    startTransition(async () => {
      try {
        const job = await api.writerTest3Reels(courseId, {
          topics: [t1, t2, t3].map((title) => ({ title: title.trim() })),
          series_linked: linked,
          series_context: seriesContext,
          idempotency_key: `${idempotencyKey.current || "retry"}-${reel.reel_id}`,
          retry_reel_id: reel.reel_id,
          existing_job_id: result.job.id,
          generation_quality_mode: "premium",
        });
        persist(job);
      } catch (err) {
        setError(formatApiErrorForDisplay(err));
      } finally {
        submitting.current = false;
      }
    });
  }

  const fingerprintMismatch = Boolean(
    result &&
      (!result.context_matches_course ||
        (result.config_fingerprint &&
          courseFingerprintHint &&
          result.config_fingerprint !== courseFingerprintHint)),
  );

  return (
    <section className="space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <header>
        <h3 className="text-lg font-semibold">اختبار الكاتب بـ 3 ريلز</h3>
        <p className="text-sm text-muted">
          نفس الكاتب والمراجعات وبوابات الجودة المستخدمة في الكورس الكامل — بدون خريطة كاملة.
        </p>
      </header>

      <label className="block text-sm">
        سياق عام اختياري للسلسلة
        <textarea
          className="field-input mt-1 w-full"
          rows={2}
          value={seriesContext}
          onChange={(e) => setSeriesContext(e.target.value)}
        />
      </label>

      {[
        ["الموضوع الأول", t1, setT1],
        ["الموضوع الثاني", t2, setT2],
        ["الموضوع الثالث", t3, setT3],
      ].map(([label, value, setter]) => (
        <label key={label as string} className="block text-sm">
          {label as string}
          <input
            className="field-input mt-1 w-full"
            value={value as string}
            onChange={(e) => (setter as (v: string) => void)(e.target.value)}
          />
        </label>
      ))}

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={linked}
          onChange={(e) => setLinked(e.target.checked)}
        />
        الموضوعات مترابطة كسلسلة
      </label>

      <button
        type="button"
        className="btn-primary"
        disabled={pending}
        onClick={handleGenerate}
      >
        {pending ? "جاري التوليد…" : "توليد 3 ريلز تجريبية"}
      </button>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {fingerprintMismatch ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
          <p className="font-medium">Fingerprint mismatch</p>
          <p className="mt-1">
            This three-reel result no longer represents the current production course context.
          </p>
          {result?.context_mismatch_fields?.length ? (
            <p className="mt-1 text-xs">
              Changed context: {result.context_mismatch_fields.join(", ")}.
            </p>
          ) : null}
        </div>
      ) : null}

      {result ? (
        <div className="space-y-4 pt-2">
          <p className="text-xs text-muted">
            Job #{result.job.id} · {result.job.status} ·{" "}
            {result.job.estimated_usage_summary || "—"}
          </p>
          {result.limitations.length > 0 ? (
            <div className="rounded-lg border border-border bg-surface-muted/40 p-3 text-xs text-muted">
              <p className="font-medium text-foreground">Writer Test limitations</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {result.limitations.map((limitation) => (
                  <li key={limitation}>{limitation}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {result.reels.map((reel) => (
            <article
              key={reel.reel_id}
              className="rounded-xl border border-[var(--border)] p-3 space-y-2"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="font-medium">{reel.title}</h4>
                <span
                  className={
                    reel.quality_status === "pass"
                      ? "text-emerald-700 text-sm"
                      : "text-red-700 text-sm"
                  }
                >
                  {reel.quality_status === "pass" ? "Pass" : "Fail"}
                </span>
              </div>
              {reel.is_final_master && reel.script_text ? (
                <pre className="whitespace-pre-wrap text-sm leading-relaxed font-[inherit]">
                  {reel.script_text}
                </pre>
              ) : (
                <p className="text-sm text-muted">
                  لم يُعرض كنص Final Master — أعد محاولة هذا الريل فقط.
                </p>
              )}
              <p className="text-xs text-muted">
                {reel.word_count} كلمة · ~{Math.round(reel.estimated_seconds)}ث · توكن{" "}
                {reel.input_tokens + reel.output_tokens}
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-ghost text-sm"
                  onClick={() =>
                    setOpenReport(openReport === reel.reel_id ? null : reel.reel_id)
                  }
                >
                  تقرير الجودة
                </button>
                {reel.quality_status !== "pass" ? (
                  <button
                    type="button"
                    className="btn-secondary text-sm"
                    disabled={pending}
                    onClick={() => handleRetry(reel)}
                  >
                    إعادة محاولة هذا الريل
                  </button>
                ) : null}
              </div>
              {openReport === reel.reel_id ? (
                <p className="text-xs rounded-lg bg-black/5 p-2">
                  {reel.quality_summary || "لا ملاحظات جوهرية"}
                </p>
              ) : null}
            </article>
          ))}
          {(result.job.output_docx_path || result.job.partial_docx_path) && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                const name = `writer_test_${courseId}.docx`;
                if (result.job.output_docx_path) {
                  void api.downloadLatestDocx(courseId, name);
                } else if (result.job.partial_docx_path) {
                  void api.downloadPartialDocx(courseId, result.job.id, name);
                }
              }}
            >
              تحميل DOCX للريلز الثلاثة
            </button>
          )}
        </div>
      ) : null}
    </section>
  );
}
