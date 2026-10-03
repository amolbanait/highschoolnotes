"""What every export format shares: labels, citations, maths as plain text, and the section order.

Exports render from the same guide document as the web view, in the same teaching order, with
the same honesty labels (AI-written examples, unverified quotes, sections to check).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

LEVEL_LABELS = {
    "middle_school": "Middle school",
    "high_school": "High school",
    "honors": "Honors",
    "ap": "AP",
    "college_intro": "Intro college",
}
DIFFICULTY_LABELS = {"easy": "Easier", "medium": "Medium", "hard": "Challenging"}
QUESTION_TYPES = {
    "recall": "Recall",
    "understanding": "Understanding",
    "application": "Apply it",
    "comparison": "Compare",
    "scenario": "Scenario",
    "test_style": "Test style",
}
FACT_KINDS = {
    "definition": "Definition",
    "date": "Date",
    "name": "Name",
    "event": "Event",
    "number": "Number",
    "rule": "Rule",
    "exception": "Exception",
    "cause_effect": "Cause and effect",
    "comparison": "Comparison",
    "other": "Fact",
}
LEVEL_TABS = (
    ("new", "Level 1: Explain like I'm new"),
    ("understand", "Level 2: Understand it"),
    ("deeper", "Level 3: Go deeper"),
)

AI_EXAMPLE = "AI-generated example"
AI_ANALOGY = "AI-written analogy; not from your material"
FROM_SOURCE = "From your material"
UNVERIFIED = "Could not be matched word for word to your material. Check it before you rely on it."
CHECK_THIS = "Check this against your source"
CHECK_THIS_BODY = (
    "An automatic review could not fully confirm this section against your material, even after "
    "rewriting it. Read it alongside your source."
)
FOOTER = (
    "Made with HighSchoolNotes. Facts come from your material and cite where they are; examples and "
    "analogies marked as AI-written were added to help explain."
)


@dataclass
class ExportInfo:
    title: str
    level: str
    source_titles: list[str] = field(default_factory=list)
    made_on: date = field(default_factory=date.today)

    @property
    def made_on_label(self) -> str:
        return f"{self.made_on:%B} {self.made_on.day}, {self.made_on.year}"

    @property
    def level_label(self) -> str:
        return LEVEL_LABELS.get(self.level, self.level)

    def ref_label(self, ref: str) -> str:
        """'p12-s3' -> 'p. 12'; 's7' -> 'part 7'; 'd2-p4-s1' -> 'Source 2, p. 4'; 't14m32s' -> '14:32';
        'v14m32s' -> '14:32 on screen' (as the web app shows them)."""
        doc = ""
        rest = ref
        multi = re.match(r"^d(\d+)-(.+)$", ref)
        if multi:
            doc = f"Source {multi.group(1)}, "
            rest = multi.group(2)
        paged = re.match(r"^p(\d+)-s\d+$", rest)
        if paged:
            return f"{doc}p. {paged.group(1)}"
        flowing = re.match(r"^s(\d+)$", rest)
        if flowing:
            return f"{doc}part {flowing.group(1)}"
        timed = re.match(r"^([tv])(?:(\d+)h)?(\d+)m(\d+)s(?:-\d+)?$", rest)
        if timed:
            kind, h, m, sec = timed.groups()
            clock = f"{int(h)}:{int(m):02d}:{sec}" if h else f"{int(m)}:{sec}"
            return f"{doc}{clock}{' on screen' if kind == 'v' else ''}"
        return ref

    def cite(self, refs: list[str] | None) -> str:
        """'(Source: p. 4, p. 5)', or '' when there are no refs."""
        labels = list(dict.fromkeys(self.ref_label(r) for r in refs or []))
        return f"(Source: {', '.join(labels)})" if labels else ""


def filename(title: str, ext: str) -> str:
    slug = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower()[:60] or "study-guide"
    return f"{slug}.{ext}"


def concept_titles(content: dict) -> dict[str, str]:
    titles: dict[str, str] = {}
    for c in content.get("concepts", []):
        titles[c["key"]] = c["title"]
        titles[c["id"]] = c["title"]
    return titles


# ---------- LaTeX as readable text (for formats that cannot typeset maths) ----------

_SUB = str.maketrans("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")
_SUP = str.maketrans("0123456789+-=()in", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁱⁿ")
_SUB_OK = set("0123456789+-=()aehijklmnoprstuvx")
_SUP_OK = set("0123456789+-=()in")
_SYMBOLS = {
    "rightarrow": "→",
    "to": "→",
    "longrightarrow": "⟶",
    "leftarrow": "←",
    "leftrightarrow": "↔",
    "rightleftharpoons": "⇌",
    "Rightarrow": "⇒",
    "times": "×",
    "cdot": "·",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "neq": "≠",
    "ne": "≠",
    "approx": "≈",
    "propto": "∝",
    "infty": "∞",
    "degree": "°",
    "circ": "°",
    "partial": "∂",
    "sum": "Σ",
    "int": "∫",
    "prod": "∏",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "rho": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "phi": "φ",
    "omega": "ω",
    "Delta": "Δ",
    "Sigma": "Σ",
    "Omega": "Ω",
    "Pi": "Π",
    "Theta": "Θ",
    "Lambda": "Λ",
    "Phi": "Φ",
    "Gamma": "Γ",
    "ldots": "…",
    "dots": "…",
    "cdots": "⋯",
    "%": "%",
    "$": "$",
    "&": "&",
    "#": "#",
    "_": "_",
    "{": "{",
    "}": "}",
}
_OPERATORS = {
    "rightarrow", "to", "longrightarrow", "leftarrow", "leftrightarrow", "rightleftharpoons", "Rightarrow",
    "times", "cdot", "div", "pm", "mp", "le", "leq", "ge", "geq", "neq", "ne", "approx", "propto",
}  # fmt: skip
_SPACES = {",": " ", ";": " ", ":": " ", "!": "", "quad": "  ", "qquad": "   ", " ": " "}
_WRAPPERS = {
    "text",
    "mathrm",
    "mathbf",
    "mathit",
    "textbf",
    "textit",
    "operatorname",
    "mathsf",
    "ce",
    "mathbb",
}


def latex_to_text(latex: str) -> str:
    """A readable plain-text version of a formula: 6CO_2 + 6H_2O \\rightarrow ... -> 6CO₂ + 6H₂O → ..."""
    try:
        text, _ = _read(latex.strip(), 0, stop=None)
    except (IndexError, ValueError):
        return latex
    return re.sub(r"[ \t]+", " ", text).strip()


def _group(s: str, i: int) -> tuple[str, int]:
    """Read one argument: a {braced group}, a \\command, or a single character."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s):
        return "", i
    if s[i] == "{":
        return _read(s, i + 1, stop="}")
    if s[i] == "\\":
        return _command(s, i)
    return s[i], i + 1


def _command(s: str, i: int) -> tuple[str, int]:
    match = re.match(r"\\([A-Za-z]+|.)", s[i:])
    if not match:
        return "", i + 1
    name, i = match.group(1), i + match.end()
    if name.isalpha():
        while i < len(s) and s[i] == " ":  # TeX ignores spaces after a control word
            i += 1
    if name in _SYMBOLS:
        return (f" {_SYMBOLS[name]} " if name in _OPERATORS else _SYMBOLS[name]), i
    if name in _SPACES:
        return _SPACES[name], i
    if name in _WRAPPERS:
        return _group(s, i)
    if name in ("left", "right", "big", "Big", "bigl", "bigr", "displaystyle"):
        return "", i
    if name == "frac" or name == "dfrac" or name == "tfrac":
        num, i = _group(s, i)
        den, i = _group(s, i)
        wrap = lambda x: x if re.fullmatch(r"[\w.]+", x) else f"({x})"  # noqa: E731
        return f"{wrap(num)}/{wrap(den)}", i
    if name == "sqrt":
        inner, i = _group(s, i)
        return f"√{inner}" if re.fullmatch(r"[\w.]+", inner) else f"√({inner})", i
    if name == "vec":
        inner, i = _group(s, i)
        return f"{inner}⃗", i
    if name in ("overline", "bar"):
        inner, i = _group(s, i)
        return inner, i
    return name, i


def _read(s: str, i: int, stop: str | None) -> tuple[str, int]:
    out: list[str] = []
    while i < len(s):
        ch = s[i]
        if stop and ch == stop:
            return "".join(out), i + 1
        if ch == "\\":
            text, i = _command(s, i)
            out.append(text)
        elif ch in "_^":
            arg, i = _group(s, i + 1)
            ok, table, mark = (_SUB_OK, _SUB, "_") if ch == "_" else (_SUP_OK, _SUP, "^")
            if arg and set(arg) <= ok:
                out.append(arg.translate(table))
            else:
                out.append(f"{mark}({arg})")
        elif ch == "{":
            text, i = _read(s, i + 1, stop="}")
            out.append(text)
        elif ch == "}":
            i += 1
        elif ch == "~":
            out.append(" ")
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out), i


_INLINE_MATH = re.compile(r"\$\$(.+?)\$\$|(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)", re.S)


def math_to_text(text: str) -> str:
    """Replace $...$ and $$...$$ maths inside prose with readable plain text."""
    return _INLINE_MATH.sub(lambda m: latex_to_text(m.group(1) or m.group(2)), text)
