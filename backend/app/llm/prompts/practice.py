import json

from app.llm.prompts.common import system_prompt

ROLE = "You are an expert teacher writing practice questions and flashcards for a finished study guide."


def build(sections: list[dict], vocabulary: list[dict], facts: list[dict], level: str) -> tuple[str, str]:
    prompt = f"""Concept sections (id, title, content, source_refs):
{json.dumps(sections, ensure_ascii=False)}

Vocabulary:
{json.dumps(vocabulary, ensure_ascii=False)}

Key facts:
{json.dumps(facts, ensure_ascii=False)}

Write practice material that tests understanding, not just memory:
- questions: 2 or 3 per concept, mixing the types recall, understanding, application, comparison, scenario \
and test_style. Use every type at least once across the set. About half should be multiple choice with 4 \
options (exactly one correct, and answer must equal that option's text); the rest are open questions with \
empty options. Each answer gets an explanation. concept_id is the id of the concept tested (c1, c2, ...). \
source_refs are the segment ids the answer is grounded in, taken from that concept's source_refs or the \
vocabulary and facts above.
- flashcards: one per vocabulary term plus one per key fact or formula, front a short prompt and back the \
answer, with source_refs.
Answers must agree with the sections; do not introduce new facts."""
    return system_prompt(ROLE, level), prompt
