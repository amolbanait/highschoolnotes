"use client";

import { ButtonLink, ErrorMessage } from "@/components/ui";
import { useGuide } from "@/lib/useGuide";

import { ExportMenu } from "../GuideTabs";
import { PrintableGuide } from "./PrintableGuide";

/** The whole guide opened up on one page, for the browser's Print (or Save as PDF). */
export function PrintScreen({ id }: { id: string }) {
  const { guide, error } = useGuide(id);
  if (error) return <ErrorMessage>{error}</ErrorMessage>;
  if (!guide) return <div className="h-64 animate-pulse rounded-2xl bg-slate-100" />;
  if (guide.status !== "ready" || !guide.content) {
    return (
      <div className="text-center">
        <p className="text-slate-600">The printable view opens when the guide is finished.</p>
        <ButtonLink href={`/guides/${id}`} variant="secondary" className="mt-4">
          Back to the guide
        </ButtonLink>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
        <ButtonLink href={`/guides/${id}`} variant="ghost">
          ← Back to the guide
        </ButtonLink>
        <div className="flex gap-2">
          <ExportMenu guideId={id} />
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Print
          </button>
        </div>
      </div>
      <PrintableGuide content={guide.content} level={guide.level} />
    </div>
  );
}
