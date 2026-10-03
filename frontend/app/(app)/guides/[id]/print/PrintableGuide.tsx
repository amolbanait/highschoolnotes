import { GuideView } from "@/components/GuideView";
import { Markdown } from "@/components/Markdown";
import { SourceRefs } from "@/components/SourcePanel";
import { levelLabel, QUESTION_TYPES } from "@/lib/labels";
import type { StudyGuideContent } from "@/lib/types";

const LETTERS = "ABCDEFGHIJ";

/** The study guide with practice questions, a separate answer key and flashcards, for printing. */
export function PrintableGuide({ content, level }: { content: StudyGuideContent; level: string }) {
  const questions = content.questions ?? [];
  const flashcards = content.flashcards ?? [];
  return (
    <article className="text-slate-800">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-slate-900">{content.title}</h1>
        <p className="mt-1 text-sm text-slate-500">
          Level: {levelLabel(level)}
          {content.topics?.length ? ` · ${content.topics.join(" · ")}` : ""}
        </p>
      </header>

      <GuideView content={content} printable />

      {questions.length > 0 && (
        <section className="mt-10 print:break-before-page">
          <h2 className="mb-4 text-xl font-bold text-slate-900">Practice questions</h2>
          <ol className="list-decimal space-y-4 pl-6">
            {questions.map((q) => (
              <li key={q.id} className="print:break-inside-avoid">
                <span className="mr-2 text-xs font-semibold uppercase text-slate-500">
                  {QUESTION_TYPES[q.type] ?? q.type}
                </span>
                <Markdown inline>{q.prompt}</Markdown>
                {q.options.length > 0 && (
                  <ol className="mt-1 space-y-0.5 pl-2">
                    {q.options.map((o, i) => (
                      <li key={i}>
                        {LETTERS[i]}. <Markdown inline>{o}</Markdown>
                      </li>
                    ))}
                  </ol>
                )}
              </li>
            ))}
          </ol>

          <h2 className="mb-4 mt-10 text-xl font-bold text-slate-900 print:break-before-page">Answer key</h2>
          <ol className="list-decimal space-y-3 pl-6">
            {questions.map((q) => {
              const index = q.options.indexOf(q.answer);
              return (
                <li key={q.id} className="print:break-inside-avoid">
                  <strong>
                    {index >= 0 ? `${LETTERS[index]}. ` : ""}
                    <Markdown inline>{q.answer}</Markdown>
                  </strong>{" "}
                  <Markdown inline>{q.explanation}</Markdown> <SourceRefs refs={q.source_refs} />
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {flashcards.length > 0 && (
        <section className="mt-10">
          <h2 className="mb-4 text-xl font-bold text-slate-900">Flashcards</h2>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="border border-slate-200 px-3 py-2 font-medium">Front</th>
                <th className="border border-slate-200 px-3 py-2 font-medium">Back</th>
              </tr>
            </thead>
            <tbody>
              {flashcards.map((card) => (
                <tr key={card.id} className="align-top print:break-inside-avoid">
                  <td className="border border-slate-200 px-3 py-2 font-medium">
                    <Markdown inline>{card.front}</Markdown>
                  </td>
                  <td className="border border-slate-200 px-3 py-2">
                    <Markdown inline>{card.back}</Markdown>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <p className="mt-10 border-t border-slate-200 pt-3 text-xs text-slate-500">
        Made with HighSchoolNotes. Facts come from your material and cite where they are; examples and
        analogies marked as AI-written were added to help explain.
      </p>
    </article>
  );
}
