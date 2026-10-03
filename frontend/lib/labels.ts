import type { Level } from "@/lib/types";

export const LEVELS: { value: Level; label: string }[] = [
  { value: "middle_school", label: "Middle school" },
  { value: "high_school", label: "High school" },
  { value: "honors", label: "Honors" },
  { value: "ap", label: "AP" },
  { value: "college_intro", label: "Intro college" },
];

export function levelLabel(level: string): string {
  return LEVELS.find((l) => l.value === level)?.label ?? level;
}

/** Pipeline stages in order, as the worker names them, with what the student sees. */
export const STAGES: { key: string; label: string }[] = [
  { key: "queued", label: "Waiting to start" },
  { key: "plan", label: "Reading your material and finding the main ideas" },
  { key: "sequence", label: "Putting the ideas in a good learning order" },
  { key: "write_sections", label: "Writing explanations and examples" },
  { key: "assemble", label: "Adding the overview and summary" },
  { key: "practice", label: "Making practice questions and flashcards" },
  { key: "check", label: "Checking facts against your material" },
];

export const QUESTION_TYPES: Record<string, string> = {
  recall: "Recall",
  understanding: "Understanding",
  application: "Apply it",
  comparison: "Compare",
  scenario: "Scenario",
  test_style: "Test style",
};

export const FACT_KINDS: Record<string, string> = {
  definition: "Definition",
  date: "Date",
  name: "Name",
  event: "Event",
  number: "Number",
  rule: "Rule",
  exception: "Exception",
  cause_effect: "Cause and effect",
  comparison: "Comparison",
  other: "Fact",
};

/**
 * A citation like "p12-s3" as a student reads it. Guides built from several sources prefix
 * the source number: "d2-p12-s3". Non-paged sources (Word, text, paste) use "s7".
 */
export function refLabel(ref: string): string {
  let rest = ref;
  let doc = "";
  const multi = /^d(\d+)-(.+)$/.exec(ref);
  if (multi) {
    doc = `Source ${multi[1]}, `;
    rest = multi[2];
  }
  const paged = /^p(\d+)-s\d+$/.exec(rest);
  if (paged) return `${doc}p. ${paged[1]}`;
  const flowing = /^s(\d+)$/.exec(rest);
  if (flowing) return `${doc}part ${flowing[1]}`;
  return ref;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}
