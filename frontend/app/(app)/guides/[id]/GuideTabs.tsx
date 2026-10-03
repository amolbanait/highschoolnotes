"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui";
import { levelLabel } from "@/lib/labels";
import type { Guide } from "@/lib/types";

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
      <h1 className="mt-2 text-3xl font-bold text-slate-900">{content?.title || guide.title}</h1>
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
