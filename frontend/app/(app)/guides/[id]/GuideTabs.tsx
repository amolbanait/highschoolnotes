"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui";
import { api } from "@/lib/api";
import { levelLabel } from "@/lib/labels";
import type { ExportFormat, Guide } from "@/lib/types";

const DOWNLOADS: { format: ExportFormat; label: string; hint: string }[] = [
  { format: "pdf", label: "PDF", hint: "Print or read anywhere" },
  { format: "docx", label: "Word (.docx)", hint: "Edit and add your own notes" },
  { format: "md", label: "Markdown", hint: "For notes apps like Obsidian or Notion" },
  { format: "html", label: "Web page (.html)", hint: "Opens in any browser, even offline" },
];

/** Title, level and the Guide / Quiz / Flashcards switcher shared by the three guide pages. */
export function GuideHeader({ guide }: { guide: Guide }) {
  const pathname = usePathname();
  const base = `/guides/${guide.id}`;
  const content = guide.content;
  const tabs = [
    { href: base, label: "Study guide" },
    {
      href: `${base}/quiz`,
      label: `Quiz${content?.questions?.length ? ` (${content.questions.length})` : ""}`,
    },
    {
      href: `${base}/flashcards`,
      label: `Flashcards${content?.flashcards?.length ? ` (${content.flashcards.length})` : ""}`,
    },
  ];
  const ready = guide.status === "ready";
  return (
    <header className="mb-8">
      <Link href="/" className="text-sm text-slate-500 hover:text-slate-800">
        ← All guides
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-3xl font-bold text-slate-900">{content?.title || guide.title}</h1>
        {ready && <ExportMenu guideId={guide.id} />}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-600">
        <Badge tone="indigo">{levelLabel(guide.level)}</Badge>
        {content?.topics?.length ? <span>{content.topics.join(" · ")}</span> : null}
      </div>
      {ready && (
        <nav className="mt-6 flex gap-1 border-b border-slate-200">
          {tabs.map((t) => {
            const active = pathname === t.href;
            return (
              <Link
                key={t.href}
                href={t.href}
                aria-current={active ? "page" : undefined}
                className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
                  active
                    ? "border-indigo-600 text-indigo-700"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
}

/** Download the guide as a file, or open the printable view. */
export function ExportMenu({ guideId }: { guideId: string }) {
  return (
    <details className="group relative">
      <summary className="inline-flex cursor-pointer list-none items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 [&::-webkit-details-marker]:hidden">
        Download or print <span aria-hidden>▾</span>
      </summary>
      <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
        <ul>
          {DOWNLOADS.map((d) => (
            <li key={d.format}>
              <a
                href={api.exportUrl(guideId, d.format)}
                download
                className="block rounded-lg px-3 py-2 hover:bg-slate-50"
              >
                <span className="block text-sm font-medium text-slate-900">{d.label}</span>
                <span className="block text-xs text-slate-500">{d.hint}</span>
              </a>
            </li>
          ))}
          <li className="mt-1 border-t border-slate-100 pt-1">
            <Link href={`/guides/${guideId}/print`} className="block rounded-lg px-3 py-2 hover:bg-slate-50">
              <span className="block text-sm font-medium text-slate-900">Printable view</span>
              <span className="block text-xs text-slate-500">Everything opened up, ready to print</span>
            </Link>
          </li>
        </ul>
      </div>
    </details>
  );
}
