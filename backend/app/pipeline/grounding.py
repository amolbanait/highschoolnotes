"""Citation checks done by code, not trusted to the model.

Every ref must be a real segment; every quote must appear in a segment it cites (whitespace-,
case- and punctuation-style-insensitive). A quote found in a different segment re-points the
citation there; a quote found nowhere is kept but marked unverified.
"""

import re
import unicodedata
from dataclasses import dataclass

from app.diagrams import mermaid

_TRANSLATE = str.maketrans(
    {
        "‘": "'", "’": "'", "‛": "'", "′": "'",
        "“": '"', "”": '"', "‟": '"', "″": '"',
        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
        " ": " ", "…": "...",
    }
)  # fmt: skip


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(" .,;:\"'")


@dataclass
class Grounded:
    refs: list[str]
    verified: bool


class SourceIndex:
    def __init__(self, segments: list[dict]):
        self.segments = segments
        self.by_ref = {s["ref"]: s for s in segments}
        self.ordinal = {s["ref"]: i for i, s in enumerate(segments)}
        self._norm = {s["ref"]: normalize(s["text"]) for s in segments}

    def clean_refs(self, refs: list[str]) -> list[str]:
        seen: list[str] = []
        for ref in refs:
            ref = ref.strip()
            if ref in self.by_ref and ref not in seen:
                seen.append(ref)
        return sorted(seen, key=self.ordinal.__getitem__)

    def first_ordinal(self, refs: list[str]) -> int:
        known = [self.ordinal[r] for r in refs if r in self.ordinal]
        return min(known) if known else len(self.segments)

    def locate(self, quote: str) -> list[str]:
        needle = normalize(quote)
        if len(needle) < 3:
            return []
        hits = [ref for ref, text in self._norm.items() if needle in text]
        if hits:
            return hits
        # A quote may span the boundary between two consecutive segments.
        refs = [s["ref"] for s in self.segments]
        for a, b in zip(refs, refs[1:], strict=False):
            if needle in f"{self._norm[a]} {self._norm[b]}":
                return [a, b]
        return []

    def ground(self, quote: str | None, refs: list[str]) -> Grounded:
        cited = self.clean_refs(refs)
        if not quote:
            return Grounded(cited, bool(cited))
        needle = normalize(quote)
        if cited and any(needle and needle in self._norm[r] for r in cited):
            return Grounded(cited, True)
        found = self.locate(quote)
        if found:
            return Grounded(self.clean_refs(found), True)
        return Grounded(cited, False)

    def context_for(self, refs: list[str], neighbours: int = 1, limit: int = 24) -> list[dict]:
        """The cited segments plus their neighbours, in source order, for a section-writing call."""
        wanted: set[int] = set()
        for ref in self.clean_refs(refs):
            i = self.ordinal[ref]
            wanted.update(range(max(0, i - neighbours), min(len(self.segments), i + neighbours + 1)))
        ordered = sorted(wanted)[:limit]
        return [self.segments[i] for i in ordered]


def mermaid_problem(source: str) -> str | None:
    """None if the diagram parses with the supported Mermaid subset, otherwise a short reason."""
    return mermaid.problem(source)
