"""The guide as Markdown. Maths stays as $...$ and diagrams as ```mermaid blocks, which most
Markdown apps (GitHub, Obsidian, Notion import) render; each diagram also gets a text version."""

from app.diagrams import mermaid
from app.export.common import (
    AI_ANALOGY,
    AI_EXAMPLE,
    CHECK_THIS,
    CHECK_THIS_BODY,
    DIFFICULTY_LABELS,
    FACT_KINDS,
    FOOTER,
    FROM_SOURCE,
    LEVEL_TABS,
    QUESTION_TYPES,
    UNVERIFIED,
    ExportInfo,
    concept_titles,
)


def _cell(text: str | None) -> str:
    return " ".join((text or "").split()).replace("|", "\\|")


def _quote_block(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.strip().splitlines())


def to_markdown(content: dict, info: ExportInfo) -> str:
    out: list[str] = []
    w = out.append
    titles = concept_titles(content)

    def cite(refs) -> str:
        label = info.cite(refs)
        return f" _{label}_" if label else ""

    w(f"# {content.get('title') or info.title}\n")
    meta = [f"**Level:** {info.level_label}"]
    if info.source_titles:
        meta.append("**From:** " + "; ".join(info.source_titles))
    meta.append(f"**Made:** {info.made_on_label}")
    w(" · ".join(meta) + "\n")

    if content.get("warnings"):
        w("> **Double-check these**")
        w(">")
        out.extend(f"> - {x}" for x in content["warnings"])
        w("")

    if content.get("overview"):
        w("## What is this topic about?\n")
        w(content["overview"].strip() + "\n")
    if content.get("objectives"):
        w("**By the end, you should be able to:**\n")
        out.extend(f"- {o}" for o in content["objectives"])
        w("")

    if content.get("vocabulary"):
        w("## Key vocabulary\n")
        w("| Term | Simple meaning | Example |")
        w("|---|---|---|")
        for v in content["vocabulary"]:
            note = " ⚠ _Not matched to your material._" if v.get("verified") is False else ""
            w(
                f"| **{_cell(v['term'])}** | {_cell(v['definition'])}{_cell(cite(v.get('source_refs')))}{note} "
                f"| {_cell(v.get('example'))} |"
            )
        w("")

    concepts = content.get("concepts", [])
    if concepts:
        w("## Main concepts\n")
    for number, c in enumerate(concepts, start=1):
        tags = [DIFFICULTY_LABELS.get(c["difficulty"], c["difficulty"])]
        if c.get("teacher_emphasis"):
            tags.append("Teacher emphasis")
        if c.get("likely_on_test"):
            tags.append("Likely on the test")
        w(f"### Concept {number}: {c['title']}\n")
        w(f"_{' · '.join(tags)}_")
        if c.get("prerequisites"):
            w(f"_Builds on: {', '.join(titles.get(p, p) for p in c['prerequisites'])}_")
        w("")
        quality = c.get("quality") or {}
        if quality.get("needs_checking"):
            w(f"> ⚠ **{CHECK_THIS}.** {CHECK_THIS_BODY}")
            out.extend(f"> - {p}" for p in quality.get("problems", []))
            w("")
        w(c["concept"].strip() + cite(c.get("source_refs")) + "\n")
        if c.get("levels"):
            w("#### Explain it three ways\n")
            for key, label in LEVEL_TABS:
                w(f"**{label}**\n")
                w(c["levels"].get(key, "").strip() + "\n")
        w("#### Why it matters\n")
        w(c["why_it_matters"].strip() + "\n")
        if c.get("how_it_works"):
            w("#### How it works\n")
            out.extend(f"{i}. {step}" for i, step in enumerate(c["how_it_works"], start=1))
            w("")
        diagram = c.get("diagram")
        if diagram and diagram.get("type") != "none" and diagram.get("mermaid"):
            _diagram(w, diagram)
        if c.get("examples"):
            w(f"#### {'Examples' if len(c['examples']) > 1 else 'Example'}\n")
            for ex in c["examples"]:
                label = (
                    f"{FROM_SOURCE}{cite(ex.get('source_refs'))}"
                    if ex["origin"] == "source"
                    else f"✦ {AI_EXAMPLE}"
                )
                w(f"- {ex['text'].strip()}  \n  _{label.strip()}_")
            w("")
        if c.get("analogy"):
            w("#### Think of it like this\n")
            w(c["analogy"]["text"].strip())
            if c["analogy"]["origin"] == "ai_generated":
                w(f"\n_✦ {AI_ANALOGY}_")
            w("")
        if c.get("common_mistake"):
            w("#### Common mistake\n")
            w(_quote_block(c["common_mistake"]) + "\n")
        if c.get("quick_check"):
            w("#### Quick check\n")
            for qc in c["quick_check"]:
                w(f"- **Q:** {qc['q']}  \n  **A:** {qc['a']}")
            w("")

    if content.get("facts"):
        w("## Key facts to remember\n")
        for f in content["facts"]:
            tag = FACT_KINDS.get(f["kind"], "Fact") + (
                ", teacher emphasis" if f.get("teacher_emphasis") else ""
            )
            line = f"- **{tag}:** {f['text']}"
            if f.get("quote"):
                line += f"  \n  > “{f['quote']}”{cite(f.get('source_refs'))}"
            if f.get("verified") is False:
                line += f"  \n  ⚠ _{UNVERIFIED}_"
            w(line)
        w("")

    if content.get("formulas"):
        w("## Formulas\n")
        for f in content["formulas"]:
            w(f"$$\n{f['latex']}\n$$\n")
            w(f["meaning"].strip() + cite(f.get("source_refs")))
            if f.get("verified") is False:
                w(f"\n⚠ _{UNVERIFIED}_")
            w("")

    if content.get("relationships"):
        w("## How the ideas connect\n")
        for r in content["relationships"]:
            a, b = titles.get(r["from"], r["from"]), titles.get(r["to"], r["to"])
            w(f"- **{a}** → {r['type']} → **{b}**: {' '.join(r['explanation'].split())}")
        w("")

    if content.get("summary"):
        w("## Summary\n")
        w(content["summary"].strip() + "\n")

    questions = content.get("questions", [])
    if questions:
        w("## Practice questions\n")
        for i, q in enumerate(questions, start=1):
            w(f"{i}. _({QUESTION_TYPES.get(q['type'], q['type'])})_ {q['prompt']}")
            for j, option in enumerate(q.get("options") or []):
                w(f"   - {chr(65 + j)}. {option}")
        w("")

    if content.get("review_checklist"):
        w("## Review checklist\n")
        out.extend(f"- [ ] {item}" for item in content["review_checklist"])
        w("")

    if content.get("not_covered"):
        w("## Not clearly covered in your material\n")
        w("You might expect these here. Check your textbook or ask your teacher.\n")
        out.extend(f"- {n}" for n in content["not_covered"])
        w("")

    if questions:
        w("## Answer key\n")
        for i, q in enumerate(questions, start=1):
            answer = q["answer"]
            if q.get("options") and answer in q["options"]:
                answer = f"{chr(65 + q['options'].index(answer))}. {answer}"
            explanation = " ".join((q.get("explanation") or "").split())
            w(f"{i}. **{answer}** {explanation}{cite(q.get('source_refs'))}")
        w("")

    if content.get("flashcards"):
        w("## Flashcards\n")
        w("| Front | Back |")
        w("|---|---|")
        out.extend(f"| {_cell(card['front'])} | {_cell(card['back'])} |" for card in content["flashcards"])
        w("")

    w("---\n")
    w(f"_{FOOTER}_\n")
    return "\n".join(out)


def _diagram(w, diagram: dict) -> None:
    try:
        parsed = mermaid.parse(diagram["mermaid"])
    except mermaid.MermaidError:
        return
    w("```mermaid")
    w(diagram["mermaid"].strip())
    w("```\n")
    if diagram.get("caption"):
        w(f"_{diagram['caption']}_\n")
    w("<details><summary>Diagram as text</summary>\n")
    for line in mermaid.as_text(parsed):
        w(f"    {line}")
    w("\n</details>\n")
