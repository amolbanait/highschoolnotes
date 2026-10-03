"use client";

import { useState } from "react";

import { Markdown } from "@/components/Markdown";
import { SourceRefs } from "@/components/SourcePanel";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import type { Flashcard, FlashcardRating } from "@/lib/types";

/**
 * One card at a time. "Again" puts the card back at the end of this session's deck; every
 * rating is recorded so later phases can schedule reviews.
 */
export function Flashcards({ guideId, cards }: { guideId: string; cards: Flashcard[] }) {
  const [deck, setDeck] = useState(() => cards.map((c) => c.id));
  const [flipped, setFlipped] = useState(false);
  const [known, setKnown] = useState(0);
  const byId = new Map(cards.map((c) => [c.id, c]));

  if (cards.length === 0) return <p className="text-slate-600">This guide has no flashcards yet.</p>;

  const current = deck[0] ? byId.get(deck[0]) : undefined;
  if (!current) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
        <p className="text-xl font-semibold text-emerald-900">Deck done!</p>
        <p className="mt-1 text-emerald-800">You went through all {cards.length} cards.</p>
        <Button
          className="mt-4"
          onClick={() => {
            setDeck(cards.map((c) => c.id));
            setKnown(0);
            setFlipped(false);
          }}
        >
          Go again
        </Button>
      </div>
    );
  }

  function rate(rating: FlashcardRating) {
    if (!current) return;
    api.reviewFlashcard(guideId, current.id, rating).catch(() => undefined); // practice continues offline
    setFlipped(false);
    setDeck((d) => (rating === "again" ? [...d.slice(1), d[0]] : d.slice(1)));
    if (rating !== "again") setKnown((k) => k + 1);
  }

  return (
    <div className="mx-auto max-w-xl">
      <p className="mb-3 text-center text-sm text-slate-600" aria-live="polite">
        {known} of {cards.length} done · {deck.length} to go
      </p>
      <button
        type="button"
        onClick={() => setFlipped((f) => !f)}
        aria-label={flipped ? "Show the question" : "Show the answer"}
        className={`flex min-h-64 w-full flex-col items-center justify-center rounded-2xl border p-8 text-center text-lg shadow-sm transition-colors ${
          flipped ? "border-indigo-200 bg-indigo-50" : "border-slate-200 bg-white hover:bg-slate-50"
        }`}
      >
        <span className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
          {flipped ? "Answer" : "Question"}
        </span>
        <Markdown>{flipped ? current.back : current.front}</Markdown>
        {!flipped && <span className="mt-4 text-sm text-slate-400">Tap to flip</span>}
      </button>
      {flipped && (
        <>
          <div className="mt-2 text-center">
            <SourceRefs refs={current.source_refs} />
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Button variant="secondary" onClick={() => rate("again")}>
              Again
            </Button>
            <Button variant="secondary" onClick={() => rate("good")}>
              Got it
            </Button>
            <Button variant="secondary" onClick={() => rate("easy")}>
              Easy
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
