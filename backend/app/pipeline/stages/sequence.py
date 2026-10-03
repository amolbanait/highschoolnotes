"""Stage 4 (code): order concepts so prerequisites come first, assign ids, check every citation.

Ties are broken by where a concept first appears in the source. Prerequisite cycles are broken
at the concept that appears earliest, and the dropped edge is recorded as a warning.
"""

import heapq
import re

from app.pipeline.grounding import SourceIndex


def run(plan: dict, index: SourceIndex) -> dict:
    warnings: list[str] = []
    concepts = _unique_concepts(plan.get("concepts", []))
    keys = [c["key"] for c in concepts]
    for c in concepts:
        c["source_refs"] = index.clean_refs(c.get("source_refs", []))
        c["prerequisites"] = [
            p for p in dict.fromkeys(c.get("prerequisites", [])) if p in keys and p != c["key"]
        ]

    order = _topological(concepts, index, warnings)
    id_by_key = {key: f"c{i + 1}" for i, key in enumerate(order)}
    by_key = {c["key"]: c for c in concepts}
    ordered = []
    for key in order:
        c = by_key[key]
        ordered.append(
            {
                "id": id_by_key[key],
                "key": key,
                "title": c["title"],
                "summary": c.get("summary", ""),
                "difficulty": c.get("difficulty", "medium"),
                "prerequisites": [id_by_key[p] for p in c["prerequisites"]],
                "source_refs": c["source_refs"],
                "teacher_emphasis": bool(c.get("teacher_emphasis")),
                "likely_on_test": bool(c.get("likely_on_test")),
                "diagram": c.get("diagram", "none"),
            }
        )

    vocabulary = []
    for item in plan.get("vocabulary", []):
        grounded = index.ground(item.get("quote"), item.get("source_refs", []))
        if not grounded.refs:
            warnings.append(f"Dropped vocabulary term without a valid source reference: {item.get('term')}")
            continue
        vocabulary.append(
            {
                "id": f"v{len(vocabulary) + 1}",
                "term": item["term"],
                "definition": item["definition"],
                "example": item.get("example") or None,
                "quote": item.get("quote"),
                "verified": grounded.verified,
                "source_refs": grounded.refs,
            }
        )

    facts = []
    for item in plan.get("facts", []):
        grounded = index.ground(item.get("quote"), item.get("source_refs", []))
        if not grounded.refs:
            warnings.append("Dropped a fact that did not point to the source.")
            continue
        facts.append(
            {
                "id": f"k{len(facts) + 1}",
                "text": item["text"],
                "kind": item.get("kind", "other"),
                "quote": item.get("quote", ""),
                "verified": grounded.verified,
                "teacher_emphasis": bool(item.get("teacher_emphasis")),
                "source_refs": grounded.refs,
            }
        )

    formulas = []
    for item in plan.get("formulas", []):
        grounded = index.ground(item.get("quote"), item.get("source_refs", []))
        if not grounded.refs:
            warnings.append(f"Dropped a formula that did not point to the source: {item.get('latex')}")
            continue
        formulas.append(
            {
                "id": f"m{len(formulas) + 1}",
                "latex": item["latex"],
                "meaning": item["meaning"],
                "quote": item.get("quote"),
                "verified": grounded.verified,
                "source_refs": grounded.refs,
            }
        )

    relationships = [
        {
            "from": id_by_key[r["from_key"]],
            "to": id_by_key[r["to_key"]],
            "type": r["type"],
            "explanation": r["explanation"],
        }
        for r in plan.get("relationships", [])
        if r.get("from_key") in id_by_key and r.get("to_key") in id_by_key and r["from_key"] != r["to_key"]
    ]

    return {
        "title": plan.get("title") or "Study guide",
        "topics": plan.get("topics", []),
        "concepts": ordered,
        "vocabulary": vocabulary,
        "facts": facts,
        "formulas": formulas,
        "relationships": relationships,
        "not_covered": plan.get("not_covered", []),
        "warnings": warnings,
    }


def _unique_concepts(concepts: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for c in concepts:
        key = re.sub(r"[^a-z0-9]+", "-", (c.get("key") or c.get("title", "")).lower()).strip("-") or "concept"
        base, n = key, 2
        while key in seen:
            key, n = f"{base}-{n}", n + 1
        seen.add(key)
        # Keep prerequisite references pointing at the normalized key.
        out.append({**c, "key": key, "_original_key": c.get("key")})
    remap = {c["_original_key"]: c["key"] for c in out if c["_original_key"]}
    for c in out:
        c["prerequisites"] = [remap.get(p, p) for p in c.get("prerequisites", [])]
    return out


def _topological(concepts: list[dict], index: SourceIndex, warnings: list[str]) -> list[str]:
    position = {c["key"]: (index.first_ordinal(c["source_refs"]), i) for i, c in enumerate(concepts)}
    pending = {c["key"]: set(c["prerequisites"]) for c in concepts}
    dependents: dict[str, list[str]] = {c["key"]: [] for c in concepts}
    for key, prereqs in pending.items():
        for p in prereqs:
            dependents[p].append(key)

    ready = [(position[k], k) for k, prereqs in pending.items() if not prereqs]
    heapq.heapify(ready)
    order: list[str] = []
    done: set[str] = set()
    while len(order) < len(concepts):
        if not ready:
            # A cycle: release the earliest remaining concept and drop its unmet prerequisites.
            key = min((k for k in pending if k not in done), key=position.__getitem__)
            for p in sorted(pending[key]):
                warnings.append(f"Circular prerequisites between '{key}' and '{p}'; '{key}' is taught first.")
                for c in concepts:
                    if c["key"] == key:
                        c["prerequisites"] = [x for x in c["prerequisites"] if x != p]
            pending[key] = set()
            heapq.heappush(ready, (position[key], key))
        _, key = heapq.heappop(ready)
        if key in done:
            continue
        order.append(key)
        done.add(key)
        for d in dependents[key]:
            pending[d].discard(key)
            if not pending[d] and d not in done:
                heapq.heappush(ready, (position[d], d))
    return order
