"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { refLabel } from "@/lib/labels";
import type { GuideRef } from "@/lib/types";

type Ctx = { open: (ref: string) => void };
const SourceContext = createContext<Ctx | null>(null);

/** Holds the "view in source" side panel for one guide; SourceRefs anywhere inside can open it. */
export function SourceProvider({ guideId, children }: { guideId: string; children: React.ReactNode }) {
  const [ref, setRef] = useState<string | null>(null);
  const open = useCallback((r: string) => setRef(r), []);
  return (
    <SourceContext.Provider value={{ open }}>
      {children}
      {ref && <SourcePanel key={ref} guideId={guideId} refId={ref} onClose={() => setRef(null)} />}
    </SourceContext.Provider>
  );
}

/** Citation chips: "p. 12", "part 3". Clicking one shows the exact source text. */
export function SourceRefs({ refs, className = "" }: { refs?: string[]; className?: string }) {
  const ctx = useContext(SourceContext);
  if (!refs?.length) return null;
  const unique = [...new Set(refs)];
  if (!ctx) {
    // Outside a guide page (e.g. the print view) citations are plain text.
    return (
      <span className={`text-xs text-slate-500 ${className}`}>
        (Source: {unique.map(refLabel).join(", ")})
      </span>
    );
  }
  return (
    <span className={`inline-flex flex-wrap items-center gap-1 align-middle ${className}`}>
      {unique.map((r) => (
        <button
          key={r}
          type="button"
          onClick={() => ctx?.open(r)}
          title="Show where this comes from in your material"
          className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-xs text-slate-600 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
        >
          {refLabel(r)}
        </button>
      ))}
    </span>
  );
}

function SourcePanel({ guideId, refId, onClose }: { guideId: string; refId: string; onClose: () => void }) {
  const [data, setData] = useState<GuideRef | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .resolveRef(guideId, refId)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : "Could not load the source."));
    return () => {
      cancelled = true;
    };
  }, [guideId, refId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const headings = (data?.heading_path ?? []).filter((h): h is string => typeof h === "string");
  return (
    <aside
      role="dialog"
      aria-label="From your material"
      className="fixed inset-x-0 bottom-0 z-40 max-h-[60vh] overflow-y-auto border-t border-slate-200 bg-white p-5 shadow-2xl md:inset-x-auto md:inset-y-0 md:right-0 md:max-h-none md:w-[28rem] md:border-l md:border-t-0"
    >
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">From your material</p>
          <p className="text-sm text-slate-600">{refLabel(refId)}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-slate-500 hover:bg-slate-100"
          aria-label="Close"
        >
          ✕
        </button>
      </div>
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {!data && !error && <div className="h-40 animate-pulse rounded bg-slate-100" />}
      {data && (
        <>
          {headings.length > 0 && <p className="mb-2 text-xs text-slate-500">{headings.join(" › ")}</p>}
          <blockquote className="whitespace-pre-wrap border-l-4 border-indigo-200 pl-4 text-sm leading-relaxed text-slate-800">
            {data.text}
          </blockquote>
        </>
      )}
    </aside>
  );
}
