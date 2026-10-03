"use client";

import { Flashcards } from "@/components/Flashcards";
import { Quiz } from "@/components/Quiz";
import { SourceProvider } from "@/components/SourcePanel";
import { ButtonLink, ErrorMessage } from "@/components/ui";
import { useGuide } from "@/lib/useGuide";

import { GuideHeader } from "./GuideTabs";

export function PracticeScreen({ id, mode }: { id: string; mode: "quiz" | "flashcards" }) {
  const { guide, error } = useGuide(id);
  if (error) return <ErrorMessage>{error}</ErrorMessage>;
  if (!guide) return <div className="h-64 animate-pulse rounded-2xl bg-slate-100" />;
  if (guide.status !== "ready") {
    return (
      <div className="text-center">
        <p className="text-slate-600">Practice opens when the guide is finished.</p>
        <ButtonLink href={`/guides/${id}`} variant="secondary" className="mt-4">
          Back to the guide
        </ButtonLink>
      </div>
    );
  }
  return (
    <SourceProvider guideId={id}>
      <GuideHeader guide={guide} />
      <div className="mx-auto max-w-3xl">
        {mode === "quiz" ? (
          <Quiz guideId={id} questions={guide.content?.questions ?? []} />
        ) : (
          <Flashcards guideId={id} cards={guide.content?.flashcards ?? []} />
        )}
      </div>
    </SourceProvider>
  );
}
