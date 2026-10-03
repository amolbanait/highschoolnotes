"""The study guide document and the structured outputs each model stage returns.

The guide is one JSON document (stored as JSONB). Every concept, fact, example, question and
flashcard has a stable id, source_refs (segment refs) and, where it matters, an origin saying
whether it came from the source or was written by the AI.

The *Output models are sent to Claude as structured-output schemas, so they stay simple:
no free-form dicts, every field present, None where a value does not apply.
"""

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1

Level = Literal["middle_school", "high_school", "honors", "ap", "college_intro"]
LEVELS: tuple[str, ...] = ("middle_school", "high_school", "honors", "ap", "college_intro")
Difficulty = Literal["easy", "medium", "hard"]
Origin = Literal["source", "ai_generated"]
DiagramKind = Literal["none", "process", "cycle", "hierarchy", "comparison", "timeline", "cause_effect"]
FactKind = Literal[
    "definition",
    "date",
    "name",
    "event",
    "number",
    "rule",
    "exception",
    "cause_effect",
    "comparison",
    "other",
]
QuestionType = Literal["recall", "understanding", "application", "comparison", "scenario", "test_style"]


# ---------- Stage 3: plan ----------


class PlannedConcept(BaseModel):
    key: str = Field(description="Short unique slug, e.g. 'light-reactions'")
    title: str
    summary: str = Field(description="One or two sentences on what this concept covers")
    difficulty: Difficulty
    prerequisites: list[str] = Field(description="Keys of other concepts a student must understand first")
    source_refs: list[str] = Field(description="Segment ids that cover this concept")
    teacher_emphasis: bool = Field(
        description="The source explicitly stresses this (e.g. 'remember', 'on the test')"
    )
    likely_on_test: bool = Field(description="Your judgement that this is likely to be tested")
    diagram: DiagramKind = Field(
        description="Structure a diagram would show, or 'none' if a diagram would not help"
    )


class PlannedVocab(BaseModel):
    term: str
    definition: str = Field(description="Simple definition at the student's level")
    example: str = Field(description="A short, concrete example of the term in use")
    quote: str = Field(description="Short verbatim quote from the source that defines or uses the term")
    source_refs: list[str]


class PlannedFact(BaseModel):
    text: str = Field(description="The fact in simple words")
    kind: FactKind
    quote: str = Field(description="Short verbatim quote from the source that states this fact")
    source_refs: list[str]
    teacher_emphasis: bool


class PlannedFormula(BaseModel):
    latex: str = Field(description="The formula in LaTeX, copied exactly from the source")
    meaning: str = Field(description="What it means and what each symbol stands for")
    quote: str = Field(description="Verbatim text of the formula or the sentence around it in the source")
    source_refs: list[str]


class PlannedRelationship(BaseModel):
    from_key: str
    to_key: str
    type: str = Field(description="e.g. causes, produces, is part of, contrasts with, depends on")
    explanation: str


class PlanOutput(BaseModel):
    title: str = Field(description="Short title for the study guide")
    topics: list[str] = Field(description="The main topics, in teaching order")
    concepts: list[PlannedConcept]
    vocabulary: list[PlannedVocab]
    facts: list[PlannedFact]
    formulas: list[PlannedFormula]
    relationships: list[PlannedRelationship]
    not_covered: list[str] = Field(
        description="Things a student would expect here that the source does not clearly state"
    )


# ---------- Stage 5: write one concept ----------


class Example(BaseModel):
    text: str
    origin: Origin
    source_refs: list[str] = Field(description="Segment ids; empty for AI-generated examples")


class Analogy(BaseModel):
    text: str
    origin: Origin


class QuickCheck(BaseModel):
    q: str
    a: str


class Levels(BaseModel):
    new: str = Field(description="Level 1, Explain Like I'm New: very simple")
    understand: str = Field(description="Level 2, Understand It: normal explanation for the chosen level")
    deeper: str = Field(description="Level 3, Go Deeper: more detail for curious students")


class Diagram(BaseModel):
    type: DiagramKind
    mermaid: str = Field(description="Mermaid source (flowchart, timeline or mindmap)")
    caption: str


class ConceptOutput(BaseModel):
    concept: str = Field(description="The idea in simple language")
    why_it_matters: str
    how_it_works: list[str] = Field(description="Step-by-step explanation, one step per item")
    examples: list[Example]
    analogy: Analogy | None
    common_mistake: str
    quick_check: list[QuickCheck]
    levels: Levels | None = Field(description="Only for difficult concepts; otherwise null")
    diagram: Diagram | None = Field(description="Only when the plan asked for one; otherwise null")
    source_refs: list[str]


# ---------- Stage 6: assemble ----------


class AssembleOutput(BaseModel):
    overview: str = Field(description="What is this topic about? 2 to 5 simple sentences")
    objectives: list[str] = Field(
        description="By the end, you should be able to ... (each item starts with a verb)"
    )
    summary: str
    review_checklist: list[str] = Field(description="Items that start with 'I can ...'")


# ---------- Stage 7: practice ----------


class QuestionOutput(BaseModel):
    type: QuestionType
    prompt: str
    options: list[str] = Field(description="Answer choices for multiple choice; empty for open questions")
    answer: str = Field(description="For multiple choice, exactly one of the options")
    explanation: str
    concept_id: str
    source_refs: list[str]


class FlashcardOutput(BaseModel):
    front: str
    back: str
    source_refs: list[str]


class PracticeOutput(BaseModel):
    questions: list[QuestionOutput]
    flashcards: list[FlashcardOutput]


# ---------- Quality review (a separate, cheaper model) ----------

ProblemKind = Literal[
    "inaccurate",
    "unsupported",
    "changed_formula_or_number",
    "wrong_example",
    "mislabelled_origin",
    "unclear_for_level",
    "unhelpful_diagram",
    "missing_key_point",
    "other",
]


class ReviewScores(BaseModel):
    accuracy: int = Field(description="0 to 100: every statement agrees with the source")
    grounding: int = Field(description="0 to 100: claims are supported by the source; nothing invented")
    examples: int = Field(description="0 to 100: examples and analogies are correct and honestly labelled")
    clarity: int = Field(description="0 to 100: a student at the stated level can follow it")
    visuals: int | None = Field(description="0 to 100: the diagram helps understanding; null if no diagram")


class ReviewProblem(BaseModel):
    kind: ProblemKind
    severity: Literal["major", "minor"] = Field(
        description="major: a student could learn something false or miss the main idea"
    )
    where: str = Field(description="Which part, e.g. 'how_it_works step 2', 'examples 1', 'diagram'")
    problem: str = Field(description="What is wrong, in one plain sentence a student could understand")
    fix: str = Field(description="How the writer should fix it, in one sentence")


class ReviewOutput(BaseModel):
    scores: ReviewScores
    problems: list[ReviewProblem]


# ---------- The stored guide document ----------


class Quality(BaseModel):
    score: int | None = Field(default=None, description="0 to 100 from the review; None if not reviewed")
    flags: list[str] = Field(default_factory=list)
    reviewed: bool = False
    rewritten: bool = Field(default=False, description="Rewritten once because the first review was low")
    needs_checking: bool = Field(
        default=False, description="Still below the threshold after a rewrite: check it against the source"
    )
    problems: list[str] = Field(
        default_factory=list, description="What the reviewer could not confirm, shown to the student"
    )


class VocabItem(BaseModel):
    id: str
    term: str
    definition: str
    example: str | None = None
    quote: str | None = None
    verified: bool = True
    source_refs: list[str]


class Concept(BaseModel):
    id: str
    key: str
    title: str
    difficulty: Difficulty
    prerequisites: list[str]
    teacher_emphasis: bool = False
    likely_on_test: bool = False
    concept: str
    why_it_matters: str
    how_it_works: list[str]
    examples: list[Example]
    analogy: Analogy | None = None
    common_mistake: str
    quick_check: list[QuickCheck]
    levels: Levels | None = None
    diagram: Diagram | None = None
    source_refs: list[str]
    quality: Quality = Field(default_factory=Quality)


class Fact(BaseModel):
    id: str
    text: str
    kind: FactKind
    quote: str
    verified: bool = True
    teacher_emphasis: bool = False
    source_refs: list[str]


class Formula(BaseModel):
    id: str
    latex: str
    meaning: str
    quote: str | None = None
    verified: bool = True
    source_refs: list[str]


class Relationship(BaseModel):
    from_: str = Field(alias="from")
    to: str
    type: str
    explanation: str

    model_config = {"populate_by_name": True}


class Question(BaseModel):
    id: str
    type: QuestionType
    prompt: str
    options: list[str]
    answer: str
    explanation: str
    concept_id: str | None
    source_refs: list[str]


class Flashcard(BaseModel):
    id: str
    front: str
    back: str
    source_refs: list[str]


class StudyGuideContent(BaseModel):
    schema_version: int = SCHEMA_VERSION
    title: str
    level: Level
    topics: list[str] = Field(default_factory=list)
    overview: str | None = None
    objectives: list[str] = Field(default_factory=list)
    vocabulary: list[VocabItem] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    summary: str | None = None
    questions: list[Question] = Field(default_factory=list)
    flashcards: list[Flashcard] = Field(default_factory=list)
    review_checklist: list[str] = Field(default_factory=list)
    not_covered: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
