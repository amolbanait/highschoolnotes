import { ConceptCard } from "@/components/ConceptCard";
import { Formula } from "@/components/Formula";
import { Markdown } from "@/components/Markdown";
import { SourceRefs } from "@/components/SourcePanel";
import { Badge } from "@/components/ui";
import { FACT_KINDS } from "@/lib/labels";
import type { Concept, StudyGuideContent } from "@/lib/types";

type TocItem = { id: string; label: string; child?: boolean };

/** The whole study guide, in the order a student should read it. Works on partial content too. */
export function GuideView({
  content,
  conceptActions,
}: {
  content: StudyGuideContent;
  conceptActions?: (concept: Concept) => React.ReactNode;
}) {
  const concepts = content.concepts ?? [];
  const vocabulary = content.vocabulary ?? [];
  const facts = content.facts ?? [];
  const formulas = content.formulas ?? [];
  const relationships = content.relationships ?? [];
  const objectives = content.objectives ?? [];
  const checklist = content.review_checklist ?? [];
  const notCovered = content.not_covered ?? [];
  const warnings = content.warnings ?? [];

  const byKeyOrId = new Map<string, Concept>();
  for (const c of concepts) {
    byKeyOrId.set(c.key, c);
    byKeyOrId.set(c.id, c);
  }
  const titleOf = (k: string) => byKeyOrId.get(k)?.title ?? k;

  const toc: TocItem[] = [
    ...(content.overview ? [{ id: "overview", label: "What is this about?" }] : []),
    ...(vocabulary.length ? [{ id: "vocabulary", label: "Key vocabulary" }] : []),
    ...concepts.map((c) => ({ id: c.id, label: c.title, child: true })),
    ...(facts.length ? [{ id: "facts", label: "Key facts" }] : []),
    ...(formulas.length ? [{ id: "formulas", label: "Formulas" }] : []),
    ...(relationships.length ? [{ id: "connections", label: "How it connects" }] : []),
    ...(content.summary ? [{ id: "summary", label: "Summary" }] : []),
    ...(checklist.length ? [{ id: "checklist", label: "Review checklist" }] : []),
  ];

  return (
    <div className="lg:grid lg:grid-cols-[14rem_1fr] lg:gap-10">
      <nav aria-label="Contents" className="hidden lg:block">
        <div className="sticky top-24 max-h-[calc(100vh-8rem)] overflow-y-auto">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Contents</p>
          <ul className="space-y-1 text-sm">
            {toc.map((item) => (
              <li key={item.id}>
                <a
                  href={`#${item.id}`}
                  className={`block rounded px-2 py-1 text-slate-600 hover:bg-slate-100 hover:text-slate-900 ${item.child ? "pl-4" : "font-medium"}`}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      <div className="min-w-0 space-y-8">
        {warnings.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <p className="font-medium">Double-check these</p>
            <ul className="mt-1 list-disc pl-5">
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {content.overview && (
          <Card id="overview" title="What is this topic about?">
            <Markdown>{content.overview}</Markdown>
            {objectives.length > 0 && (
              <>
                <h3 className="mb-2 mt-5 font-semibold text-slate-900">By the end, you should be able to:</h3>
                <ul className="list-disc space-y-1 pl-6">
                  {objectives.map((o, i) => (
                    <li key={i}>
                      <Markdown inline>{o}</Markdown>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>
        )}

        {vocabulary.length > 0 && (
          <Card id="vocabulary" title="Key vocabulary">
            <div className="-mx-2 overflow-x-auto">
              <table className="w-full min-w-[36rem] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="px-2 py-2 font-medium">Term</th>
                    <th className="px-2 py-2 font-medium">Simple meaning</th>
                    <th className="px-2 py-2 font-medium">Example</th>
                  </tr>
                </thead>
                <tbody>
                  {vocabulary.map((v) => (
                    <tr key={v.id} className="border-b border-slate-100 align-top last:border-0">
                      <td className="px-2 py-3 font-semibold text-slate-900">{v.term}</td>
                      <td className="px-2 py-3">
                        <Markdown inline>{v.definition}</Markdown> <SourceRefs refs={v.source_refs} />
                      </td>
                      <td className="px-2 py-3 text-slate-600">
                        {v.example && <Markdown inline>{v.example}</Markdown>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {concepts.map((c, i) => (
          <ConceptCard
            key={c.id}
            concept={c}
            number={i + 1}
            prerequisiteTitles={c.prerequisites.map(titleOf)}
            actions={conceptActions?.(c)}
          />
        ))}

        {facts.length > 0 && (
          <Card id="facts" title="Key facts to remember">
            <ul className="space-y-3">
              {facts.map((f) => (
                <li key={f.id} className="rounded-xl bg-slate-50 p-4">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <Badge>{FACT_KINDS[f.kind] ?? "Fact"}</Badge>
                    {f.teacher_emphasis && <Badge tone="violet">Teacher emphasis</Badge>}
                  </div>
                  <Markdown>{f.text}</Markdown>
                  {f.quote && (
                    <p className="mt-2 border-l-2 border-slate-300 pl-3 text-sm italic text-slate-600">
                      “{f.quote}” <SourceRefs refs={f.source_refs} />
                    </p>
                  )}
                  {f.verified === false && <Unverified />}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {formulas.length > 0 && (
          <Card id="formulas" title="Formulas">
            <ul className="space-y-4">
              {formulas.map((f) => (
                <li key={f.id} className="rounded-xl bg-slate-50 p-4">
                  <Formula latex={f.latex} />
                  <Markdown>{f.meaning}</Markdown>
                  <SourceRefs refs={f.source_refs} className="mt-1" />
                  {f.verified === false && <Unverified />}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {relationships.length > 0 && (
          <Card id="connections" title="How the ideas connect">
            <ul className="space-y-3">
              {relationships.map((r, i) => (
                <li key={i} className="rounded-xl border border-slate-200 p-4">
                  <p className="font-medium text-slate-900">
                    {titleOf(r.from)} <span className="px-1 text-indigo-600">→ {r.type} →</span>{" "}
                    {titleOf(r.to)}
                  </p>
                  <div className="mt-1 text-slate-700">
                    <Markdown>{r.explanation}</Markdown>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {content.summary && (
          <Card id="summary" title="Summary">
            <Markdown>{content.summary}</Markdown>
          </Card>
        )}

        {checklist.length > 0 && (
          <Card id="checklist" title="Review checklist">
            <p className="mb-3 text-sm text-slate-600">
              Tick each one you could explain to a friend without notes.
            </p>
            <ul className="space-y-2">
              {checklist.map((item, i) => (
                <li key={i}>
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-slate-300 accent-indigo-600"
                    />
                    <span>{item}</span>
                  </label>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {notCovered.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-700">
            <p className="font-medium text-slate-900">Not clearly covered in your material</p>
            <p className="mt-1 text-slate-600">
              You might expect these here. Check your textbook or ask your teacher.
            </p>
            <ul className="mt-2 list-disc pl-5">
              {notCovered.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function Card({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section
      id={id}
      className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <h2 className="mb-4 text-xl font-bold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

function Unverified() {
  return (
    <p className="mt-2 text-xs text-amber-800">
      ⚠ This couldn&apos;t be matched word for word to your material. Check it before you rely on it.
    </p>
  );
}
