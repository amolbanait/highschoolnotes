"use client";

import { useState } from "react";

import { Diagram } from "@/components/Diagram";
import { Markdown } from "@/components/Markdown";
import { SourceRefs } from "@/components/SourcePanel";
import { Badge } from "@/components/ui";
import type { Concept, Example } from "@/lib/types";

const DIFFICULTY = {
  easy: { label: "Easier", tone: "emerald" },
  medium: { label: "Medium", tone: "amber" },
  hard: { label: "Challenging", tone: "rose" },
} as const;

export function ConceptCard({
  concept,
  number,
  prerequisiteTitles,
  actions,
}: {
  concept: Concept;
  number: number;
  prerequisiteTitles: string[];
  actions?: React.ReactNode;
}) {
  const difficulty = DIFFICULTY[concept.difficulty];
  return (
    <article
      id={concept.id}
      className="scroll-mt-24 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
    >
      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-indigo-700">Concept {number}</span>
          <Badge tone={difficulty.tone}>{difficulty.label}</Badge>
          {concept.teacher_emphasis && (
            <Badge tone="violet" title="Your material stresses this">
              Teacher emphasis
            </Badge>
          )}
          {concept.likely_on_test && <Badge tone="indigo">Likely on the test</Badge>}
        </div>
        <h2 className="mt-2 text-2xl font-bold text-slate-900">{concept.title}</h2>
        {prerequisiteTitles.length > 0 && (
          <p className="mt-1 text-sm text-slate-500">Builds on: {prerequisiteTitles.join(", ")}</p>
        )}
      </header>

      <Markdown>{concept.concept}</Markdown>
      <SourceRefs refs={concept.source_refs} className="mt-2" />

      {concept.levels && (
        <Section title="Explain it three ways">
          <LevelTabs levels={concept.levels} />
        </Section>
      )}

      <Section title="Why it matters">
        <Markdown>{concept.why_it_matters}</Markdown>
      </Section>

      {concept.how_it_works.length > 0 && (
        <Section title="How it works">
          <ol className="list-decimal space-y-2 pl-6 marker:font-semibold marker:text-indigo-600">
            {concept.how_it_works.map((step, i) => (
              <li key={i} className="pl-1">
                <Markdown inline>{step}</Markdown>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {concept.diagram && concept.diagram.type !== "none" && concept.diagram.mermaid && (
        <Diagram diagram={concept.diagram} />
      )}

      {concept.examples.length > 0 && (
        <Section title={concept.examples.length > 1 ? "Examples" : "Example"}>
          <ul className="space-y-3">
            {concept.examples.map((ex, i) => (
              <ExampleItem key={i} example={ex} />
            ))}
          </ul>
        </Section>
      )}

      {concept.analogy && (
        <Section title="Think of it like this">
          <div className="rounded-xl bg-sky-50 p-4">
            <Markdown>{concept.analogy.text}</Markdown>
            {concept.analogy.origin === "ai_generated" && <AiLabel />}
          </div>
        </Section>
      )}

      {concept.common_mistake && (
        <Section title="Common mistake">
          <div className="rounded-xl border-l-4 border-amber-400 bg-amber-50 p-4">
            <Markdown>{concept.common_mistake}</Markdown>
          </div>
        </Section>
      )}

      {concept.quick_check.length > 0 && (
        <Section title="Quick check">
          <ul className="space-y-3">
            {concept.quick_check.map((qc, i) => (
              <QuickCheckItem key={i} q={qc.q} a={qc.a} />
            ))}
          </ul>
        </Section>
      )}

      {actions && (
        <footer className="mt-6 flex flex-wrap gap-2 border-t border-slate-100 pt-4">{actions}</footer>
      )}
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </section>
  );
}

function AiLabel() {
  return (
    <p
      className="mt-2 text-xs text-slate-500"
      title="Not from your material. Written by the AI to help explain."
    >
      ✦ AI-written to help explain; not from your material
    </p>
  );
}

function ExampleItem({ example }: { example: Example }) {
  const fromSource = example.origin === "source";
  return (
    <li className={`rounded-xl p-4 ${fromSource ? "bg-emerald-50" : "bg-slate-50"}`}>
      <Markdown>{example.text}</Markdown>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {fromSource ? (
          <>
            <span className="text-xs font-medium text-emerald-800">From your material</span>
            <SourceRefs refs={example.source_refs} />
          </>
        ) : (
          <span className="text-xs text-slate-500">✦ AI-written example</span>
        )}
      </div>
    </li>
  );
}

function QuickCheckItem({ q, a }: { q: string; a: string }) {
  const [shown, setShown] = useState(false);
  return (
    <li className="rounded-xl border border-slate-200 p-4">
      <div className="font-medium text-slate-900">
        <Markdown inline>{q}</Markdown>
      </div>
      {shown ? (
        <div className="mt-2 text-slate-700">
          <Markdown>{a}</Markdown>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShown(true)}
          className="mt-2 text-sm font-medium text-indigo-700 hover:underline"
        >
          Show answer
        </button>
      )}
    </li>
  );
}

const LEVEL_TABS = [
  { key: "new", label: "Explain like I'm new" },
  { key: "understand", label: "Understand it" },
  { key: "deeper", label: "Go deeper" },
] as const;

export function LevelTabs({ levels }: { levels: NonNullable<Concept["levels"]> }) {
  const [active, setActive] = useState<(typeof LEVEL_TABS)[number]["key"]>("understand");
  return (
    <div>
      <div
        role="tablist"
        aria-label="Explanation level"
        className="mb-3 inline-flex flex-wrap rounded-lg bg-slate-100 p-1"
      >
        {LEVEL_TABS.map((tab, i) => (
          <button
            key={tab.key}
            role="tab"
            type="button"
            aria-selected={active === tab.key}
            onClick={() => setActive(tab.key)}
            className={`rounded-md px-3 py-1.5 text-sm ${active === tab.key ? "bg-white font-medium text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
          >
            <span className="text-slate-400">{i + 1}.</span> {tab.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        <Markdown>{levels[active]}</Markdown>
      </div>
    </div>
  );
}
