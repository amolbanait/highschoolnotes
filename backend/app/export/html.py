"""The guide as one self-contained HTML page: the HTML export, and the source of the PDF.

Model-written text is Markdown. It is rendered with raw HTML and images turned off, so neither
the source material nor the model can inject markup or make the PDF renderer fetch anything.
Diagrams are drawn as inline SVG; formulas are shown as readable text.
"""

from html import escape

from markdown_it import MarkdownIt

from app.diagrams import mermaid, svg
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
    latex_to_text,
    math_to_text,
)

_md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable("table")
_md.disable(["image", "link", "autolink"])  # model text never links or loads anything


def md(text: str | None) -> str:
    return _md.render(math_to_text(text or ""))


def md_inline(text: str | None) -> str:
    return _md.renderInline(math_to_text(text or ""))


CSS = """
@page { size: Letter; margin: 0.75in 0.7in 0.8in;
  @bottom-left { content: string(guide-title); font: 8pt "DejaVu Sans", Arial, sans-serif; color: #64748b; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 8pt "DejaVu Sans", Arial, sans-serif;
    color: #64748b; } }
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.5;
  color: #1e293b; max-width: 52rem; margin: 0 auto; padding: 1.5rem; background: #fff; }
@media print { body { padding: 0; max-width: none; } }
h1 { font-size: 22pt; margin: 0 0 .2rem; color: #0f172a; string-set: guide-title content(); }
h2 { font-size: 15pt; color: #0f172a; border-bottom: 2px solid #c7d2fe; padding-bottom: .2rem; margin: 1.6rem 0 .7rem;
  break-after: avoid; }
h3 { font-size: 12.5pt; color: #0f172a; margin: 1.2rem 0 .4rem; break-after: avoid; }
h4 { font-size: 9pt; text-transform: uppercase; letter-spacing: .04em; color: #64748b; margin: .9rem 0 .3rem;
  break-after: avoid; }
p { margin: .35rem 0; }
ul, ol { margin: .3rem 0; padding-left: 1.4rem; }
li { margin: .15rem 0; }
table { width: 100%; border-collapse: collapse; margin: .5rem 0; font-size: 9.5pt; }
th, td { border: 1px solid #e2e8f0; padding: .35rem .5rem; text-align: left; vertical-align: top; }
th { background: #f1f5f9; }
tr { break-inside: avoid; }
code { background: #f1f5f9; padding: 0 .2rem; border-radius: 3px; }
.meta { color: #475569; font-size: 9.5pt; margin-bottom: 1rem; }
.badge { display: inline-block; font-size: 8pt; padding: .05rem .45rem; border-radius: 999px; background: #e2e8f0;
  color: #334155; margin-right: .25rem; }
.badge.emphasis { background: #ede9fe; color: #5b21b6; } .badge.test { background: #e0e7ff; color: #3730a3; }
.cite { color: #64748b; font-size: 8.5pt; white-space: nowrap; }
.box { border-radius: 6px; padding: .5rem .75rem; margin: .4rem 0; break-inside: avoid; }
.warn { background: #fffbeb; border: 1px solid #fde68a; color: #78350f; }
.check { background: #fff7ed; border: 1px solid #fdba74; color: #7c2d12; }
.mistake { background: #fffbeb; border-left: 4px solid #f59e0b; }
.analogy { background: #f0f9ff; }
.example { background: #f8fafc; } .example.source { background: #ecfdf5; }
.label { font-size: 8pt; color: #64748b; margin-top: .2rem; } .label.source { color: #065f46; }
.quote { border-left: 3px solid #cbd5e1; padding-left: .6rem; font-style: italic; color: #475569; }
.formula { font-size: 12pt; font-family: "DejaVu Serif", Georgia, serif; margin: .2rem 0; }
figure { margin: .6rem 0; text-align: center; break-inside: avoid; }
figure svg { max-width: 100%; height: auto; }
figcaption { font-size: 9pt; color: #475569; }
.concept { break-before: auto; }
.concept-head { color: #4338ca; font-size: 9pt; font-weight: bold; margin-top: 1.4rem; break-after: avoid; }
.qa dt { font-weight: bold; margin-top: .4rem; } .qa dd { margin: .1rem 0 .3rem 1rem; }
.answers { break-before: page; }
.checklist { list-style: none; padding-left: 0; } .checklist li::before { content: "☐  "; }
.footer { margin-top: 2rem; font-size: 8.5pt; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: .5rem; }
"""


def to_html(content: dict, info: ExportInfo) -> str:
    out: list[str] = []
    w = out.append
    titles = concept_titles(content)

    def cite(refs) -> str:
        label = info.cite(refs)
        return f' <span class="cite">{escape(label)}</span>' if label else ""

    w(f"<h1>{escape(content.get('title') or info.title)}</h1>")
    meta = [f"Level: {escape(info.level_label)}"]
    if info.source_titles:
        meta.append("From: " + escape("; ".join(info.source_titles)))
    meta.append(f"Made {info.made_on_label}")
    w(f'<p class="meta">{" · ".join(meta)}</p>')

    if content.get("warnings"):
        w('<div class="box warn"><strong>Double-check these</strong><ul>')
        out.extend(f"<li>{escape(x)}</li>" for x in content["warnings"])
        w("</ul></div>")

    if content.get("overview"):
        w("<h2>What is this topic about?</h2>" + md(content["overview"]))
    if content.get("objectives"):
        w("<h3>By the end, you should be able to:</h3><ul>")
        out.extend(f"<li>{md_inline(o)}</li>" for o in content["objectives"])
        w("</ul>")

    if content.get("vocabulary"):
        w(
            "<h2>Key vocabulary</h2><table><thead><tr><th>Term</th><th>Simple meaning</th><th>Example</th></tr>"
        )
        w("</thead><tbody>")
        for v in content["vocabulary"]:
            note = f'<div class="label">⚠ {UNVERIFIED}</div>' if v.get("verified") is False else ""
            w(
                f"<tr><td><strong>{escape(v['term'])}</strong></td>"
                f"<td>{md_inline(v['definition'])}{cite(v.get('source_refs'))}{note}</td>"
                f"<td>{md_inline(v.get('example'))}</td></tr>"
            )
        w("</tbody></table>")

    concepts = content.get("concepts", [])
    if concepts:
        w("<h2>Main concepts</h2>")
    for number, c in enumerate(concepts, start=1):
        _concept(w, c, number, titles, cite)

    if content.get("facts"):
        w("<h2>Key facts to remember</h2><ul>")
        for f in content["facts"]:
            badges = f'<span class="badge">{FACT_KINDS.get(f["kind"], "Fact")}</span>'
            if f.get("teacher_emphasis"):
                badges += '<span class="badge emphasis">Teacher emphasis</span>'
            quote = (
                f'<div class="quote">“{escape(f["quote"])}”{cite(f.get("source_refs"))}</div>'
                if f.get("quote")
                else ""
            )
            note = f'<div class="label">⚠ {UNVERIFIED}</div>' if f.get("verified") is False else ""
            w(f"<li>{badges} {md_inline(f['text'])}{quote}{note}</li>")
        w("</ul>")

    if content.get("formulas"):
        w("<h2>Formulas</h2>")
        for f in content["formulas"]:
            note = f'<div class="label">⚠ {UNVERIFIED}</div>' if f.get("verified") is False else ""
            w(
                f'<div class="box example"><div class="formula">{escape(latex_to_text(f["latex"]))}</div>'
                f"{md(f['meaning'])}{cite(f.get('source_refs'))}{note}</div>"
            )

    if content.get("relationships"):
        w("<h2>How the ideas connect</h2><ul>")
        for r in content["relationships"]:
            a, b = titles.get(r["from"], r["from"]), titles.get(r["to"], r["to"])
            w(
                f"<li><strong>{escape(a)}</strong> → {escape(r['type'])} → <strong>{escape(b)}</strong>"
                f"{md(r['explanation'])}</li>"
            )
        w("</ul>")

    if content.get("summary"):
        w("<h2>Summary</h2>" + md(content["summary"]))

    questions = content.get("questions", [])
    if questions:
        w("<h2>Practice questions</h2><ol>")
        for q in questions:
            options = ""
            if q.get("options"):
                options = (
                    '<ol type="A">' + "".join(f"<li>{md_inline(o)}</li>" for o in q["options"]) + "</ol>"
                )
            kind = QUESTION_TYPES.get(q["type"], q["type"])
            w(f'<li><span class="badge">{kind}</span> {md_inline(q["prompt"])}{options}</li>')
        w("</ol>")

    if content.get("review_checklist"):
        w(
            '<h2>Review checklist</h2><p>Tick each one you could explain to a friend without notes.</p><ul class="checklist">'
        )
        out.extend(f"<li>{md_inline(item)}</li>" for item in content["review_checklist"])
        w("</ul>")

    if content.get("not_covered"):
        w("<h2>Not clearly covered in your material</h2>")
        w("<p>You might expect these here. Check your textbook or ask your teacher.</p><ul>")
        out.extend(f"<li>{escape(n)}</li>" for n in content["not_covered"])
        w("</ul>")

    if questions:
        w('<section class="answers"><h2>Answer key</h2><ol>')
        for q in questions:
            answer = q["answer"]
            if q.get("options") and answer in q["options"]:
                answer = f"{chr(65 + q['options'].index(answer))}. {answer}"
            w(
                f"<li><strong>{md_inline(answer)}</strong>{md(q.get('explanation'))}"
                f"{cite(q.get('source_refs'))}</li>"
            )
        w("</ol></section>")

    if content.get("flashcards"):
        w("<h2>Flashcards</h2><table><thead><tr><th>Front</th><th>Back</th></tr></thead><tbody>")
        for card in content["flashcards"]:
            w(f"<tr><td>{md_inline(card['front'])}</td><td>{md_inline(card['back'])}</td></tr>")
        w("</tbody></table>")

    w(f'<p class="footer">{escape(FOOTER)}</p>')
    title = escape(content.get("title") or info.title)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title><style>{CSS}</style></head><body>{''.join(out)}</body></html>"
    )


def _concept(w, c: dict, number: int, titles: dict[str, str], cite) -> None:
    badges = f'<span class="badge">{DIFFICULTY_LABELS.get(c["difficulty"], c["difficulty"])}</span>'
    if c.get("teacher_emphasis"):
        badges += '<span class="badge emphasis">Teacher emphasis</span>'
    if c.get("likely_on_test"):
        badges += '<span class="badge test">Likely on the test</span>'
    w(f'<section class="concept" id="{escape(c["id"])}">')
    w(f'<div class="concept-head">Concept {number} {badges}</div><h3>{escape(c["title"])}</h3>')
    if c.get("prerequisites"):
        names = ", ".join(titles.get(p, p) for p in c["prerequisites"])
        w(f'<p class="label">Builds on: {escape(names)}</p>')
    quality = c.get("quality") or {}
    if quality.get("needs_checking"):
        problems = "".join(f"<li>{escape(p)}</li>" for p in quality.get("problems", []))
        w(
            f'<div class="box check"><strong>⚠ {CHECK_THIS}</strong><p>{CHECK_THIS_BODY}</p>'
            + (f"<ul>{problems}</ul>" if problems else "")
            + "</div>"
        )
    w(md(c["concept"]) + cite(c.get("source_refs")))
    if c.get("levels"):
        w("<h4>Explain it three ways</h4>")
        for key, label in LEVEL_TABS:
            w(f"<p><strong>{label}</strong></p>{md(c['levels'].get(key))}")
    w(f"<h4>Why it matters</h4>{md(c['why_it_matters'])}")
    if c.get("how_it_works"):
        w(
            "<h4>How it works</h4><ol>"
            + "".join(f"<li>{md_inline(s)}</li>" for s in c["how_it_works"])
            + "</ol>"
        )
    diagram = c.get("diagram")
    if diagram and diagram.get("type") != "none" and diagram.get("mermaid"):
        w(_diagram(diagram))
    if c.get("examples"):
        w(f"<h4>{'Examples' if len(c['examples']) > 1 else 'Example'}</h4>")
        for ex in c["examples"]:
            if ex["origin"] == "source":
                label = f'<div class="label source">{FROM_SOURCE}{cite(ex.get("source_refs"))}</div>'
                w(f'<div class="box example source">{md(ex["text"])}{label}</div>')
            else:
                w(f'<div class="box example">{md(ex["text"])}<div class="label">✦ {AI_EXAMPLE}</div></div>')
    if c.get("analogy"):
        label = f'<div class="label">✦ {AI_ANALOGY}</div>' if c["analogy"]["origin"] == "ai_generated" else ""
        w(f'<h4>Think of it like this</h4><div class="box analogy">{md(c["analogy"]["text"])}{label}</div>')
    if c.get("common_mistake"):
        w(f'<h4>Common mistake</h4><div class="box mistake">{md(c["common_mistake"])}</div>')
    if c.get("quick_check"):
        w('<h4>Quick check</h4><dl class="qa">')
        for qc in c["quick_check"]:
            w(f"<dt>{md_inline(qc['q'])}</dt><dd>Answer: {md_inline(qc['a'])}</dd>")
        w("</dl>")
    w("</section>")


def _diagram(diagram: dict) -> str:
    caption = f"<figcaption>{escape(diagram.get('caption') or '')}</figcaption>"
    try:
        parsed = mermaid.parse(diagram["mermaid"])
    except mermaid.MermaidError:
        return ""
    return f"<figure>{svg.render(parsed)}{caption}</figure>"
