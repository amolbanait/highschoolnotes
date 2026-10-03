// Types generated from the backend (python -m app.export_schemas, then npm run gen:types).
import type { components, operations } from "@/lib/schema/api";
import type {
  Concept,
  Diagram,
  Example,
  Fact,
  Flashcard,
  Formula,
  Question,
  Relationship,
  StudyGuideContent,
  VocabItem,
} from "@/lib/schema/study-guide";

type Schemas = components["schemas"];

export type User = Schemas["UserOut"];
export type Source = Schemas["SourceOut"];
export type Segment = Schemas["SegmentOut"];
export type GuideRef = Schemas["GuideRefOut"];
export type GuideSummary = Schemas["GuideSummaryOut"];
export type GuideList = Schemas["GuideListOut"];
export type QuizResult = Schemas["QuizAttemptOut"];
export type Level = NonNullable<Schemas["UpdateMeIn"]["default_level"]>;
export type FlashcardRating = Schemas["FlashcardReviewIn"]["rating"];
export type ExportFormat = NonNullable<
  NonNullable<operations["export_guide_api_v1_guides__guide_id__export_get"]["parameters"]["query"]>["format"]
>;

/** GET /guides/{id}. `content` is typed loosely by the API, so it is narrowed to the guide schema here. */
export type Guide = Omit<Schemas["GuideOut"], "content" | "progress" | "error"> & {
  content: StudyGuideContent | null;
  progress: { stage: string | null; done?: string[]; sections?: number } | null;
  error: { code?: string; message?: string } | null;
};

export type {
  Concept,
  Diagram,
  Example,
  Fact,
  Flashcard,
  Formula,
  Question,
  Relationship,
  StudyGuideContent,
  VocabItem,
};
