"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Badge, Button, ButtonLink, ErrorMessage } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDate, levelLabel } from "@/lib/labels";
import type { GuideSummary } from "@/lib/types";

const STATUS: Record<string, { label: string; tone: "slate" | "indigo" | "emerald" | "rose" }> = {
  queued: { label: "Starting", tone: "indigo" },
  running: { label: "Being made", tone: "indigo" },
  ready: { label: "Ready", tone: "emerald" },
  failed: { label: "Didn't work", tone: "rose" },
};

export default function HomePage() {
  const [guides, setGuides] = useState<GuideSummary[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (from?: string) => {
    try {
      const page = await api.listGuides(from);
      setGuides((prev) => (from && prev ? [...prev, ...page.items] : page.items));
      setCursor(page.next_cursor);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load your guides.");
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading on mount
    load();
  }, [load]);

  async function remove(g: GuideSummary) {
    if (!confirm(`Delete "${g.title}"? This can't be undone.`)) return;
    try {
      await api.deleteGuide(g.id);
      setGuides((prev) => prev?.filter((x) => x.id !== g.id) ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete the guide.");
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Your study guides</h1>
          <p className="mt-1 text-slate-600">
            Add class material and get a guide, practice questions and flashcards.
          </p>
        </div>
        <ButtonLink href="/new">+ New study guide</ButtonLink>
      </div>

      <div className="mt-8">
        <ErrorMessage>{error}</ErrorMessage>
        {guides === null && !error && <div className="h-40 animate-pulse rounded-2xl bg-slate-100" />}
        {guides?.length === 0 && (
          <div className="rounded-2xl border-2 border-dashed border-slate-300 bg-white p-12 text-center">
            <p className="text-lg font-medium text-slate-900">No study guides yet</p>
            <p className="mt-1 text-slate-600">
              Upload a PDF, Word file or text, or paste your notes, to make your first one.
            </p>
            <ButtonLink href="/new" className="mt-5">
              Make my first guide
            </ButtonLink>
          </div>
        )}
        {guides && guides.length > 0 && (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {guides.map((g) => {
              const status = STATUS[g.status] ?? { label: g.status, tone: "slate" as const };
              return (
                <li
                  key={g.id}
                  className="group relative flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:border-indigo-300"
                >
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone={status.tone}>{status.label}</Badge>
                    <span className="text-xs text-slate-500">{formatDate(g.created_at)}</span>
                  </div>
                  <Link
                    href={`/guides/${g.id}`}
                    className="mt-3 text-lg font-semibold text-slate-900 after:absolute after:inset-0"
                  >
                    {g.title}
                  </Link>
                  <p className="mt-1 text-sm text-slate-500">{levelLabel(g.level)}</p>
                  <div className="relative z-10 mt-4 flex gap-3 text-sm">
                    {g.status === "ready" && (
                      <>
                        <Link
                          href={`/guides/${g.id}/quiz`}
                          className="font-medium text-indigo-700 hover:underline"
                        >
                          Quiz
                        </Link>
                        <Link
                          href={`/guides/${g.id}/flashcards`}
                          className="font-medium text-indigo-700 hover:underline"
                        >
                          Flashcards
                        </Link>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={() => remove(g)}
                      className="ml-auto text-slate-400 hover:text-rose-700"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {cursor && (
          <div className="mt-6 text-center">
            <Button variant="secondary" onClick={() => load(cursor)}>
              Show more
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
