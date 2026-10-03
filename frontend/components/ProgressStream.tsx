import { STAGES } from "@/lib/labels";
import type { GuideProgress } from "@/lib/useGuideEvents";

/** The live checklist shown while a guide is being made. */
export function ProgressStream({
  progress,
  fallbackStage,
}: {
  progress: GuideProgress;
  fallbackStage?: string | null;
}) {
  const stage = progress.stage ?? fallbackStage ?? "queued";
  const current = Math.max(
    0,
    STAGES.findIndex((s) => s.key === stage),
  );
  const { topics, readySections } = progress;

  return (
    <section aria-live="polite" className="rounded-2xl border border-indigo-100 bg-indigo-50/50 p-6">
      <h2 className="text-lg font-semibold text-slate-900">Making your study guide</h2>
      <p className="mt-1 text-sm text-slate-600">
        This usually takes a few minutes. You can leave this page and come back; it keeps going.
      </p>
      <ol className="mt-5 space-y-2.5">
        {STAGES.slice(1).map((s, i) => {
          const index = i + 1;
          const state = index < current ? "done" : index === current ? "active" : "todo";
          return (
            <li key={s.key} className="flex items-center gap-3 text-sm">
              <span
                aria-hidden
                className={
                  state === "done"
                    ? "flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-[11px] text-white"
                    : state === "active"
                      ? "h-5 w-5 animate-pulse rounded-full border-2 border-indigo-500 bg-indigo-100"
                      : "h-5 w-5 rounded-full border-2 border-slate-300"
                }
              >
                {state === "done" ? "✓" : ""}
              </span>
              <span
                className={
                  state === "todo"
                    ? "text-slate-400"
                    : state === "active"
                      ? "font-medium text-slate-900"
                      : "text-slate-600"
                }
              >
                {s.label}
                {s.key === "write_sections" && state === "active" && topics.length > 0 && (
                  <span className="text-slate-500">
                    {" "}
                    ({readySections.length} of {topics.length})
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
      {topics.length > 0 && (
        <div className="mt-6">
          <h3 className="text-sm font-semibold text-slate-800">Topics found</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {topics.map((t) => (
              <li
                key={t.id}
                className={`rounded-full px-3 py-1 text-xs ${readySections.includes(t.id) ? "bg-emerald-100 text-emerald-800" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}
              >
                {readySections.includes(t.id) ? "✓ " : ""}
                {t.title}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
