"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { GuideView } from "@/components/GuideView";
import { ProgressStream } from "@/components/ProgressStream";
import { SourceProvider } from "@/components/SourcePanel";
import { Button, ButtonLink, ErrorMessage } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Concept, Guide, Level, Source } from "@/lib/types";
import { useGuide } from "@/lib/useGuide";
import { useGuideEvents, useJobEvents } from "@/lib/useGuideEvents";

import { GuideHeader } from "./GuideTabs";

export function GuideScreen({ id }: { id: string }) {
  const { guide, error, reload } = useGuide(id);
  const inProgress = guide?.status === "queued" || guide?.status === "running";
  const progress = useGuideEvents(id, inProgress, reload);

  if (error) {
    return (
      <div className="space-y-4">
        <ErrorMessage>{error}</ErrorMessage>
        <ButtonLink href="/" variant="secondary">
          Back to your guides
        </ButtonLink>
      </div>
    );
  }
  if (!guide) return <div className="h-64 animate-pulse rounded-2xl bg-slate-100" />;

  const partial = guide.content && (guide.content.concepts?.length ?? 0) > 0;
  return (
    <SourceProvider guideId={id}>
      <GuideHeader guide={guide} />
      {inProgress && (
        <div className="mb-8">
          <ProgressStream progress={progress} fallbackStage={guide.progress?.stage} />
        </div>
      )}
      {guide.status === "failed" && <FailedGuide guide={guide} failure={progress.failed} />}
      {guide.status === "ready" && guide.content && <ReadyGuide guide={guide} reload={reload} />}
      {inProgress && partial && guide.content && (
        <>
          <p className="mb-4 text-sm font-medium text-slate-500">Sections ready so far</p>
          <GuideView content={guide.content} />
        </>
      )}
    </SourceProvider>
  );
}

function ReadyGuide({ guide, reload }: { guide: Guide; reload: () => Promise<void> }) {
  const [rewriting, setRewriting] = useState<{ sectionId: string; jobId: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlers = useMemo(
    () => ({
      onDone: () => {
        setRewriting(null);
        reload();
      },
      onFailed: (message: string) => {
        setRewriting(null);
        setError(message);
      },
    }),
    [reload],
  );
  useJobEvents(guide.id, rewriting?.jobId ?? null, handlers);

  async function simplify(concept: Concept) {
    setError(null);
    try {
      const { job_id } = await api.regenerateSection(guide.id, concept.id, "simpler");
      setRewriting({ sectionId: concept.id, jobId: job_id });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not rewrite this section.");
    }
  }

  return (
    <>
      {error && (
        <div className="mb-6">
          <ErrorMessage>{error}</ErrorMessage>
        </div>
      )}
      <GuideView
        content={guide.content!}
        conceptActions={(c) => (
          <Button
            variant="secondary"
            onClick={() => simplify(c)}
            disabled={rewriting !== null}
            title="Rewrite this section in simpler words"
          >
            {rewriting?.sectionId === c.id ? "Rewriting in simpler words…" : "Explain this more simply"}
          </Button>
        )}
      />
      <div className="mt-10 rounded-2xl bg-indigo-600 p-8 text-center text-white">
        <p className="text-xl font-semibold">Ready to test yourself?</p>
        <div className="mt-4 flex flex-wrap justify-center gap-3">
          <ButtonLink href={`/guides/${guide.id}/quiz`} variant="secondary">
            Take the quiz
          </ButtonLink>
          <ButtonLink href={`/guides/${guide.id}/flashcards`} variant="secondary">
            Study flashcards
          </ButtonLink>
        </div>
      </div>
    </>
  );
}

function FailedGuide({ guide, failure }: { guide: Guide; failure: { message?: string } | null }) {
  const router = useRouter();
  const [sources, setSources] = useState<Source[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listSources()
      .then((all) => setSources(all.filter((s) => guide.source_ids.includes(s.id))))
      .catch(() => undefined);
  }, [guide.source_ids]);

  const unreadable = sources.filter((s) => s.status === "failed");
  const message = failure?.message ?? guide.error?.message ?? "Something went wrong while making this guide.";

  async function retry() {
    setBusy(true);
    setError(null);
    try {
      const { guide_id } = await api.createGuide(guide.source_ids, guide.level as Level);
      router.push(`/guides/${guide_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start again.");
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-rose-200 bg-rose-50 p-6">
      <h2 className="text-lg font-semibold text-rose-900">This guide couldn&apos;t be made</h2>
      <p className="mt-1 text-rose-800">{message}</p>
      {unreadable.length > 0 && (
        <ul className="mt-3 list-disc pl-5 text-sm text-rose-800">
          {unreadable.map((s) => (
            <li key={s.id}>
              <span className="font-medium">{s.title}:</span>{" "}
              {String(s.error?.message ?? "could not be read.")}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-5 flex flex-wrap gap-3">
        {unreadable.length === 0 && (
          <Button onClick={retry} disabled={busy}>
            {busy ? "Starting…" : "Try again"}
          </Button>
        )}
        <ButtonLink href="/new" variant="secondary">
          Use different material
        </ButtonLink>
      </div>
      {error && (
        <div className="mt-3">
          <ErrorMessage>{error}</ErrorMessage>
        </div>
      )}
    </section>
  );
}
