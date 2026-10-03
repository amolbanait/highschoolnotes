"use client";

import { useState } from "react";

import { Markdown } from "@/components/Markdown";
import { SourceRefs } from "@/components/SourcePanel";
import { Badge, Button, ErrorMessage, inputClass } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { QUESTION_TYPES } from "@/lib/labels";
import type { Question, QuizResult } from "@/lib/types";

/** Practice questions. Multiple choice is graded by the API; open answers are self-checked. */
export function Quiz({ guideId, questions }: { guideId: string; questions: Question[] }) {
  const [results, setResults] = useState<Record<string, QuizResult & { selfCorrect?: boolean }>>({});
  const graded = Object.values(results).filter((r) => r.is_correct !== null || r.selfCorrect !== undefined);
  const correct = graded.filter((r) => r.is_correct ?? r.selfCorrect).length;

  if (questions.length === 0) {
    return <p className="text-slate-600">This guide has no practice questions yet.</p>;
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-600" aria-live="polite">
        {graded.length === 0
          ? `${questions.length} questions. Answer each one, then check it.`
          : `${correct} of ${graded.length} right so far · ${questions.length - Object.keys(results).length} left`}
      </p>
      {questions.map((q, i) => (
        <QuestionCard
          key={q.id}
          guideId={guideId}
          number={i + 1}
          question={q}
          result={results[q.id]}
          onResult={(r) => setResults((prev) => ({ ...prev, [q.id]: { ...prev[q.id], ...r } }))}
        />
      ))}
    </div>
  );
}

function QuestionCard({
  guideId,
  number,
  question,
  result,
  onResult,
}: {
  guideId: string;
  number: number;
  question: Question;
  result?: QuizResult & { selfCorrect?: boolean };
  onResult: (r: Partial<QuizResult & { selfCorrect?: boolean }>) => void;
}) {
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isChoice = question.options.length > 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      onResult(await api.answerQuestion(guideId, question.id, answer));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not check your answer.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm font-semibold text-indigo-700">Question {number}</span>
        <Badge>{QUESTION_TYPES[question.type] ?? question.type}</Badge>
      </div>
      <div className="text-lg font-medium text-slate-900">
        <Markdown>{question.prompt}</Markdown>
      </div>

      <form onSubmit={submit} className="mt-4 space-y-3">
        {isChoice ? (
          <fieldset className="space-y-2" disabled={!!result}>
            <legend className="sr-only">Choose one answer</legend>
            {question.options.map((opt) => {
              const picked = answer === opt;
              const isAnswer = result && opt === result.correct_answer;
              const wrongPick = result && picked && !isAnswer;
              return (
                <label
                  key={opt}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 ${
                    isAnswer
                      ? "border-emerald-400 bg-emerald-50"
                      : wrongPick
                        ? "border-rose-300 bg-rose-50"
                        : picked
                          ? "border-indigo-400 bg-indigo-50"
                          : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name={question.id}
                    value={opt}
                    checked={picked}
                    onChange={() => setAnswer(opt)}
                    className="mt-1 accent-indigo-600"
                  />
                  <span>
                    <Markdown inline>{opt}</Markdown>
                  </span>
                </label>
              );
            })}
          </fieldset>
        ) : (
          <textarea
            aria-label="Your answer"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            disabled={!!result}
            rows={3}
            placeholder="Write your answer in your own words"
            className={inputClass}
          />
        )}
        <ErrorMessage>{error}</ErrorMessage>
        {!result && (
          <Button type="submit" disabled={busy || !answer.trim()}>
            {busy ? "Checking…" : "Check answer"}
          </Button>
        )}
      </form>

      {result && (
        <div className="mt-4 rounded-xl bg-slate-50 p-4">
          {result.is_correct === true && <p className="font-semibold text-emerald-700">Correct!</p>}
          {result.is_correct === false && (
            <p className="font-semibold text-rose-700">
              Not quite. The answer is: <Markdown inline>{result.correct_answer}</Markdown>
            </p>
          )}
          {result.is_correct === null && (
            <>
              <p className="font-semibold text-slate-900">Compare with a good answer:</p>
              <div className="mt-1">
                <Markdown>{result.correct_answer}</Markdown>
              </div>
            </>
          )}
          <div className="mt-2 text-slate-700">
            <Markdown>{result.explanation}</Markdown>
          </div>
          <SourceRefs refs={result.source_refs} className="mt-2" />
          {result.is_correct === null && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-600">Did you get it?</span>
              <Button
                variant={result.selfCorrect === true ? "primary" : "secondary"}
                type="button"
                onClick={() => onResult({ selfCorrect: true })}
              >
                Yes
              </Button>
              <Button
                variant={result.selfCorrect === false ? "primary" : "secondary"}
                type="button"
                onClick={() => onResult({ selfCorrect: false })}
              >
                Not yet
              </Button>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
