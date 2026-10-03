import json

from app.llm.prompts.common import system_prompt

ROLE = "You are an expert teacher finishing a study guide whose concept sections are already written."


def build(title: str, sections: list[dict], level: str) -> tuple[str, str]:
    prompt = f"""Study guide: {title}

Finished concept sections, in teaching order:
{json.dumps(sections, ensure_ascii=False)}

Write the parts that frame the guide, based only on the sections above:
- overview: "What is this topic about?" in 2 to 5 simple sentences.
- objectives: what the student should be able to do after studying, each starting with a verb \
(Explain, Identify, Describe, Compare, Calculate ...). One per major concept or skill.
- summary: a short recap that ties the concepts together in order.
- review_checklist: 5 to 12 items starting with "I can ..." that a student ticks off before a test."""
    return system_prompt(ROLE, level), prompt
