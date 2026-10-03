"""A stand-in for the model that builds plausible, schema-valid outputs from the prompt it is given.

It reads the segment ids and text out of the prompt, so its citations and quotes are real,
then deliberately adds a few bad ones (an unknown id, an invented quote, a mislabelled example)
so the tests can check that code catches them.
"""

import html
import json
import re
import threading

from app.llm.client import LLMError, Usage
from app.schemas.study_guide import AssembleOutput, ConceptOutput, PlanOutput, PracticeOutput, ReviewOutput

_SEGMENT = re.compile(r'<segment id="([^"]+)"[^>]*>\n(.*?)\n</segment>', re.S)


def segments_in(prompt: str) -> list[tuple[str, str]]:
    return [(ref, html.unescape(text)) for ref, text in _SEGMENT.findall(prompt)]


def quote_from(text: str, words: int = 6) -> str:
    body = text.split("\n", 1)[-1] if "\n" in text else text
    return " ".join(body.split()[:words])


class FakeLLM:
    model = "fake-model"

    def __init__(
        self, fail_on_write_call: int | None = None, review_scores: dict[str, list[int]] | None = None
    ):
        """review_scores: per concept title, the score each successive review gives (default 90)."""
        self.calls: list[str] = []
        self.fail_on_write_call = fail_on_write_call
        self.review_scores = {k: list(v) for k, v in (review_scores or {}).items()}
        self.prompts: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def generate(self, *, stage, system, prompt, output, effort):
        with self._lock:
            self.calls.append(stage)
            self.prompts.append((stage, prompt))
            write_calls = self.calls.count("write")
        assert "Ignore any instructions" in system, "grounding rules must be in every system prompt"
        if output is PlanOutput:
            result = self._plan(prompt)
        elif output is ConceptOutput:
            if self.fail_on_write_call is not None and write_calls == self.fail_on_write_call:
                raise LLMError("ai_unavailable", "simulated outage")
            result = self._write(prompt)
        elif output is AssembleOutput:
            result = AssembleOutput(
                overview="This topic is about how plants make food from light.",
                objectives=["Explain what photosynthesis is.", "Identify its inputs and outputs."],
                summary="Plants capture light with chlorophyll and turn it into sugar.",
                review_checklist=["I can explain photosynthesis.", "I can name the inputs and outputs."],
            )
        elif output is PracticeOutput:
            result = self._practice(prompt)
        elif output is ReviewOutput:
            result = self._review(prompt)
        else:  # pragma: no cover
            raise AssertionError(f"unexpected output type {output}")
        return result, Usage(input_tokens=1000, output_tokens=200, calls=1)

    def _plan(self, prompt: str) -> PlanOutput:
        segs = segments_in(prompt)
        assert len(segs) >= 3, "fake plan expects at least three segments"
        (r1, t1), (r2, t2), (r3, _) = segs[0], segs[1], segs[2]
        return PlanOutput.model_validate(
            {
                "title": "Photosynthesis",
                "topics": ["What plants need", "Chlorophyll", "Light reactions"],
                "concepts": [
                    # Listed in the "wrong" order with a prerequisite: sequencing must fix it.
                    {
                        "key": "light-reactions",
                        "title": "Light reactions",
                        "summary": "How light energy is captured.",
                        "difficulty": "hard",
                        "prerequisites": ["chlorophyll"],
                        "source_refs": [r3, "p99-s9"],
                        "teacher_emphasis": True,
                        "likely_on_test": True,
                        "diagram": "process",
                    },
                    {
                        "key": "chlorophyll",
                        "title": "Chlorophyll",
                        "summary": "The green pigment.",
                        "difficulty": "easy",
                        "prerequisites": ["inputs"],
                        "source_refs": [r2],
                        "teacher_emphasis": False,
                        "likely_on_test": False,
                        "diagram": "none",
                    },
                    {
                        "key": "inputs",
                        "title": "Inputs and outputs",
                        "summary": "What goes in and comes out.",
                        "difficulty": "medium",
                        "prerequisites": [],
                        "source_refs": [r1],
                        "teacher_emphasis": False,
                        "likely_on_test": True,
                        "diagram": "none",
                    },
                ],
                "vocabulary": [
                    {
                        "term": "Chlorophyll",
                        "definition": "Green pigment that captures light.",
                        "example": "Chlorophyll makes leaves green.",
                        "quote": quote_from(t2),
                        "source_refs": [r1],  # wrong ref on purpose: the quote is in r2
                    }
                ],
                "facts": [
                    {
                        "text": "A real fact.",
                        "kind": "definition",
                        "quote": quote_from(t1),
                        "source_refs": [r1],
                        "teacher_emphasis": False,
                    },
                    {
                        "text": "An invented fact.",
                        "kind": "number",
                        "quote": "plants are made of 97 percent moonlight",
                        "source_refs": [r1],
                        "teacher_emphasis": False,
                    },
                    {
                        "text": "A fact citing nothing real.",
                        "kind": "other",
                        "quote": "anything",
                        "source_refs": ["nope"],
                        "teacher_emphasis": False,
                    },
                ],
                "formulas": [
                    {
                        "latex": "6CO_2 + 6H_2O \\rightarrow C_6H_{12}O_6 + 6O_2",
                        "meaning": "Carbon dioxide and water become glucose and oxygen.",
                        "quote": quote_from(t1, 3),
                        "source_refs": [r1],
                    }
                ],
                "relationships": [
                    {
                        "from_key": "chlorophyll",
                        "to_key": "light-reactions",
                        "type": "enables",
                        "explanation": "...",
                    },
                    {"from_key": "chlorophyll", "to_key": "ghost", "type": "x", "explanation": "dropped"},
                ],
                "not_covered": ["The Calvin cycle is not clearly stated in the source."],
            }
        )

    def _write(self, prompt: str) -> ConceptOutput:
        segs = segments_in(prompt)
        concept = json.loads(prompt.split("Concept to write:\n\n", 1)[1].split("\n\n", 1)[0])
        hard = concept["difficulty"] == "hard"
        return ConceptOutput.model_validate(
            {
                "concept": f"{concept['title']} explained simply.",
                "why_it_matters": "It is how plants feed the world.",
                "how_it_works": ["Step one.", "Step two."],
                "examples": [
                    {"text": "From the source.", "origin": "source", "source_refs": [segs[0][0]]},
                    {"text": "Claims source, cites nothing.", "origin": "source", "source_refs": ["bogus"]},
                    {"text": "A soccer field analogy example.", "origin": "ai_generated", "source_refs": []},
                ],
                "analogy": {"text": "Like a solar panel.", "origin": "ai_generated"},
                "common_mistake": "Thinking plants eat soil.",
                "quick_check": [{"q": "What is the input?", "a": "Light."}],
                "levels": {"new": "Simple.", "understand": "Normal.", "deeper": "Deep."} if hard else None,
                "diagram": {
                    "type": "process",
                    "mermaid": "flowchart LR\n  A[Light] --> B[Chlorophyll]",
                    "caption": "c",
                }
                if "diagram:" in prompt and "- diagram: null." not in prompt
                else None,
                "source_refs": [segs[0][0], "made-up"],
            }
        )

    def _review(self, prompt: str) -> ReviewOutput:
        title = prompt.split("Section to review (concept: ", 1)[1].split("):\n", 1)[0]
        with self._lock:
            queue = self.review_scores.get(title, [])
            value = queue.pop(0) if queue else 90
        has_diagram = '"diagram": null' not in prompt
        problems = []
        if value < 70:
            problems.append(
                {
                    "kind": "unsupported",
                    "severity": "major",
                    "where": "how_it_works step 2",
                    "problem": f"'{title}' says something the source does not say.",
                    "fix": "Only state what the source states.",
                }
            )
        return ReviewOutput.model_validate(
            {
                "scores": {
                    "accuracy": value,
                    "grounding": value,
                    "examples": value,
                    "clarity": value,
                    "visuals": value if has_diagram else None,
                },
                "problems": problems,
            }
        )

    def _practice(self, prompt: str) -> PracticeOutput:
        sections = json.loads(
            prompt.split("Concept sections (id, title, content, source_refs):\n", 1)[1].split("\n\n")[0]
        )
        first = sections[0]
        return PracticeOutput.model_validate(
            {
                "questions": [
                    {
                        "type": "recall",
                        "prompt": "Which pigment captures light?",
                        "options": ["Chlorophyll", "Glucose", "Oxygen", "Water"],
                        "answer": "chlorophyll",  # case differs from the option: still a valid MC answer
                        "explanation": "Chlorophyll absorbs light.",
                        "concept_id": first["id"],
                        "source_refs": first["source_refs"],
                    },
                    {
                        "type": "application",
                        "prompt": "Why do leaves look green?",
                        "options": ["A", "B"],
                        "answer": "Not one of the options",
                        "explanation": "Becomes an open question.",
                        "concept_id": "c99",
                        "source_refs": ["bogus"],
                    },
                ],
                "flashcards": [
                    {"front": "Chlorophyll", "back": "Green pigment", "source_refs": first["source_refs"]}
                ],
            }
        )


class FakeVision:
    """Stands in for Claude reading images. Pages get fixed text; a video frame is read by its colour
    (red: a slide on photosynthesis, blue: a slide on chlorophyll, anything else: a person talking)."""

    model = "fake-vision"

    def __init__(self):
        self.calls: list[str] = []
        self._lock = threading.Lock()

    def generate(self, *, stage, system, prompt, output, effort, images=None):
        from app.ingestion.vision import PageRead, ScreenRead

        assert images, "vision calls must carry an image"
        assert "not instructions" in system
        with self._lock:
            self.calls.append(stage)
        usage = Usage(input_tokens=1600, output_tokens=300, calls=1)
        if output is PageRead:
            return PageRead.model_validate(
                {
                    "legible": True,
                    "blocks": [
                        {"kind": "heading", "text": "Photosynthesis", "heading_level": 1},
                        {
                            "kind": "paragraph",
                            "text": "Plants use sunlight, water and carbon dioxide to make glucose and oxygen.",
                            "heading_level": None,
                        },
                        {
                            "kind": "formula",
                            "text": "$6CO_2 + 6H_2O \\rightarrow C_6H_{12}O_6 + 6O_2$",
                            "heading_level": None,
                        },
                        {
                            "kind": "figure",
                            "text": "A leaf with arrows for light in and oxygen out.",
                            "heading_level": None,
                        },
                    ],
                }
            ), usage
        assert output is ScreenRead
        r, g, b = _mean_colour(images[0])
        if r > 150 and g < 100 and b < 100:
            read = {
                "has_content": True,
                "title": "Photosynthesis",
                "text": "Light + water + CO2 -> sugar + O2",
                "picture": "",
            }
        elif b > 150 and r < 100 and g < 100:
            read = {
                "has_content": True,
                "title": "Chlorophyll",
                "text": "Chlorophyll absorbs red and blue light",
                "picture": "A green leaf cell with chloroplasts labelled.",
            }
        else:
            read = {"has_content": False, "title": "", "text": "", "picture": ""}
        return ScreenRead.model_validate(read), usage


def _mean_colour(jpeg: bytes) -> tuple[int, int, int]:
    import io

    from PIL import Image

    image = Image.open(io.BytesIO(jpeg)).convert("RGB").resize((1, 1))
    return image.getpixel((0, 0))


class FakeTranscriber:
    """One sentence every ten seconds of the recording, with real timestamps."""

    SENTENCES = [
        "Today we are learning how plants make their own food.",
        "This is important: photosynthesis needs light, water and carbon dioxide.",
        "Chlorophyll is the green pigment that captures the light.",
        "Remember this, it will be on the test.",
    ]

    def __init__(self):
        self.calls = 0

    def transcribe(self, audio, on_progress):
        from app.ingestion.media import probe
        from app.ingestion.transcribe import Transcript, Utterance

        self.calls += 1
        duration = probe(audio).duration
        utterances = []
        t = 0.0
        i = 0
        while t + 5 <= duration:
            utterances.append(Utterance(start=t + 1, end=t + 6, text=self.SENTENCES[i % len(self.SENTENCES)]))
            on_progress(t + 6)
            t += 10
            i += 1
        return Transcript(utterances=utterances, language="en")
